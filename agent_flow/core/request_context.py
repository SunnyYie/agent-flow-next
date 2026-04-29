from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agent_flow.core.flow_context import FlowContextManager


_URL_RE = re.compile(r"https?://[^\s，、]+")
_PATH_RE = re.compile(r"(?<!:)/[^\s，、]+")
_PROJECT_PATTERNS = [
    re.compile(r"在([A-Za-z0-9._-]+)项目下"),
    re.compile(r"\b([A-Za-z0-9._-]+)项目\b"),
]


class RequestDocument(BaseModel):
    type: str
    path: str


class StageGate(BaseModel):
    id: str
    name: str
    required: bool = False
    goal: str = ""


class RequestContext(BaseModel):
    project: str = ""
    raw_prompt: str = ""
    documents: list[RequestDocument] = Field(default_factory=list)
    has_ui_input: bool = False
    ui_constraints_required: bool = False
    requires_feishu: bool = False
    execution_mode: str = "auto-with-gates"
    stage_gates: list[StageGate] = Field(default_factory=list)


def parse_request_prompt(prompt: str) -> RequestContext:
    text = prompt.strip()
    documents: list[RequestDocument] = []
    seen_paths: set[str] = set()

    for path in _extract_candidates(text):
        normalized = path.rstrip("。；;,.，、")
        if not normalized or normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        documents.append(RequestDocument(type=_classify_document(normalized), path=normalized))

    project = ""
    for pattern in _PROJECT_PATTERNS:
        match = pattern.search(text)
        if match:
            project = match.group(1)
            break

    has_ui_input = any(doc.type == "ui file" for doc in documents)
    ui_constraints_required = has_ui_input and _is_ui_related_prompt(text)
    requires_feishu = any(doc.type == "feishu url" for doc in documents)
    return RequestContext(
        project=project,
        raw_prompt=text,
        documents=documents,
        has_ui_input=has_ui_input,
        ui_constraints_required=ui_constraints_required,
        requires_feishu=requires_feishu,
        stage_gates=[
            StageGate(id="G1", name="初始化与环境就绪", required=False, goal="协议、Hook、结构文档全部就绪"),
            StageGate(id="G2", name="需求拆解与任务清单确认", required=True, goal="任务列表、代码定位、待确认项完整"),
            StageGate(id="G3", name="实现与测试证据完成", required=False, goal="代码完成并具备验证证据"),
            StageGate(id="G4", name="用户验收与交付闭环", required=True, goal="复盘、验收、Jira/PR 闭环完成"),
        ],
    )


def write_request_context(project_root: Path, context: RequestContext) -> Path:
    state_dir = project_root / ".agent-flow" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "request-context.json"
    path.write_text(context.model_dump_json(indent=2), encoding="utf-8")
    return path


def ensure_request_scaffolds(project_root: Path, project_name: str, context: RequestContext | None = None) -> None:
    state_dir = project_root / ".agent-flow" / "state"
    wiki_dir = project_root / ".agent-flow" / "wiki"
    state_dir.mkdir(parents=True, exist_ok=True)
    wiki_dir.mkdir(parents=True, exist_ok=True)

    _ensure_text_file(
        wiki_dir / "project-structure.md",
        render_project_structure(project_name),
    )
    _ensure_text_file(
        state_dir / "requirements-initial.md",
        render_requirements_initial(project_name, context),
    )
    _ensure_text_file(
        state_dir / "task-list.md",
        render_task_list(project_name, context),
    )
    _ensure_text_file(
        state_dir / "phase-review.md",
        render_phase_review(project_name),
    )
    _ensure_text_file(
        state_dir / "agent-team-config.yaml",
        yaml.safe_dump(default_agent_team_config(), sort_keys=False, allow_unicode=True),
    )

    flow_manager = FlowContextManager(project_root)
    flow_context = flow_manager.load()
    if not flow_context.workflow_id:
        flow_context = flow_manager.init_workflow(f"{project_name or project_root.name}-request")
    if flow_context.phase.value == "PLAN":
        flow_context.phase = type(flow_context.phase)("TEAM_INIT")
    flow_context.team_config = default_agent_team_config()
    flow_manager.save(flow_context)


def render_project_structure(project_name: str) -> str:
    return (
        f"# 项目结构映射: {project_name}\n\n"
        "## 1. 业务关键词 -> 代码目录\n"
        "| 关键词/Tag | 目录/模块 | 关键文件 | 说明 |\n"
        "|---|---|---|---|\n"
        "| 待补充 | 待补充 | 待补充 | 初始化后根据需求列表补齐 |\n\n"
        "## 2. 页面/组件入口\n"
        "| 场景 | 入口文件 | 关联组件 | 关联Hook |\n"
        "|---|---|---|---|\n"
        "| 待补充 | 待补充 | 待补充 | 待补充 |\n\n"
        "## 3. 数据与状态\n"
        "| 数据源 | 状态管理 | 消费位置 | 备注 |\n"
        "|---|---|---|---|\n"
        "| 待补充 | 待补充 | 待补充 | 待补充 |\n\n"
        "## 4. 埋点与日志\n"
        "| 事件名 | 触发位置 | 参数结构 | 备注 |\n"
        "|---|---|---|---|\n"
        "| 待补充 | 待补充 | 待补充 | 待补充 |\n"
    )


def render_requirements_initial(project_name: str, context: RequestContext | None = None) -> str:
    source_lines = ["## 需求来源"]
    if context and context.documents:
        for doc in context.documents:
            source_lines.append(f"- {doc.type}: {doc.path}")
    else:
        source_lines.append("- 文档链接: 待补充")
        source_lines.append("- 文档类型: 待补充")

    return (
        f"# 前端需求初步列表: {project_name}\n\n"
        + "\n".join(source_lines)
        + "\n\n## UI需求\n"
        "| 编号 | 需求点 | 页面/组件 | 期望表现 | 验收要点 |\n"
        "|---|---|---|---|---|\n"
        "| UI-1 | 待补充 | 待补充 | 待补充 | 待补充 |\n\n"
        "## 功能需求\n"
        "| 编号 | 需求点 | 触发条件 | 输入/输出 | 数据/接口/埋点 |\n"
        "|---|---|---|---|---|\n"
        "| FN-1 | 待补充 | 待补充 | 待补充 | 待补充 |\n\n"
        "## 待确认事项\n"
        "- Q1:\n"
        "- Q2:\n\n"
        "## 初步范围边界\n"
        "- In scope:\n"
        "- Out of scope:\n"
    )


def render_task_list(project_name: str, context: RequestContext | None = None) -> str:
    ui_rule = "必须严格按照提供的 UI 文件实现，并在开始编码前完成 frontend-design / ui-ux-pro-max 约束确认。"
    ui_hint = ui_rule if context and context.ui_constraints_required else "无 UI 文件时按常规需求拆解执行。"
    return (
        f"# 开发任务清单: {project_name}\n\n"
        "## 任务约束\n"
        f"- UI 约束: {ui_hint}\n"
        "- 每个任务都必须写明功能点、目标文件/模块、依赖、验收方式。\n"
        "- 没有明确目标文件/模块的任务禁止进入开发。\n\n"
        "## 任务列表\n"
        "| 任务ID | 任务类型 | 功能点 | 目标文件/模块 | 执行Agent | 依赖 | 验收方式 | 状态 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| T1 | ui/feature/api/test | 待补充 | 待补充 | coder-agent/verifier-agent/supervisor-agent | 无 | 待补充 | pending |\n\n"
        "## Agent 分工\n"
        "| 角色 | 触发时机 | 职责 |\n"
        "|---|---|---|\n"
        "| Main Agent | 全流程 | 结构化输入、阶段推进、门控与复盘 |\n"
        "| Supervisor Agent | G2/G4、Jira/分支/PR 场景 | 流程监督、Jira 字段校验、交付闭环 |\n"
        "| Coder Agent | 进入 EXECUTE 后 | 按任务清单实现和测试 |\n"
        "| Verifier Agent | 首轮实现完成后 | 独立验收、回归核查 |\n"
    )


def render_phase_review(project_name: str) -> str:
    return (
        f"# 阶段复盘: {project_name}\n\n"
        "## G1 初始化与环境就绪\n"
        "- 目标: 协议文件、Hook、project-structure、request-context、agent-team-config 就绪\n"
        "- 当前问题:\n"
        "- 优化动作:\n\n"
        "## G2 需求拆解与任务清单确认\n"
        "- 目标: requirements-initial、task-list、代码定位、待确认项全部明确\n"
        "- 当前问题:\n"
        "- 优化动作:\n\n"
        "## G3 实现与测试证据完成\n"
        "- 目标: 开发完成，测试证据齐备，风险登记清晰\n"
        "- 当前问题:\n"
        "- 优化动作:\n\n"
        "## G4 用户验收与交付闭环\n"
        "- 目标: 用户确认、Jira/PR 完成、复盘沉淀结束\n"
        "- 当前问题:\n"
        "- 优化动作:\n"
    )


def default_agent_team_config() -> dict:
    return {
        "team_mode": "full-team",
        "gates": {
            "G1": {"required": False, "goal": "初始化与环境就绪"},
            "G2": {"required": True, "goal": "需求拆解与任务清单确认"},
            "G3": {"required": False, "goal": "实现与测试证据完成"},
            "G4": {"required": True, "goal": "用户验收与交付闭环"},
        },
        "roles": [
            {
                "name": "main-agent",
                "role": "coordinator",
                "trigger": "always",
                "responsibility": "维护 request-context、task-list、flow-context 与阶段门控",
            },
            {
                "name": "supervisor-agent",
                "role": "supervisor",
                "trigger": "before G2 and before G4",
                "responsibility": "监督 Jira/分支/PR/交付动作，处理非默认业务决策字段",
            },
            {
                "name": "coder-agent",
                "role": "executor",
                "trigger": "after G2 approval",
                "responsibility": "依据 task-list 开发功能并回传测试证据",
            },
            {
                "name": "verifier-agent",
                "role": "verifier",
                "trigger": "after implementation package ready",
                "responsibility": "独立验收功能、检查回归与风险",
            },
        ],
    }


def _extract_candidates(text: str) -> list[str]:
    urls = _URL_RE.findall(text)
    url_path_fragments = set()
    for url in urls:
        domain_marker = "://"
        if domain_marker in url:
            after_scheme = url.split(domain_marker, 1)[1]
            url_path_fragments.add("/" + after_scheme)
            slash_index = after_scheme.find("/")
            if slash_index >= 0:
                url_path_fragments.add("/" + after_scheme[slash_index + 1 :])

    paths = [path for path in _PATH_RE.findall(text) if path not in url_path_fragments]
    items = [*urls, *paths]
    items.sort(key=text.find)
    return items


def _classify_document(candidate: str) -> str:
    lower = candidate.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        if "feishu.cn" in lower:
            return "feishu url"
        return "url"
    if "/fewshots/" in lower:
        return "fewshots file"
    if any(keyword in candidate for keyword in ("交付物", "设计稿", "设计文档", "原型")):
        return "ui file"
    if candidate.endswith(".html"):
        return "ui file"
    return "local file"


def _is_ui_related_prompt(text: str) -> bool:
    lowered = text.lower()
    ui_keywords = (
        "ui",
        "h5",
        "html",
        "设计稿",
        "设计图",
        "原型",
        "交互",
        "视觉",
        "样式",
        "布局",
    )
    return any(keyword in lowered for keyword in ui_keywords)


def _ensure_text_file(path: Path, content: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
