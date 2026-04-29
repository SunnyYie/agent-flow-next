#!/usr/bin/env python3
"""
AgentFlow Promotion Guard — PreToolUse hook
拦截写入全局 agent-flow 知识库（wiki/skills）的操作，强制执行：
1. 相似内容检查：如果全局已有相似主题的文档，阻断新建并提示更新已有文档
2. 验收标记检查：写入全局必须先通过 promotion-verify 多Agent验收
   验收通过后会创建 .agent-flow/state/.promotion-verified 标记文件

仅在写入 ~/.agent-flow/wiki/ 和 ~/.agent-flow/skills/ 时生效。
"""
import json
import os
import re
import sys

# 全局 agent-flow 路径
GLOBAL_AGENT_FLOW = os.path.expanduser("~/.agent-flow")

# 需要守卫的全局子目录
GUARDED_SUBDIRS = ["wiki", "skills"]

# 需要守卫的项目级文档
PROJECT_GUARDED_FILES = [
    "project-structure.md",  # .agent-flow/wiki/ 下
    "Agent.md",  # .agent-flow/ 下
]

# 项目级文档验收标记文件
PROJECT_VERIFICATION_MARKER = ".agent-flow/state/.project-doc-verified"

# 验收标记文件
VERIFICATION_MARKER = ".agent-flow/state/.promotion-verified"

# 相似度阈值（文件名/标题关键词重叠比例）
SIMILARITY_THRESHOLD = 0.4


def is_guarded_path(file_path: str) -> bool:
    """判断文件路径是否在全局 agent-flow 的守卫目录下"""
    normalized = os.path.normpath(os.path.abspath(file_path))
    for subdir in GUARDED_SUBDIRS:
        guarded_prefix = os.path.normpath(os.path.join(GLOBAL_AGENT_FLOW, subdir))
        if normalized.startswith(guarded_prefix + os.sep) or normalized.startswith(
            guarded_prefix + "/"
        ):
            return True
    return False


def is_project_doc_path(file_path: str) -> bool:
    """判断是否为项目级受保护文档"""
    normalized = os.path.normpath(file_path)
    for guarded_name in PROJECT_GUARDED_FILES:
        if normalized.endswith(guarded_name):
            # 确认在 .agent-flow/ 下
            if ".agent-flow" in normalized:
                return True
    return False


def check_project_doc_verification(file_path: str) -> bool:
    """检查项目级文档验收标记"""
    if not os.path.isfile(PROJECT_VERIFICATION_MARKER):
        return False
    try:
        normalized = os.path.normpath(os.path.abspath(file_path))
        with open(PROJECT_VERIFICATION_MARKER, "r", encoding="utf-8") as f:
            for line in f:
                if os.path.normpath(os.path.abspath(line.strip())) == normalized:
                    return True
    except Exception:
        pass
    return False


def remove_project_doc_verified_path(file_path: str):
    """从项目级验收标记文件中移除已使用的路径"""
    if not os.path.isfile(PROJECT_VERIFICATION_MARKER):
        return
    try:
        normalized = os.path.normpath(os.path.abspath(file_path))
        with open(PROJECT_VERIFICATION_MARKER, "r", encoding="utf-8") as f:
            paths = [line.strip() for line in f if line.strip()]
        remaining = [
            p for p in paths if os.path.normpath(os.path.abspath(p)) != normalized
        ]
        with open(PROJECT_VERIFICATION_MARKER, "w", encoding="utf-8") as f:
            f.write("\n".join(remaining) + "\n" if remaining else "")
    except Exception:
        pass


def check_duplicate_tags(file_path: str, new_string: str) -> str:
    """检查新添加的标签行是否与已有内容重复

    Returns: 重复的标签描述，无重复返回空字符串
    """
    if not os.path.isfile(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            existing = f.read()
        # 提取新行中的标签名（第一个 | 之间的内容）
        new_tag = ""
        for part in new_string.split("|"):
            part = part.strip()
            if part and not part.startswith("-"):
                new_tag = part
                break
        if not new_tag:
            return ""
        # 检查已有内容中是否有相同标签
        for line in existing.split("\n"):
            if "|" in line and new_tag in line:
                # 确认是标签列匹配（不是子串匹配）
                line_parts = [p.strip() for p in line.split("|") if p.strip()]
                if line_parts and line_parts[0] == new_tag:
                    return new_tag
    except Exception:
        pass
    return ""


def extract_title_from_content(content: str) -> str:
    """从 Markdown 内容中提取标题（第一个 # 标题行）"""
    if not content:
        return ""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def extract_name_from_frontmatter(content: str) -> str:
    """从 YAML frontmatter 中提取 name 字段"""
    if not content or not content.startswith("---"):
        return ""
    match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return ""
    fm = match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
    if name_match:
        return name_match.group(1).strip()
    return ""


def extract_keywords(text: str) -> set:
    """从文本中提取有意义的关键词（去除停用词和短词）"""
    if not text:
        return set()
    # 去除标点和特殊字符，分词
    words = re.findall(r"[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}", text.lower())
    # 英文停用词
    stop_words = {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "how",
        "its",
        "let",
        "may",
        "new",
        "now",
        "old",
        "see",
        "way",
        "who",
        "did",
        "get",
        "got",
        "use",
        "used",
        "using",
        "this",
        "that",
        "with",
        "from",
        "they",
        "been",
        "have",
        "will",
        "each",
        "make",
        "like",
        "into",
        "them",
        "than",
        "then",
        "also",
        "more",
        "very",
        "much",
        "some",
        "when",
        "what",
        "which",
        "about",
        "would",
        "could",
        "should",
        "pattern",
        "pitfall",
        "concept",
        "workflow",
    }
    return {w for w in words if w not in stop_words}


def compute_similarity(keywords1: set, keywords2: set) -> float:
    """计算两组关键词的 Jaccard 相似度"""
    if not keywords1 or not keywords2:
        return 0.0
    intersection = keywords1 & keywords2
    union = keywords1 | keywords2
    return len(intersection) / len(union) if union else 0.0


def find_similar_files(
    target_dir: str, new_title: str, new_name: str, new_content: str
) -> list:
    """在目标目录中查找与新内容相似的已有文件

    返回: [(文件路径, 相似度, 标题/名称), ...] 按相似度降序
    """
    if not os.path.isdir(target_dir):
        return []

    new_keywords = extract_keywords(f"{new_title} {new_name}")
    if not new_keywords:
        # 退化为标题关键词
        new_keywords = extract_keywords(new_title) or extract_keywords(new_name)

    similar = []

    for root, dirs, files in os.walk(target_dir):
        # 跳过隐藏目录
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    existing_content = f.read()
            except Exception:
                continue

            existing_title = extract_title_from_content(existing_content)
            existing_name = extract_name_from_frontmatter(existing_content)

            # 文件名关键词
            fname_keywords = extract_keywords(
                fname.replace("-", " ").replace("_", " ").replace(".md", "")
            )

            # 合并已有文件的所有关键词
            existing_keywords = (
                extract_keywords(f"{existing_title} {existing_name}") | fname_keywords
            )

            sim = compute_similarity(new_keywords, existing_keywords)

            # 也检查标题的子串匹配
            if new_title and existing_title:
                # 标题完全包含
                if (
                    new_title.lower() in existing_title.lower()
                    or existing_title.lower() in new_title.lower()
                ):
                    sim = max(sim, 0.6)

            if sim >= SIMILARITY_THRESHOLD:
                display = existing_title or existing_name or fname
                similar.append((fpath, sim, display))

    similar.sort(key=lambda x: x[1], reverse=True)
    return similar


def check_verification_marker(target_path: str) -> bool:
    """检查验收标记文件中是否包含目标路径"""
    if not os.path.isfile(VERIFICATION_MARKER):
        return False
    try:
        with open(VERIFICATION_MARKER, "r", encoding="utf-8") as f:
            verified_paths = [line.strip() for line in f if line.strip()]
        normalized_target = os.path.normpath(os.path.abspath(target_path))
        for vp in verified_paths:
            if os.path.normpath(os.path.abspath(vp)) == normalized_target:
                return True
    except Exception:
        pass
    return False


def remove_verified_path(target_path: str):
    """从验收标记文件中移除已使用的路径"""
    if not os.path.isfile(VERIFICATION_MARKER):
        return
    try:
        with open(VERIFICATION_MARKER, "r", encoding="utf-8") as f:
            verified_paths = [line.strip() for line in f if line.strip()]
        normalized_target = os.path.normpath(os.path.abspath(target_path))
        remaining = [
            vp
            for vp in verified_paths
            if os.path.normpath(os.path.abspath(vp)) != normalized_target
        ]
        with open(VERIFICATION_MARKER, "w", encoding="utf-8") as f:
            f.write("\n".join(remaining) + "\n" if remaining else "")
    except Exception:
        pass


def is_new_file(file_path: str) -> bool:
    """判断目标文件是否为新建（文件不存在）"""
    return not os.path.isfile(file_path)


def main():
    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 只拦截 Write 和 Edit
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # 只拦截全局 agent-flow 的 wiki/ 和 skills/ 目录，或项目级受保护文档
    is_global = is_guarded_path(file_path)
    is_project = is_project_doc_path(file_path)

    if not is_global and not is_project:
        sys.exit(0)

    # === 项目级文档保护 ===
    if is_project:
        # 检查验收标记
        if check_project_doc_verification(file_path):
            remove_project_doc_verified_path(file_path)
            sys.exit(0)

        # 新建文件不阻断（由 agent-flow init 命令创建）
        if is_new_file(file_path):
            sys.exit(0)

        # 更新已有文件 → 检查标签重复
        if tool_name == "Edit":
            new_string = tool_input.get("new_string", "")
            # 如果是向标签表添加新行
            if "| " in new_string and " | " in new_string:
                duplicate = check_duplicate_tags(file_path, new_string)
                if duplicate:
                    print(
                        f"[AgentFlow BLOCKED] 向项目文档添加了重复标签！\n"
                        f"目标: {file_path}\n"
                        f"重复项: {duplicate}\n\n"
                        f"⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。\n\n"
                        f"✅ 解除方法：\n"
                        f"  先读取现有内容，确认标签不存在后再添加\n"
                        f"  如需重新生成完整索引: agent-flow init --force\n"
                        f"  完成后，当前操作会自动放行。"
                    )
                    sys.exit(2)

        # 非标签行的更新 → 软提醒
        print(
            f"[AgentFlow REMINDER] 正在更新项目级文档: {os.path.basename(file_path)}\n\n"
            f"如果是标签更新，请确认:\n"
            f"1. 标签不与已有条目重复\n"
            f"2. 目录路径正确\n"
            f"3. 更新后运行 agent-flow init --force 可重新生成"
        )
        sys.exit(0)

    # === 全局知识库保护 === (原有逻辑)

    # 检查验收标记
    if check_verification_marker(file_path):
        # 验收通过，放行并清除标记
        remove_verified_path(file_path)
        sys.exit(0)

    # 提取新内容信息
    content = ""
    if tool_name == "Write":
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        # Edit 没有完整内容，用文件路径提取信息
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                pass

    new_title = extract_title_from_content(content) if content else ""
    new_name = extract_name_from_frontmatter(content) if content else ""

    # 从文件路径提取名称作为 fallback
    if not new_title and not new_name:
        basename = (
            os.path.basename(file_path)
            .replace(".md", "")
            .replace("-", " ")
            .replace("_", " ")
        )
        new_title = basename
        new_name = basename

    # 确定搜索范围：整个 wiki/ 或 skills/ 目录（不仅限子目录）
    normalized_path = os.path.normpath(os.path.abspath(file_path))
    target_dir = None
    for subdir in GUARDED_SUBDIRS:
        guarded_prefix = os.path.normpath(os.path.join(GLOBAL_AGENT_FLOW, subdir))
        if normalized_path.startswith(
            guarded_prefix + os.sep
        ) or normalized_path.startswith(guarded_prefix + "/"):
            target_dir = guarded_prefix
            break
    if not target_dir:
        target_dir = os.path.dirname(file_path)

    # 如果是新建文件 → 检查相似内容
    if is_new_file(file_path):
        similar = find_similar_files(target_dir, new_title, new_name, content)

        if similar:
            top = similar[0]
            similar_list = "\n".join(
                f"  - {s[2]} (相似度: {s[1]:.0%}) → {s[0]}" for s in similar[:3]
            )
            print(
                f"[AgentFlow BLOCKED] 全局知识库中已有相似内容，禁止重复创建！\n"
                f"目标: {file_path}\n"
                f"新建标题: {new_title or new_name}\n\n"
                f"⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。\n\n"
                f"✅ 解除方法（任选其一）：\n"
                f"1. 更新已有文档（推荐）：Edit 已有文件，合并新内容\n"
                f"2. 如果确认是全新主题，先执行 promotion-verify Skill 获取验收标记\n"
                f"   启动 Verifier Agent 独立验收 → 通过后自动放行\n\n"
                f"已有相似文档:\n{similar_list}"
            )
            sys.exit(2)
        else:
            # 无相似内容但仍需验收
            print(
                f"[AgentFlow BLOCKED] 写入全局知识库需要先通过多Agent验收！\n"
                f"目标: {file_path}\n"
                f"新建标题: {new_title or new_name}\n\n"
                f"⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。\n\n"
                f"✅ 解除方法：\n"
                f"  执行 promotion-verify Skill\n"
                f"  1. 启动 Verifier Agent 独立审查内容（通用性+质量+去重）\n"
                f"  2. 验收通过后创建 .promotion-verified 标记\n"
                f"  完成后，当前操作会自动放行。"
            )
            sys.exit(2)
    else:
        # 更新已有文件 → 软提醒（不阻断，但建议验收）
        print(
            f"[AgentFlow REMINDER] 正在更新全局知识库文件:\n"
            f"目标: {file_path}\n\n"
            f"如果是重大内容变更，建议先执行 promotion-verify Skill 验收。\n"
            f"如果是小修小补（typo/格式），可直接更新。"
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
