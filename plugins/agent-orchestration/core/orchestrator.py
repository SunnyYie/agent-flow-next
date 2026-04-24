"""FlexibleOrchestrator — 编排者-工作者模式的核心实现。

参考: https://github.com/anthropics/claude-cookbooks/blob/main/patterns/agents/orchestrator_workers.ipynb

两阶段工作流:
  Phase 1: 分析 & 计划 — 编排者分析任务，生成结构化子任务
  Phase 2: 执行 — 工作者并行/串行执行子任务
  Phase 3: 聚合 — 合并工作者结果，返回结构化输出
"""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent_flow.core.structured_state import (
    OrchestratorOutput,
    TaskState,
    WorkerResultState,
    WorkerResultStatus,
)


def extract_xml(text: str, tag: str) -> str:
    """从文本中提取 XML 标签内容。LLM 友好的解析方式。"""
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_tasks(tasks_xml: str) -> list[TaskState]:
    """解析编排者输出的 XML 任务列表为结构化对象。

    支持两种格式:
    1. 多行格式（LLM 典型输出）：每个标签独占一行
    2. 内联格式：所有标签在同一行
    """
    tasks: list[TaskState] = []

    # 策略1：正则匹配（支持多行和内联格式）
    task_matches = re.findall(
        r"<task>\s*<type>(.*?)</type>\s*<description>(.*?)</description>\s*</task>",
        tasks_xml,
        re.DOTALL,
    )
    if task_matches:
        for task_type, description in task_matches:
            tasks.append(
                TaskState(
                    task_id=f"task-{task_type.strip()}",
                    task_type=task_type.strip() or "default",
                    description=description.strip(),
                )
            )
        return tasks

    # 策略2：逐行解析（兼容 cookbooks 原始实现）
    current: dict[str, str] = {}
    for line in tasks_xml.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("<task>"):
            current = {}
        elif line.startswith("<type>"):
            current["type"] = line[6:-7].strip()
        elif line.startswith("<description>"):
            current["description"] = line[12:-13].strip()
        elif line.startswith("</task>"):
            if "description" in current:
                if "type" not in current:
                    current["type"] = "default"
                tasks.append(
                    TaskState(
                        task_id=f"task-{current['type']}",
                        task_type=current["type"],
                        description=current["description"],
                    )
                )

    return tasks


class FlexibleOrchestrator:
    """编排者-工作者模式的核心实现。

    编排者动态分析任务并生成子任务列表，工作者执行各自子任务，
    最终聚合为结构化结果。

    用法:
        orchestrator = FlexibleOrchestrator(
            orchestrator_prompt=ORCHESTRATOR_PROMPT,
            worker_prompt=WORKER_PROMPT,
            llm_call=my_llm_call_fn,
        )
        result = orchestrator.process("Write docs for feature X")
    """

    def __init__(
        self,
        orchestrator_prompt: str,
        worker_prompt: str,
        llm_call: Callable[[str, str], str],
        max_workers: int = 3,
        on_worker_start: Callable[[TaskState], None] | None = None,
        on_worker_complete: Callable[[TaskState, WorkerResultState], None] | None = None,
    ) -> None:
        """初始化编排者。

        Args:
            orchestrator_prompt: 编排者提示词模板，支持 {task} 和 {context} 变量。
            worker_prompt: 工作者提示词模板，支持 {original_task}, {task_type}, {task_description} 变量。
            llm_call: LLM 调用函数，签名 (prompt, system_prompt) -> response_text。
            max_workers: 并行工作者的最大数量。
        """
        self.orchestrator_prompt = orchestrator_prompt
        self.worker_prompt = worker_prompt
        self.llm_call = llm_call
        self.max_workers = max_workers
        self.on_worker_start = on_worker_start
        self.on_worker_complete = on_worker_complete

    def _format_prompt(self, template: str, **kwargs: str) -> str:
        """格式化提示词模板。"""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required prompt variable: {e}") from e

    def _run_worker(self, task: str, task_def: TaskState, context: dict[str, str]) -> WorkerResultState:
        """执行单个工作者任务。"""
        worker_id = f"worker-{task_def.task_type}"
        if self.on_worker_start is not None:
            self.on_worker_start(task_def)

        try:
            worker_input = self._format_prompt(
                self.worker_prompt,
                original_task=task,
                task_type=task_def.task_type,
                task_description=task_def.description,
                **context,
            )

            worker_response = self.llm_call(worker_input, "")
            worker_content = extract_xml(worker_response, "response")

            # 输出验证 — 空值兜底
            if not worker_content or not worker_content.strip():
                result = WorkerResultState(
                    worker_id=worker_id,
                    task_type=task_def.task_type,
                    description=task_def.description,
                    result=f"[Error: Worker '{task_def.task_type}' failed to generate content]",
                    status=WorkerResultStatus.FAILED,
                )
                if self.on_worker_complete is not None:
                    self.on_worker_complete(task_def, result)
                return result

            result = WorkerResultState(
                worker_id=worker_id,
                task_type=task_def.task_type,
                description=task_def.description,
                result=worker_content,
                status=WorkerResultStatus.SUCCESS,
            )
            if self.on_worker_complete is not None:
                self.on_worker_complete(task_def, result)
            return result
        except Exception as e:
            result = WorkerResultState(
                worker_id=worker_id,
                task_type=task_def.task_type,
                description=task_def.description,
                result=f"[Error: {e}]",
                status=WorkerResultStatus.FAILED,
            )
            if self.on_worker_complete is not None:
                self.on_worker_complete(task_def, result)
            return result

    def process(self, task: str, context: dict[str, str] | None = None) -> OrchestratorOutput:
        """处理任务：编排分析 → 工作者执行 → 结果聚合。

        Args:
            task: 原始任务描述。
            context: 额外上下文变量（如 target_audience, key_features 等）。

        Returns:
            OrchestratorOutput 包含分析、工作者结果和元数据。
        """
        context = context or {}

        # Phase 1: 编排者分析 & 计划
        orchestrator_input = self._format_prompt(self.orchestrator_prompt, task=task, **context)
        orchestrator_response = self.llm_call(orchestrator_input, "")

        analysis = extract_xml(orchestrator_response, "analysis")
        tasks_xml = extract_xml(orchestrator_response, "tasks")
        task_defs = parse_tasks(tasks_xml)

        if not task_defs:
            return OrchestratorOutput(
                analysis=analysis or "No analysis produced.",
                metadata={"error": "No tasks parsed from orchestrator output"},
            )

        # Phase 2: 工作者执行（并行）
        worker_results: list[WorkerResultState] = []

        if len(task_defs) == 1 or self.max_workers <= 1:
            # 串行执行
            for td in task_defs:
                result = self._run_worker(task, td, context)
                worker_results.append(result)
        else:
            # 并行执行
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(task_defs))) as executor:
                futures = {
                    executor.submit(self._run_worker, task, td, context): td
                    for td in task_defs
                }
                for future in as_completed(futures):
                    worker_results.append(future.result())

        # Phase 3: 结果聚合
        # 按原始任务顺序排序
        type_order = {td.task_type: i for i, td in enumerate(task_defs)}
        worker_results.sort(key=lambda r: type_order.get(r.task_type, 999))

        return OrchestratorOutput(
            analysis=analysis,
            tasks=task_defs,
            worker_results=worker_results,
            metadata={
                "total_tasks": len(task_defs),
                "successful": sum(1 for r in worker_results if r.status == WorkerResultStatus.SUCCESS),
                "failed": sum(1 for r in worker_results if r.status == WorkerResultStatus.FAILED),
            },
        )


# ── 标准提示词模板 ──────────────────────────────────────────

ORCHESTRATOR_PROMPT = """\
Analyze this task and break it down into 2-3 distinct approaches:

Task: {task}

Return your response in this format:

<analysis>
Explain your understanding of the task and which variations would be valuable.
Focus on how each approach serves different aspects of the task.
</analysis>

<tasks>
    <task>
    <type>approach_name</type>
    <description>What this approach should focus on and produce</description>
    </task>
</tasks>
"""

WORKER_PROMPT = """\
Generate content based on:
Task: {original_task}
Style: {task_type}
Guidelines: {task_description}

Return your response in this format:

<response>
Your content here, maintaining the specified style and fully addressing requirements.
</response>
"""
