"""Structured task reflection helpers.

Builds a post-task reflection report from main/sub-agent memory files and
produces a compact payload suitable for recall summaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


_TIMESTAMP_PREFIX_RE = re.compile(r"^\[[^\]]+\]\s*")

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "search": ("搜索", "文档", "issue", "github", "源码", "案例", "最佳实践", "keyword", "recall"),
    "business": ("project-structure", "模块", "入口", "结构", "依赖", "环境", "配置", "权限", "脚本", "初始化"),
    "execution": ("hook", "阻拦", "耗时", "流程", "阶段", "编排", "agent-flow", "上下文", "重试"),
    "best_practice": ("最佳实践", "github", "社区", "开源", "模式", "wiki", "全局 wiki"),
}

_DECISION_KEYWORDS = ("决定", "决策", "选择", "adopt", "use ", "改为", "统一由")
_ISSUE_KEYWORDS = ("问题", "阻拦", "报错", "失败", "缺少", "缺失", "冲突", "耗时", "卡住")


@dataclass
class AgentReflection:
    agent_name: str
    memory_path: str
    lines: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    categories: dict[str, list[str]] = field(default_factory=lambda: {
        "search": [],
        "business": [],
        "execution": [],
        "best_practice": [],
    })
    decisions: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    has_explicit_summary: bool = False


@dataclass
class ReflectionBundle:
    report_path: Path
    aggregated_categories: dict[str, list[str]]
    key_decisions: list[str]
    experiences_extracted: list[str]
    errors_encountered: list[str]


def build_reflection_bundle(project_dir: Path, phase: str, task_description: str) -> ReflectionBundle:
    """Aggregate structured reflection across main + sub-agent memories."""
    reflections = _collect_agent_reflections(project_dir)
    aggregated = {
        "search": [],
        "business": [],
        "execution": [],
        "best_practice": [],
    }
    decisions: list[str] = []
    issues: list[str] = []

    for reflection in reflections:
        for category, items in reflection.categories.items():
            aggregated[category].extend(_dedupe_preserve_order(items))
        decisions.extend(reflection.decisions)
        issues.extend(reflection.issues)
        if reflection.agent_name != "main" and not reflection.has_explicit_summary:
            issues.append(f"子 Agent {reflection.agent_name} 未提供显式总结，主 Agent 已按 Memory 回收线索。")

    subagent_names = [r.agent_name for r in reflections if r.agent_name != "main"]
    if subagent_names:
        decisions.insert(0, f"主 Agent 汇总 {len(subagent_names)} 个子 Agent 的反思结果：{', '.join(subagent_names)}")

    report_path = _write_reflection_report(project_dir, phase, task_description, reflections, aggregated, decisions, issues)

    experiences = []
    label_map = {
        "search": "搜索复盘",
        "business": "业务与代码定位复盘",
        "execution": "任务执行流程复盘",
        "best_practice": "最佳实践复盘",
    }
    for key in ("search", "business", "execution", "best_practice"):
        items = _dedupe_preserve_order(aggregated[key])
        if items:
            experiences.append(f"{label_map[key]}: {items[0]}")
    if subagent_names:
        experiences.append(f"子 Agent 总结: 已汇总 {', '.join(subagent_names)}")

    return ReflectionBundle(
        report_path=report_path,
        aggregated_categories={k: _dedupe_preserve_order(v) for k, v in aggregated.items()},
        key_decisions=_dedupe_preserve_order(decisions),
        experiences_extracted=experiences,
        errors_encountered=_dedupe_preserve_order(issues),
    )


def _collect_agent_reflections(project_dir: Path) -> list[AgentReflection]:
    memory_root = project_dir / ".agent-flow" / "memory"
    reflections: list[AgentReflection] = []
    if not memory_root.is_dir():
        return reflections

    for agent_dir in sorted(memory_root.iterdir(), key=lambda p: (p.name != "main", p.name)):
        if not agent_dir.is_dir():
            continue
        memory_path = agent_dir / "Memory.md"
        if not memory_path.is_file():
            continue
        lines = _load_memory_lines(memory_path)
        if not lines:
            continue
        reflections.append(_analyze_agent_memory(agent_dir.name, memory_path, lines))

    return reflections


def _load_memory_lines(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    cleaned: list[str] = []
    for raw in content.splitlines():
        stripped = _TIMESTAMP_PREFIX_RE.sub("", raw).strip()
        if stripped:
            cleaned.append(stripped)
    return cleaned


def _analyze_agent_memory(agent_name: str, memory_path: Path, lines: list[str]) -> AgentReflection:
    reflection = AgentReflection(
        agent_name=agent_name,
        memory_path=str(memory_path.relative_to(memory_path.parents[3])),
        lines=lines,
        summary_lines=lines[:5],
    )

    reflection.has_explicit_summary = any(
        line.startswith("### 完成情况") or line.startswith("### 经验提取")
        for line in lines
    )

    for line in lines:
        lowered = line.lower()
        matched = False
        for category, keywords in _CATEGORY_KEYWORDS.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                reflection.categories[category].append(line)
                matched = True
        if any(keyword.lower() in lowered for keyword in _DECISION_KEYWORDS):
            reflection.decisions.append(line)
        if any(keyword.lower() in lowered for keyword in _ISSUE_KEYWORDS):
            reflection.issues.append(line)
        if not matched and ("建议" in line or "总结" in line):
            reflection.summary_lines.append(line)

    return reflection


def _write_reflection_report(
    project_dir: Path,
    phase: str,
    task_description: str,
    reflections: list[AgentReflection],
    aggregated: dict[str, list[str]],
    decisions: list[str],
    issues: list[str],
) -> Path:
    now = datetime.now()
    phase_slug = (phase or "session").lower()
    report_dir = project_dir / ".agent-flow" / "logs" / "reflection"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{now.strftime('%Y-%m-%d')}-{phase_slug}.md"

    parts = [
        f"# Reflection: {task_description or phase or 'session'}",
        "",
        f"- 生成时间: {now.isoformat(timespec='seconds')}",
        f"- 阶段: {phase or 'session'}",
        "",
        "## 搜索复盘",
    ]
    parts.extend(_render_bullets(aggregated["search"], "未记录困难问题搜索、缺失文档或有效关键词。"))
    parts.extend(["", "## 业务与代码定位复盘"])
    parts.extend(_render_bullets(aggregated["business"], "未记录 project-structure、环境、依赖或代码定位相关反思。"))
    parts.extend(["", "## 任务执行流程复盘"])
    parts.extend(_render_bullets(aggregated["execution"], "未记录 hook、耗时、流程裁剪或架构优化相关反思。"))
    parts.extend(["", "## 最佳实践复盘"])
    parts.extend(_render_bullets(aggregated["best_practice"], "未记录来自 GitHub / 社区的最佳实践结论。"))

    parts.extend(["", "## 子 Agent 总结"])
    subagents = [item for item in reflections if item.agent_name != "main"]
    if not subagents:
        parts.append("- 本次任务没有子 Agent。")
    else:
        for reflection in subagents:
            parts.append(f"### {reflection.agent_name}")
            parts.append(f"- Memory: `{reflection.memory_path}`")
            parts.append(f"- 显式总结: {'是' if reflection.has_explicit_summary else '否'}")
            for line in reflection.summary_lines[:4]:
                parts.append(f"- {line}")
            if not reflection.summary_lines:
                parts.append("- 未提取到有效总结内容。")
            parts.append("")

    parts.extend(["## 主 Agent 统一结论"])
    parts.extend(_render_bullets(decisions, "主 Agent 未记录显式统一决策。"))

    if issues:
        parts.extend(["", "## 待补充与风险"])
        parts.extend(_render_bullets(issues, "无"))

    report_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return report_path


def _render_bullets(lines: list[str], fallback: str) -> list[str]:
    items = _dedupe_preserve_order(lines)
    if not items:
        return [f"- {fallback}"]
    return [f"- {line}" for line in items]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
