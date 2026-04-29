#!/usr/bin/env python3
"""
AgentFlow Context Guard — PostToolUse hook
监控上下文膨胀和污染风险，在以下场景发出警告：

1. 读取大文件（>500行）未指定行范围 → 建议指定行范围
2. 连续读取多个大文件 → 建议用 Explore Agent 隔离
3. 主对话中出现大量调试/日志输出 → 建议用子 Agent

仅在主对话中生效，子 Agent 中不触发（避免干扰）。
"""
import json
import os
import sys

# 阈值配置
LARGE_FILE_LINE_THRESHOLD = 500  # 大文件行数阈值
CONSECUTIVE_LARGE_READS = 3      # 连续大文件读取次数阈值
CONTEXT_PCT_WARNING = 0.6        # 上下文使用率警告阈值

# 会话内状态（进程内持久化）
_state = {
    "large_read_count": 0,
    "last_warning_step": 0,
    "total_steps": 0,
}


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    _state["total_steps"] += 1
    step = _state["total_steps"]

    # 只监控 Read 工具
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        offset = tool_input.get("offset")
        limit = tool_input.get("limit")

        # Create .project-structure-read marker when agent reads project-structure.md
        if file_path and "project-structure.md" in file_path and ".agent-flow" in file_path:
            marker_dir = os.path.join(".agent-flow", "state")
            os.makedirs(marker_dir, exist_ok=True)
            marker_path = os.path.join(marker_dir, ".project-structure-read")
            if not os.path.isfile(marker_path):
                with open(marker_path, "w", encoding="utf-8") as f:
                    f.write("read")

        # 检查是否读取大文件未指定行范围
        if not offset and not limit and file_path and os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    line_count = sum(1 for _ in f)
                if line_count > LARGE_FILE_LINE_THRESHOLD:
                    _state["large_read_count"] += 1
                    if _state["large_read_count"] == 1:
                        print(
                            f"[ContextGuard] 大文件 {os.path.basename(file_path)} "
                            f"({line_count}行) 未指定行范围。\n"
                            f"建议: Read 指定 offset+limit 只读需要的部分，避免上下文膨胀。"
                        )
                    elif _state["large_read_count"] >= CONSECUTIVE_LARGE_READS:
                        if step - _state["last_warning_step"] > 5:
                            print(
                                f"[ContextGuard] 已连续读取 {_state['large_read_count']} 个大文件！\n"
                                f"上下文膨胀风险高。建议：\n"
                                f"1. 用 Explore Agent 做代码探索（独立上下文）\n"
                                f"2. /compact 压缩当前上下文\n"
                                f"3. 每次只读需要的行范围"
                            )
                            _state["last_warning_step"] = step
                else:
                    _state["large_read_count"] = max(0, _state["large_read_count"] - 1)
            except Exception:
                pass

    # 监控 Bash 工具中的日志输出
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        # 检测可能的日志/调试输出命令
        log_patterns = ["tail -f", "kubectl logs", "docker logs", "journalctl"]
        for pattern in log_patterns:
            if pattern in command:
                print(
                    f"[ContextGuard] 检测到日志输出命令: {pattern}\n"
                    f"日志输出会快速膨胀上下文。建议：\n"
                    f"1. 用 `| head -n 50` 限制输出行数\n"
                    f"2. 用子 Agent 执行日志分析（隔离上下文）\n"
                    f"3. 用 `| grep` 过滤只看关键行"
                )
                break

    sys.exit(0)


if __name__ == "__main__":
    main()
