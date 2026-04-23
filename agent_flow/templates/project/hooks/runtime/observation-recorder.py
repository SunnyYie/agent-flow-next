#!/usr/bin/env python3
"""
AgentFlow Observation Recorder — PostToolUse hook
在每次工具调用后，静默捕获操作记录到 SQLite 数据库。

捕获字段：session_id, timestamp, tool_name, tool_input_summary,
tool_output_summary, file_path, project_dir, layer, observation_type

性能目标：< 50ms（SQLite WAL 模式单行插入 ~5ms）
"""
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# --- 配置 ---

# 数据库路径：优先项目级，回退全局
DB_DIR_PROJECT = ".agent-flow"
DB_DIR_DEV = ".dev-workflow"
DB_FILENAME = "observations.db"

# 会话标记文件
SESSION_MARKER = ".agent-flow/state/.current-session-id"

# 输出截断
MAX_OUTPUT_SUMMARY = 500
MAX_INPUT_SUMMARY = 500

# 噪声过滤：跳过这些路径下的 Read
NOISE_PATH_PREFIXES = (
    ".git/", "node_modules/", "__pycache__/", ".venv/", "venv/",
    ".mypy_cache/", ".pytest_cache/", ".ruff_cache/", "dist/", "build/",
)

# 噪声过滤：跳过这些 Bash 命令
NOISE_BASH_COMMANDS = (
    "ls", "pwd", "whoami", "echo", "cat", "head", "tail",
    "which", "type", "uname", "date", "id",
)

# 知识路径关键词 — 搜索这些路径视为 knowledge search
KNOWLEDGE_PATH_KEYWORDS = (
    "skills/", "wiki/", "Soul.md", "soul.md", "Memory.md", "memory.md",
    "recall/", "handler.md",
)

# 需要追踪的工具
TRACKED_TOOLS = {"Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebSearch"}


# --- 数据库初始化 ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    user_prompt TEXT,
    project_dir TEXT,
    observation_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_input_summary TEXT,
    tool_output_summary TEXT,
    file_path TEXT,
    project_dir TEXT,
    layer TEXT DEFAULT 'project',
    observation_type TEXT NOT NULL,
    compressed INTEGER DEFAULT 0,
    summary_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_obs_session ON observations(session_id);
CREATE INDEX IF NOT EXISTS idx_obs_type ON observations(observation_type);
CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON observations(timestamp);
CREATE INDEX IF NOT EXISTS idx_obs_file ON observations(file_path);
CREATE INDEX IF NOT EXISTS idx_obs_layer ON observations(layer);

CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
    tool_input_summary, tool_output_summary, file_path,
    content='observations', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS obs_ai AFTER INSERT ON observations BEGIN
    INSERT INTO observations_fts(rowid, tool_input_summary, tool_output_summary, file_path)
    VALUES (new.id, new.tool_input_summary, new.tool_output_summary, new.file_path);
END;
"""


def get_db_path() -> str:
    """确定数据库路径：优先 .agent-flow/，回退 .dev-workflow/"""
    for base in [DB_DIR_PROJECT, DB_DIR_DEV]:
        db_path = os.path.join(base, DB_FILENAME)
        if os.path.isdir(base):
            return db_path
    # 默认使用 .agent-flow/
    return os.path.join(DB_DIR_PROJECT, DB_FILENAME)


def get_connection(db_path: str) -> sqlite3.Connection:
    """获取 SQLite 连接，初始化 schema"""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# --- 工具函数 ---

def get_session_id() -> str:
    """获取当前会话 ID（从标记文件读取，或生成新的）"""
    # 检查项目级标记
    for base in [".agent-flow/state", ".dev-workflow/state"]:
        marker = os.path.join(base, ".current-session-id")
        if os.path.isfile(marker):
            try:
                return Path(marker).read_text(encoding="utf-8").strip()
            except Exception:
                pass

    # 检查全局标记
    global_marker = os.path.expanduser("~/.agent-flow/state/.current-session-id")
    if os.path.isfile(global_marker):
        try:
            return Path(global_marker).read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # 生成新会话 ID
    session_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    # 尝试写入标记
    for base in [".agent-flow/state", ".dev-workflow/state"]:
        marker = os.path.join(base, ".current-session-id")
        try:
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            Path(marker).write_text(session_id, encoding="utf-8")
            break
        except Exception:
            pass
    return session_id


def get_project_dir() -> str:
    """获取项目根目录"""
    return os.getcwd()


def determine_layer(file_path: str) -> str:
    """判断文件所属层级：global/project/dev"""
    if not file_path:
        return "project"
    abs_path = os.path.abspath(file_path)
    home = os.path.expanduser("~")
    if abs_path.startswith(os.path.join(home, ".agent-flow")):
        return "global"
    if ".dev-workflow" in abs_path:
        return "dev"
    return "project"


def infer_observation_type(tool_name: str, file_path: str, bash_command: str = "") -> str:
    """推断 observation 类型"""
    if tool_name in ("Write", "Edit"):
        return "write"

    if tool_name == "Bash":
        cmd = bash_command.strip().lower()
        # 安装命令
        install_keywords = ("pip ", "pip3 ", "npm ", "npm ", "brew ", "cargo ", "uv pip")
        for kw in install_keywords:
            if cmd.startswith(kw) or f" {kw}" in cmd:
                return "install"
        # 执行命令
        return "execute"

    if tool_name == "WebSearch":
        return "search"

    # Read/Glob/Grep — 判断是否是知识搜索
    if file_path:
        for kw in KNOWLEDGE_PATH_KEYWORDS:
            if kw in file_path:
                return "search"

    if tool_name in ("Grep", "Glob"):
        # 检查搜索路径是否包含知识路径
        return "search"

    if tool_name == "Read":
        return "read"

    return "read"


def is_noise(file_path: str, tool_name: str, bash_command: str = "") -> bool:
    """判断是否为噪声数据，应跳过"""
    if file_path:
        for prefix in NOISE_PATH_PREFIXES:
            if prefix in file_path:
                return True

    if tool_name == "Bash":
        cmd = bash_command.strip().split()[0] if bash_command.strip() else ""
        if cmd in NOISE_BASH_COMMANDS:
            return True

    return False


def extract_file_path(tool_name: str, tool_input: dict) -> str:
    """从工具输入中提取主文件路径"""
    if tool_name == "Read":
        return tool_input.get("file_path", "")
    elif tool_name in ("Write", "Edit"):
        return tool_input.get("file_path", "")
    elif tool_name == "Grep":
        return tool_input.get("path", "") or tool_input.get("glob", "")
    elif tool_name == "Glob":
        return tool_input.get("path", "")
    elif tool_name == "Bash":
        # 尝试从命令中提取文件路径
        cmd = tool_input.get("command", "")
        # 简单启发式：找最后一个看起来像文件路径的参数
        for part in reversed(cmd.split()):
            if "/" in part or part.endswith((".py", ".ts", ".js", ".md", ".yaml", ".json", ".toml")):
                return part.strip("\"'")
    return ""


def summarize_tool_input(tool_name: str, tool_input: dict) -> str:
    """生成工具输入的摘要"""
    if tool_name == "Read":
        return f"file_path={tool_input.get('file_path', '')}"
    elif tool_name in ("Write", "Edit"):
        fp = tool_input.get("file_path", "")
        # 对于 Edit，显示 old_string 的前 100 字符
        if tool_name == "Edit":
            old = tool_input.get("old_string", "")[:100]
            return f"file_path={fp} old_string={old}"
        return f"file_path={fp}"
    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "")
        return f"pattern={pattern} path={path}"
    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "")
        return f"pattern={pattern} path={path}"
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd[:MAX_INPUT_SUMMARY]
    elif tool_name == "WebSearch":
        return f"query={tool_input.get('query', '')}"
    return json.dumps(tool_input, ensure_ascii=False)[:MAX_INPUT_SUMMARY]


def summarize_tool_output(tool_output: str | None) -> str:
    """截断工具输出摘要"""
    if not tool_output:
        return ""
    return tool_output[:MAX_OUTPUT_SUMMARY]


# --- 主逻辑 ---

def main():
    # 读取输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_output = input_data.get("tool_output", "")

    # 只追踪指定工具
    if tool_name not in TRACKED_TOOLS:
        sys.exit(0)

    # 提取关键信息
    file_path = extract_file_path(tool_name, tool_input)
    bash_command = tool_input.get("command", "") if tool_name == "Bash" else ""

    # 噪声过滤
    if is_noise(file_path, tool_name, bash_command):
        sys.exit(0)

    # 确定类型和层级
    obs_type = infer_observation_type(tool_name, file_path, bash_command)
    layer = determine_layer(file_path)
    session_id = get_session_id()
    project_dir = get_project_dir()
    timestamp = datetime.now().isoformat()

    # 生成摘要
    input_summary = summarize_tool_input(tool_name, tool_input)
    output_summary = summarize_tool_output(tool_output)

    # 相对化文件路径
    if file_path and os.path.isabs(file_path):
        try:
            file_path = os.path.relpath(file_path, project_dir)
        except ValueError:
            pass  # 不同驱动器，保持绝对路径

    # 写入数据库
    try:
        db_path = get_db_path()
        conn = get_connection(db_path)

        # 确保 session 存在
        existing = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, started_at, project_dir) VALUES (?, ?, ?)",
                (session_id, timestamp, project_dir),
            )

        # 插入 observation
        conn.execute(
            """INSERT INTO observations
            (session_id, timestamp, tool_name, tool_input_summary, tool_output_summary,
             file_path, project_dir, layer, observation_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, timestamp, tool_name, input_summary, output_summary,
             file_path, project_dir, layer, obs_type),
        )

        # 更新 session 的 observation_count
        conn.execute(
            "UPDATE sessions SET observation_count = observation_count + 1 WHERE session_id = ?",
            (session_id,),
        )

        conn.commit()
        conn.close()
    except Exception:
        # 静默失败 — Hook 不应影响正常工作流
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
