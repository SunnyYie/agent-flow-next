"""Task runner — execution loop with dual verification, retry, and recovery.

Manages the per-task execution cycle: run → verify → commit/rollback.
Supports interruption recovery via pipeline state persistence.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agent_flow.core.pipeline_state import (
    PipelineManager,
    PipelineState,
    StageStatus,
    TaskState,
    TaskComplexity,
)


class TaskResult:
    """Result of a single task execution."""

    def __init__(
        self,
        task_id: int,
        success: bool,
        files_modified: list[str] | None = None,
        test_results: str = "",
        verification_passed: bool = False,
        error: str = "",
    ) -> None:
        self.task_id = task_id
        self.success = success
        self.files_modified = files_modified or []
        self.test_results = test_results
        self.verification_passed = verification_passed
        self.error = error


class TaskRunner:
    """Manages the task execution loop within the /run pipeline stage."""

    def __init__(
        self,
        project_dir: Path,
        pipeline: PipelineManager,
        max_retries: int = 3,
    ) -> None:
        self.project_dir = project_dir
        self.pipeline = pipeline
        self.max_retries = max_retries
        self.run_log_path = pipeline.pipeline_dir / "run-log.md"

    def get_next_task(self) -> TaskState | None:
        state = self.pipeline.load_state()
        completed_ids = {t.id for t in state.tasks if t.status == StageStatus.COMPLETED}
        for task in state.tasks:
            if task.status != StageStatus.PENDING:
                continue
            if all(dep in completed_ids for dep in task.dependencies):
                return task
        return None

    def get_ready_tasks(self, max_count: int = 3) -> list[TaskState]:
        state = self.pipeline.load_state()
        completed_ids = {t.id for t in state.tasks if t.status == StageStatus.COMPLETED}
        ready = []
        for task in state.tasks:
            if task.status != StageStatus.PENDING:
                continue
            if all(dep in completed_ids for dep in task.dependencies):
                ready.append(task)
                if len(ready) >= max_count:
                    break
        return sorted(ready, key=lambda t: t.id)

    def start_tasks_batch(self, tasks: list[TaskState]) -> None:
        for task in tasks:
            self.pipeline.update_task(task.id, status=StageStatus.IN_PROGRESS)
        task_ids = ", ".join(str(t.id) for t in tasks)
        self._append_run_log(f"## Batch: Tasks {task_ids}\n\n**Status**: in_progress (parallel)\n")

    def start_task(self, task: TaskState) -> None:
        self.pipeline.update_task(task.id, status=StageStatus.IN_PROGRESS)
        self._append_run_log(f"## Task {task.id}: {task.title}\n\n**Status**: in_progress\n")

    def complete_task(self, task: TaskState, result: TaskResult) -> None:
        self.pipeline.update_task(
            task.id,
            status=StageStatus.COMPLETED,
            verified=result.verification_passed,
            commit_sha=_get_head_commit(self.project_dir),
        )
        log_entry = (
            f"**Status**: completed\n"
            f"**Files modified**: {', '.join(result.files_modified) or 'none'}\n"
            f"**Verification**: {'PASS' if result.verification_passed else 'FAIL (overridden)'}\n"
        )
        self._append_run_log(log_entry)

    def fail_task(self, task: TaskState, result: TaskResult) -> None:
        retry_count = task.retry_count + 1
        self.pipeline.update_task(task.id, status=StageStatus.FAILED, retry_count=retry_count)
        log_entry = (
            f"**Status**: failed (retry {retry_count}/{self.max_retries})\n"
            f"**Error**: {result.error}\n"
        )
        self._append_run_log(log_entry)

    def reset_task_for_retry(self, task: TaskState) -> None:
        self.pipeline.update_task(task.id, status=StageStatus.PENDING)

    def should_retry(self, task: TaskState) -> bool:
        return task.retry_count < self.max_retries

    def generate_executor_prompt(self, task: TaskState, state: PipelineState) -> str:
        return f"""# Executor Agent — Task {task.id}: {task.title}

## Task Description
{task.description}

## Files to Create/Modify
{chr(10).join(f'- `{f}`' for f in task.files) if task.files else '(to be determined by executor)'}

## Test Criteria
{chr(10).join(f'- {c}' for c in task.test_criteria) if task.test_criteria else '(to be defined)'}

## Complexity
{task.complexity.value}

## Dependencies
{', '.join(f'Task {d}' for d in task.dependencies) if task.dependencies else 'None'}

## Pipeline Context
- Feature: {state.feature_name}
- Branch: {state.branch}
- Base branch: {state.base_branch}

## Rules
1. Implement ONLY what is specified — no scope creep
2. Search .agent-flow/skills/ and ~/.agent-flow/skills/ for relevant skills before implementing
3. Record your execution process to .agent-flow/memory/main/Memory.md
4. After implementation, run relevant tests
5. Report: list all files created/modified and test results

## Report Format
### Files Modified
- `path/to/file.py` — (what changed)

### Test Results
- (test output or "no tests run")

### Issues Encountered
- (any problems or blockers)
"""

    def generate_verifier_prompt(self, task: TaskState, result: TaskResult) -> str:
        test_criteria_text = "\n".join(
            f"- [ ] {c}" for c in task.test_criteria
        ) if task.test_criteria else "(no test criteria defined)"

        return f"""# Verifier Agent — Task {task.id}: {task.title}

## Verification Checklist

### Test Criteria
{test_criteria_text}

### Code Quality
- [ ] No obvious bugs or logic errors
- [ ] No security vulnerabilities (OWASP Top 10)
- [ ] Error handling is appropriate
- [ ] Code follows project conventions

### Files Modified
{chr(10).join(f'- `{f}`' for f in result.files_modified) if result.files_modified else '(none reported)'}

### Test Results
```
{result.test_results or '(no test results provided)'}
```

## Verification Rules
1. You must verify INDEPENDENTLY — do not trust the executor's self-assessment
2. Each criterion is either PASS or FAIL — no partial passes
3. Provide concrete evidence for each judgment
4. If any CRITICAL criterion fails, the task FAILS

## Report Format
### Criterion Results
- [criterion]: PASS/FAIL — (evidence)

### Verdict
VERDICT: PASS / FAIL

### Issues (if any)
- (description of issues found)
"""

    def generate_parallel_executor_prompt(
        self,
        task: TaskState,
        state: PipelineState,
        executor_name: str,
        owned_files: list[str],
        shared_context_path: str,
    ) -> str:
        base_prompt = self.generate_executor_prompt(task, state)
        ownership_section = f"""
## Parallel Execution Rules
- You are executor **{executor_name}**
- You may ONLY modify these files: {', '.join(f'`{f}`' for f in owned_files) if owned_files else '(files listed in task)'}
- NEVER modify files not in your ownership list — raise an issue instead
- Shared context: {shared_context_path}
- Write your summary to: .agent-flow/artifacts/task-{task.id}-summary.md
"""
        return base_prompt + ownership_section

    def write_shared_context(
        self,
        state: PipelineState,
        ready_tasks: list[TaskState],
        search_artifact_path: str = "",
    ) -> Path:
        shared_path = self.project_dir / ".agent-flow" / "state" / "shared-context.md"
        completed = [t for t in state.tasks if t.status == StageStatus.COMPLETED]
        completed_l1 = "\n".join(f"- Task {t.id}: {t.title} (done)" for t in completed) or "(none yet)"
        ready_l1 = "\n".join(f"- Task {t.id}: {t.title} (current batch)" for t in ready_tasks)
        content = f"""# Shared Execution Context

## Completed Tasks (L1)
{completed_l1}

## Current Batch
{ready_l1}

## Search Results
{f"See: {search_artifact_path}" if search_artifact_path else "(no search results)"}

## Rules
- Read this file for context about completed tasks
- Write your L2 summary to .agent-flow/artifacts/task-{{id}}-summary.md
- Do NOT modify files outside your ownership list
"""
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_text(content, encoding="utf-8")
        return shared_path

    def generate_run_summary(self) -> str:
        state = self.pipeline.load_state()
        if not state.tasks:
            return "No tasks in pipeline."
        completed = [t for t in state.tasks if t.status == StageStatus.COMPLETED]
        in_progress = [t for t in state.tasks if t.status == StageStatus.IN_PROGRESS]
        failed = [t for t in state.tasks if t.status == StageStatus.FAILED]
        pending = [t for t in state.tasks if t.status == StageStatus.PENDING]
        lines = [
            f"# Run Summary — {state.feature_name}",
            "",
            f"**Branch**: {state.branch}",
            f"**Total tasks**: {len(state.tasks)}",
            f"**Completed**: {len(completed)}",
            f"**In Progress**: {len(in_progress)}",
            f"**Failed**: {len(failed)}",
            f"**Pending**: {len(pending)}",
            "",
        ]
        if completed:
            lines.append("## Completed Tasks")
            for t in completed:
                lines.append(f"- Task {t.id}: {t.title} (verified: {t.verified})")
            lines.append("")
        if in_progress:
            lines.append("## In Progress")
            for t in in_progress:
                lines.append(f"- Task {t.id}: {t.title}")
            lines.append("")
        if failed:
            lines.append("## Failed Tasks")
            for t in failed:
                lines.append(f"- Task {t.id}: {t.title} (retries: {t.retry_count})")
            lines.append("")
        if pending:
            lines.append("## Pending Tasks")
            for t in pending:
                lines.append(f"- Task {t.id}: {t.title} (depends on: {t.dependencies})")
            lines.append("")
        return "\n".join(lines)

    def parse_tasks_from_eng_review(self, eng_review_path: Path) -> list[TaskState]:
        if not eng_review_path.is_file():
            return []
        content = eng_review_path.read_text(encoding="utf-8")
        tasks: list[TaskState] = []

        # Strategy 1: YAML task blocks
        in_yaml_block = False
        yaml_content = ""
        for line in content.splitlines():
            if line.strip() == "```yaml" and "tasks:" in content[content.find(line):content.find(line) + 200]:
                in_yaml_block = True
                yaml_content = ""
                continue
            if in_yaml_block:
                if line.strip() == "```":
                    in_yaml_block = False
                    try:
                        data = yaml.safe_load(yaml_content)
                        if isinstance(data, dict) and "tasks" in data:
                            for task_data in data["tasks"]:
                                task = TaskState(
                                    id=task_data.get("id", len(tasks) + 1),
                                    title=task_data.get("title", ""),
                                    description=task_data.get("description", ""),
                                    files=task_data.get("files", []),
                                    dependencies=task_data.get("dependencies", []),
                                    test_criteria=task_data.get("test_criteria", []),
                                    complexity=TaskComplexity(task_data.get("complexity", "medium")),
                                    phase=task_data.get("phase", 1),
                                )
                                tasks.append(task)
                    except yaml.YAMLError:
                        pass
                    continue
                yaml_content += line + "\n"

        if tasks:
            return tasks

        # Strategy 2: Markdown task sections
        import re
        task_pattern = re.compile(r"^####\s+T(\d+)\.(\d+)\s+(.+)$")
        impl_pattern = re.compile(r"^- \*\*实现内容\*\*[：:]\s*(.*)$")
        impl_detail_pattern = re.compile(r"^\s+-\s+(.+)$")
        criteria_pattern = re.compile(r"^- \*\*完成标志\*\*[：:]\s*(.+)$")
        test_pattern = re.compile(r"^- \*\*测试方法\*\*[：:]\s*(.+)$")
        dep_pattern = re.compile(r"^- \*\*依赖\*\*[：:]\s*(.+)$")

        current_task: dict[str, Any] | None = None
        current_field: str | None = None

        for line in content.splitlines():
            m = task_pattern.match(line)
            if m:
                if current_task is not None:
                    tasks.append(TaskState(
                        id=current_task.get("id", len(tasks) + 1),
                        title=current_task.get("title", ""),
                        description=current_task.get("description", ""),
                        files=current_task.get("files", []),
                        dependencies=current_task.get("dependencies", []),
                        test_criteria=current_task.get("test_criteria", []),
                        complexity=TaskComplexity(current_task.get("complexity", "medium")),
                        phase=current_task.get("phase", 1),
                    ))
                phase = int(m.group(1))
                seq = int(m.group(2))
                title = m.group(3).strip()
                task_id = phase * 10 + seq
                current_task = {
                    "id": task_id,
                    "title": title,
                    "description": "",
                    "files": [],
                    "dependencies": [],
                    "test_criteria": [],
                    "complexity": "medium",
                    "phase": phase,
                }
                current_field = None
                continue

            if current_task is None:
                continue

            m = impl_pattern.match(line)
            if m:
                current_field = "impl"
                impl_text = m.group(1).strip()
                if impl_text:
                    current_task["description"] += impl_text
                continue

            m = criteria_pattern.match(line)
            if m:
                current_field = "criteria"
                criteria_text = m.group(1).strip()
                if criteria_text:
                    current_task["test_criteria"].append(criteria_text)
                continue

            m = test_pattern.match(line)
            if m:
                current_field = "test"
                test_text = m.group(1).strip()
                if test_text:
                    current_task["test_criteria"].append(test_text)
                continue

            m = dep_pattern.match(line)
            if m:
                current_field = "dep"
                dep_text = m.group(1).strip()
                if dep_text and dep_text != "无":
                    dep_refs = re.findall(r"T(\d+)\.(\d+)", dep_text)
                    current_task["dependencies"] = [int(p) * 10 + int(s) for p, s in dep_refs]
                continue

            m = impl_detail_pattern.match(line)
            if m and current_field == "impl":
                detail = m.group(1).strip()
                if detail:
                    current_task["description"] += "；" + detail
                file_refs = re.findall(r"[\w/.-]+\.(ts|tsx|js|jsx|py|rs|go|java|vue|css|scss)", detail)
                current_task["files"].extend(file_refs)
                continue

            if line.strip() and not line.startswith(" "):
                current_field = None

        if current_task is not None:
            tasks.append(TaskState(
                id=current_task.get("id", len(tasks) + 1),
                title=current_task.get("title", ""),
                description=current_task.get("description", ""),
                files=current_task.get("files", []),
                dependencies=current_task.get("dependencies", []),
                test_criteria=current_task.get("test_criteria", []),
                complexity=TaskComplexity(current_task.get("complexity", "medium")),
                phase=current_task.get("phase", 1),
            ))

        return tasks

    def _append_run_log(self, entry: str) -> None:
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.run_log_path.exists():
            self.run_log_path.write_text(
                f"# Run Log — {datetime.now().strftime('%Y-%m-%d')}\n\n{entry}",
                encoding="utf-8",
            )
        else:
            current = self.run_log_path.read_text(encoding="utf-8")
            self.run_log_path.write_text(current + "\n" + entry, encoding="utf-8")


def _get_head_commit(project_dir: Path) -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_dir,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""
