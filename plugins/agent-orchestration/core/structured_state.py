"""StructuredState — Agent 间的结构化状态定义与验证。

替代松散的 dict payload，提供类型安全的跨 Agent 状态传递。
与 EventBus 集成，确保事件 payload 满足预定义 schema。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    """子任务状态枚举。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkerResultStatus(str, Enum):
    """工作者结果状态枚举。"""

    SUCCESS = "success"
    FAILED = "failed"


class TaskState(BaseModel):
    """单个子任务的结构化状态。用于编排者→工作者的任务传递。"""

    task_id: str = Field(description="唯一任务标识")
    task_type: str = Field(default="default", description="任务类型（如 formal, conversational, technical）")
    description: str = Field(description="任务描述 — 工作者执行的具体指令")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    result: str = Field(default="", description="XML/Markdown 格式的执行结果")
    artifacts: list[str] = Field(default_factory=list, description="产物文件路径列表")
    metadata: dict[str, Any] = Field(default_factory=dict, description="类型、描述等元数据")
    artifact_path: str = Field(default="", description="L2 摘要制品文件路径")
    context_budget_used: int = Field(default=0, description="该任务消耗的估算 token 数")
    verification_path: str = Field(default="", description="验证结果文件路径")
    verified: bool = Field(default=False, description="摘要是否已通过验证")

    @field_validator("task_id")
    @classmethod
    def task_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("task_id must not be empty")
        return v


class WorkerResultState(BaseModel):
    """单个工作者执行结果的结构化状态。用于工作者→编排者的结果回传。"""

    worker_id: str = Field(description="工作者标识（如 worker-formal）")
    task_type: str = Field(description="执行的任务类型")
    description: str = Field(description="原始任务描述")
    result: str = Field(description="执行结果内容")
    status: WorkerResultStatus = Field(default=WorkerResultStatus.SUCCESS)
    artifacts: list[str] = Field(default_factory=list, description="输出产物路径")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("worker_id")
    @classmethod
    def worker_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("worker_id must not be empty")
        return v


class DispatchStatus(str, Enum):
    """子 Agent 派发状态枚举。"""

    PENDING = "pending"
    SPAWNED = "spawned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SubAgentDispatchState(BaseModel):
    """子 Agent 派发状态 — 跟踪从 Main Agent 到 Sub-Agent 的任务分发。"""

    agent_name: str = Field(description="子 Agent 实例名称")
    role: str = Field(description="角色: executor|verifier|researcher|analyst")
    task_id: str = Field(description="关联的任务标识")
    packet_path: str = Field(default="", description="任务包文件路径")
    summary_path: str = Field(default="", description="L2 摘要文件路径")
    result_path: str = Field(default="", description="L3 完整结果文件路径")
    files_path: str = Field(default="", description="文件列表路径")
    recursion_depth: int = Field(default=0, description="递归深度: 0=可派发子 Agent, 1=不可再派发")
    status: DispatchStatus = Field(default=DispatchStatus.PENDING)


class OrchestratorOutput(BaseModel):
    """编排者的完整输出 — 分析 + 任务列表 + 工作者结果。"""

    analysis: str = Field(description="编排者对任务的分析和理解")
    tasks: list[TaskState] = Field(default_factory=list, description="分解出的子任务列表")
    worker_results: list[WorkerResultState] = Field(default_factory=list, description="工作者执行结果")
    metadata: dict[str, Any] = Field(default_factory=dict, description="执行统计等元数据")

    @property
    def success_rate(self) -> float:
        """计算工作者成功率。"""
        if not self.worker_results:
            return 0.0
        succeeded = sum(1 for r in self.worker_results if r.status == WorkerResultStatus.SUCCESS)
        return succeeded / len(self.worker_results)

    @property
    def failed_workers(self) -> list[WorkerResultState]:
        """返回失败的工作者列表。"""
        return [r for r in self.worker_results if r.status == WorkerResultStatus.FAILED]


class StateTransition(BaseModel):
    """状态转换记录 — 用于跨 Agent 状态同步的事件 payload。"""

    from_agent: str = Field(description="发送方 Agent 标识")
    to_agent: str = Field(default="", description="接收方 Agent 标识（空=广播）")
    state_type: str = Field(description="状态类型: task_state | worker_result | orchestrator_output")
    payload: dict[str, Any] = Field(description="结构化状态内容（需符合对应 schema）")
    timestamp: str = Field(default="", description="ISO 格式时间戳")

    def validate_payload(self) -> bool:
        """验证 payload 是否符合 state_type 对应的 schema。"""
        try:
            if self.state_type == "task_state":
                TaskState(**self.payload)
            elif self.state_type == "worker_result":
                WorkerResultState(**self.payload)
            elif self.state_type == "orchestrator_output":
                OrchestratorOutput(**self.payload)
            else:
                return False
            return True
        except Exception:
            return False


# ── EventBus 集成的辅助函数 ──────────────────────────────────────


def event_payload_to_task_state(payload: dict[str, Any]) -> TaskState:
    """从 EventBus 事件的 payload 解析 TaskState。"""
    return TaskState(**payload)


def event_payload_to_worker_result(payload: dict[str, Any]) -> WorkerResultState:
    """从 EventBus 事件的 payload 解析 WorkerResultState。"""
    return WorkerResultState(**payload)


def task_state_to_event_payload(task: TaskState) -> dict[str, Any]:
    """将 TaskState 转换为 EventBus 事件的 payload。"""
    return task.model_dump()


def worker_result_to_event_payload(result: WorkerResultState) -> dict[str, Any]:
    """将 WorkerResultState 转换为 EventBus 事件的 payload。"""
    return result.model_dump()
