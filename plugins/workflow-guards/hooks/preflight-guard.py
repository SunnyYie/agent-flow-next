#!/usr/bin/env python3
"""
AgentFlow Pre-Flight Guard — UserPromptSubmit hook
在用户提交 prompt 时，检查是否需要执行 pre-flight-check。
如果 .agent-flow/ 存在但 pre-flight 未完成，注入强制协议指令。
无论 pre-flight 是否完成，都注入开发铁律提醒。
"""
import os
import sys

DEV_IRON_LAWS = """
【开发铁律】违反将被 Hook 拦截：
1. 修改代码前必须先创建 feature 分支（禁止在 main 上开发）
2. 修改代码前必须先创建实施计划文档（requirement-decomposition.md 或 ## 实施计划 章节）
3. 遇到错误禁止自行推测，必须搜索 Skill/Wiki 或询问用户
4. 执行 MR 等操作前必须先搜索相关 Skill 并按 Procedure 执行
5. 任务开始前必须执行 pre-flight-check Step 2 进行 5 维量化评估（无 .complexity-level 标记 → 代码修改被阻断）
6. VERIFY 后、REFLECT 前必须执行 self-questioning skill（无 .self-questioning-done 标记 → REFLECT 被阻断）

【思维链】执行每个子任务的硬性要求（无搜索标记 → Hook 阻断执行）：
  思考 → 搜索解决方案 → 确认方案 → 执行 → 验证 → 未解决则继续思考"""


def check_stale_acceptance_marker():
    """检查用户验收标记是否属于当前任务，如果不是则清除过时标记"""
    marker = ".agent-flow/state/.user-acceptance-done"
    if not os.path.isfile(marker):
        return
    phase_file = ".agent-flow/state/current_phase.md"
    if not os.path.isfile(phase_file):
        return
    try:
        marker_task = ""
        with open(marker, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("task="):
                    marker_task = line.strip().split("=", 1)[1]
        current_task = ""
        with open(phase_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("# 任务:") or line.strip().startswith(
                    "# Task:"
                ):
                    current_task = line.strip().lstrip("# ").strip()
        # 如果标记中的任务与当前任务不匹配，删除过时标记
        if marker_task and current_task and marker_task != current_task:
            os.remove(marker)
    except Exception:
        pass


def main():
    # 只在配置了 agent-flow 的项目中生效
    has_agent_flow = os.path.isdir(".agent-flow")

    if not has_agent_flow:
        # No agent-flow: suggest initialization
        print(
            f"""<system-reminder>
[AgentFlow] 检测到当前项目未初始化 agent-flow。

为了让你更高效地理解项目和工作，建议执行初始化：

1. 运行命令: agent-flow init
2. 初始化完成后，按 Agent.md 启动协议工作

初始化将自动：
- 检测项目技术栈和目录结构
- 生成 Tag → Directory 索引（帮助快速定位代码）
- 创建项目配置和工作流文件

如果不想初始化，可忽略此提示继续工作。
</system-reminder>"""
        )
        sys.exit(0)

    # 清除过时的验收标记（任务变更时）
    check_stale_acceptance_marker()

    # Detect incomplete initialization
    incomplete_issues = []
    if has_agent_flow:
        config_path = ".agent-flow/config.yaml"
        if not os.path.isfile(config_path) or os.path.getsize(config_path) < 10:
            incomplete_issues.append("config.yaml 缺失或为空")

    # Output incomplete initialization warning
    incomplete_warning = ""
    if incomplete_issues:
        issues_str = "\n".join(f"  - {issue}" for issue in incomplete_issues)
        incomplete_warning = (
            f"\n\n[AgentFlow WARNING] 项目初始化不完整，以下文件缺失:\n"
            f"{issues_str}\n"
            f"建议运行: agent-flow init --force\n"
            f"补全缺失文件后，按启动协议工作。"
        )

    # 检查 pre-flight 是否已完成（current_phase.md 非空即为已规划）
    phase_file = ".agent-flow/state/current_phase.md"
    preflight_done = (
        os.path.isfile(phase_file) and os.path.getsize(phase_file) > 10  # 非空文件
    )

    if preflight_done:
        # 已完成 pre-flight，检查上一个任务的自我质询是否完成
        sq_marker = ".agent-flow/state/.self-questioning-done"
        sq_warning = ""
        if not os.path.isfile(sq_marker):
            sq_warning = "\n\n[AgentFlow WARNING] 上一个任务的自我质询(self-questioning)未完成！\n请先补做 self-questioning，创建 .self-questioning-done 标记后再开始新任务。"

        # 检查复杂度评估是否完成
        complexity_marker = ".agent-flow/state/.complexity-level"
        complexity_warning = ""
        if not os.path.isfile(complexity_marker):
            complexity_warning = "\n\n[AgentFlow WARNING] 当前任务的复杂度评估(complexity-level)未完成！\n请先执行 pre-flight-check Step 2，创建 .complexity-level 标记后再修改代码。"

        # 检查需求澄清标记（v3.0 新增）
        clarified_marker = ".agent-flow/state/.requirement-clarified"
        clarified_warning = ""
        if not os.path.isfile(clarified_marker):
            clarified_warning = "\n\n[AgentFlow WARNING] 需求深度澄清(.requirement-clarified)未完成！\n请先执行 requirement-decomposition Phase 3.5 深度澄清，穷举假设、追问边界场景后再修改代码。"

        # 检查设计决策确认标记（v3.0 新增）
        design_marker = ".agent-flow/state/.design-confirmed"
        design_warning = ""
        if not os.path.isfile(design_marker):
            design_warning = "\n\n[AgentFlow WARNING] 设计决策确认(.design-confirmed)未完成！\n请先执行 requirement-decomposition Phase 5.5 设计决策检查点，确认修改方式、影响范围、实施策略和回滚方案。"

        # 检查用户验收标记（v3.0 新增）
        acceptance_marker = ".agent-flow/state/.user-acceptance-done"
        acceptance_warning = ""
        if not os.path.isfile(acceptance_marker):
            acceptance_warning = "\n\n[AgentFlow REMINDER] 用户验收(.user-acceptance-done)未完成。\n推送代码前必须获得用户验收确认（Medium/Complex 任务 hook 强制执行）。"

        # 注入开发铁律提醒
        print(
            f"[AgentFlow] Pre-flight 已完成。{DEV_IRON_LAWS}\n每个子任务前执行 subtask-guard 搜索知识库。{sq_warning}{complexity_warning}{clarified_warning}{design_warning}{acceptance_warning}{incomplete_warning}"
        )
        sys.exit(0)

    # === Pre-flight 未完成 === 强制注入协议指令

    preflight_steps = f"""<system-reminder>
[AgentFlow Protocol — MANDATORY] PRE-FLIGHT CHECK 未完成，你必须先完成以下步骤才能执行任何任务：

【禁止跳过】按顺序执行：
1. 读取 ~/.agent-flow/skills/workflow/pre-flight-check/handler.md，按其 5 步 Procedure 执行
2. Step 1: 检查项目配置（.agent-flow/config.yaml）
3. Step 2: 知识检索（5 次搜索：项目技能→全局技能→Soul→项目Wiki→全局Wiki）
4. Step 3: 将分析写入 .agent-flow/memory/main/Memory.md
5. Step 4: 将计划写入 .agent-flow/state/current_phase.md
6. Step 5: 向用户展示计划摘要，等待用户确认

违规行为（将被 Hook 拦截）：
- 未完成 5 步就开始写代码或执行命令
- 不搜索 Skill/Soul/Wiki 就执行子任务
- 用户未确认就开始执行

{DEV_IRON_LAWS}{incomplete_warning}
</system-reminder>"""

    print(preflight_steps)

    sys.exit(0)


if __name__ == "__main__":
    main()
