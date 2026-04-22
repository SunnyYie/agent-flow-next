#!/usr/bin/env python3
"""
AgentFlow Session Starter — UserPromptSubmit hook
在用户发送新消息时，创建新的会话记录并写入标记文件。

与 observation-recorder.py 配合：
- 本 Hook 创建 session_id 并写入标记文件
- observation-recorder.py 读取标记文件获取当前 session_id
"""
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


# --- 配置 ---

DB_DIR_PROJECT = ".agent-flow"
DB_DIR_DEV = ".dev-workflow"
DB_FILENAME = "observations.db"

SESSION_MARKER_DIR = ".agent-flow/state"
SESSION_MARKER_ALT = ".dev-workflow/state"
SESSION_MARKER_FILENAME = ".current-session-id"

# 用户提示截断
MAX_PROMPT_LENGTH = 200

# Session schema（与 observation-recorder.py 共享）
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    user_prompt TEXT,
    project_dir TEXT,
    observation_count INTEGER DEFAULT 0
);
"""


def get_db_path() -> str:
    """确定数据库路径"""
    for base in [DB_DIR_PROJECT, DB_DIR_DEV]:
        if os.path.isdir(base):
            return os.path.join(base, DB_FILENAME)
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


def generate_session_id() -> str:
    """生成会话 ID：YYYY-MM-DD-HHMMSS 格式"""
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def write_session_marker(session_id: str) -> None:
    """将会话 ID 写入标记文件"""
    for marker_dir in [SESSION_MARKER_DIR, SESSION_MARKER_ALT]:
        try:
            os.makedirs(marker_dir, exist_ok=True)
            marker_path = os.path.join(marker_dir, SESSION_MARKER_FILENAME)
            Path(marker_path).write_text(session_id, encoding="utf-8")
        except Exception:
            pass


def end_previous_sessions(conn: sqlite3.Connection) -> None:
    """关闭之前未结束的会话"""
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE sessions SET ended_at = ?, status = 'completed' WHERE ended_at IS NULL",
        (now,),
    )
    conn.commit()


def main():
    # 读取输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    # 提取用户消息
    user_prompt = input_data.get("prompt", "")
    if isinstance(user_prompt, str):
        user_prompt = user_prompt[:MAX_PROMPT_LENGTH]
    else:
        user_prompt = str(user_prompt)[:MAX_PROMPT_LENGTH]

    # 生成新会话 ID
    session_id = generate_session_id()
    timestamp = datetime.now().isoformat()
    project_dir = os.getcwd()

    # 写入数据库
    try:
        db_path = get_db_path()
        conn = get_connection(db_path)

        # 关闭之前的未结束会话
        end_previous_sessions(conn)

        # 创建新会话
        conn.execute(
            "INSERT INTO sessions (session_id, started_at, user_prompt, project_dir) VALUES (?, ?, ?, ?)",
            (session_id, timestamp, user_prompt, project_dir),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    # 写入标记文件供 observation-recorder.py 读取
    write_session_marker(session_id)

    sys.exit(0)


if __name__ == "__main__":
    main()
