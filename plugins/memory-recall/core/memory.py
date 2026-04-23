"""Short-term memory and Soul manager for agent-flow.

File-based read/write/append for Memory.md and Soul.md.
Evolved from agent-workflow/aw/core/memory.py — ChromaDB removed, pure file system.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_MEMORY_FILENAME = "Memory.md"
_SOUL_FILENAME = "Soul.md"

_FIXED_SECTION_HEADER = "## 固定区"
_DYNAMIC_SECTION_HEADER = "## 动态区"

# Regex for dynamic experience entry header:
# ### 2026-04-11 | module:modal | type:pitfall | abstraction:framework
_EXPERIENCE_HEADER_RE = re.compile(
    r"^###\s+(?P<date>\S+)\s*\|\s*module:(?P<module>\S+)\s*\|\s*type:(?P<exp_type>\S+)"
    r"(?:\s*\|\s*abstraction:(?P<abstraction>\S+))?"
    r"(?:\s*\|\s*source:(?P<source>\S+))?\s*$"
)


class MemoryManager:
    """Manages working memory (Memory.md) and Soul.md for a single agent.

    All operations use pure file system — no external dependencies.
    """

    def __init__(self, project_dir: Path, agent_name: str = "main") -> None:
        self._project_dir: Path = project_dir
        self.memory_dir: Path = project_dir / ".agent-flow" / "memory" / agent_name
        self._agent_name: str = agent_name

    def _ensure_dir(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _fire_on_memory_write(self, content: str) -> None:
        """Fire the on_memory_write hook, non-blocking."""
        try:
            from agent_flow.core.lifecycle import fire_memory_write

            fire_memory_write(
                self._project_dir,
                agent_name=self._agent_name,
                content=content,
                metadata={"source": "memory-manager"},
            )
            logger.debug("on_memory_write hook fired successfully")
        except Exception as exc:
            logger.debug("on_memory_write hook failed: %s", exc)

    # -- Memory.md -----------------------------------------------------------

    def _memory_file(self) -> Path:
        return self.memory_dir / _MEMORY_FILENAME

    def read_memory(self) -> str:
        self._ensure_dir()
        path = self._memory_file()
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def write_memory(self, content: str) -> None:
        self._ensure_dir()
        self._memory_file().write_text(content, encoding="utf-8")
        self._fire_on_memory_write(content)

    def append_memory(self, entry: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        line = f"[{timestamp}] {entry}"
        current = self.read_memory()
        self.write_memory(f"{current}\n{line}" if current else line)

    # -- Soul.md -------------------------------------------------------------

    def _soul_file(self) -> Path:
        return self.memory_dir / _SOUL_FILENAME

    def read_soul(self) -> dict:
        self._ensure_dir()
        path = self._soul_file()
        if not path.is_file():
            return {"fixed": "", "dynamic": []}
        content = path.read_text(encoding="utf-8")
        return self._parse_soul_content(content)

    @staticmethod
    def _parse_soul_content(content: str) -> dict:
        fixed_part = ""
        dynamic_part = ""

        if _FIXED_SECTION_HEADER in content:
            fixed_start = content.index(_FIXED_SECTION_HEADER) + len(_FIXED_SECTION_HEADER)
            if _DYNAMIC_SECTION_HEADER in content:
                fixed_end = content.index(_DYNAMIC_SECTION_HEADER)
                fixed_part = content[fixed_start:fixed_end]
            else:
                fixed_part = content[fixed_start:]

        if _DYNAMIC_SECTION_HEADER in content:
            dynamic_start = content.index(_DYNAMIC_SECTION_HEADER) + len(_DYNAMIC_SECTION_HEADER)
            dynamic_part = content[dynamic_start:]

        return {
            "fixed": fixed_part.strip(),
            "dynamic": MemoryManager._parse_experiences(dynamic_part),
        }

    @staticmethod
    def _parse_experiences(text: str) -> list[dict]:
        entries: list[dict] = []
        if not text.strip():
            return entries

        lines = text.split("\n")
        current: dict | None = None
        description_lines: list[str] = []

        for line in lines:
            header_match = _EXPERIENCE_HEADER_RE.match(line.strip())
            if header_match:
                if current is not None:
                    current["description"] = "\n".join(description_lines).strip()
                    entries.append(current)
                current = {
                    "date": header_match.group("date"),
                    "module": header_match.group("module"),
                    "exp_type": header_match.group("exp_type"),
                    "abstraction": header_match.group("abstraction") or "",
                    "source": header_match.group("source") or "",
                    "description": "",
                    "confidence": 0.0,
                    "validations": 0,
                    "last_validated": "",
                }
                description_lines = []
            elif current is not None:
                stripped = line.strip()
                if stripped.startswith("confidence:"):
                    try:
                        current["confidence"] = float(stripped.split(":", 1)[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif stripped.startswith("validations:"):
                    try:
                        current["validations"] = int(stripped.split(":", 1)[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif stripped.startswith("last_validated:"):
                    current["last_validated"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("deprecated:"):
                    current["deprecated"] = stripped.split(":", 1)[1].strip().lower() in ("true", "yes", "1")
                else:
                    if stripped or description_lines:
                        description_lines.append(stripped)

        if current is not None:
            current["description"] = "\n".join(description_lines).strip()
            entries.append(current)

        return entries

    def write_soul_fixed(self, content: str) -> None:
        self._ensure_dir()
        current = self.read_soul()
        self._write_soul_file(content.strip(), current["dynamic"])

    def add_experience(
        self,
        date: str,
        module: str,
        exp_type: str,
        description: str,
        confidence: float,
        abstraction: str = "",
    ) -> None:
        self._ensure_dir()
        current = self.read_soul()
        fixed_text = current["fixed"]
        dynamic_entries = current["dynamic"]

        dynamic_entries.append({
            "date": date,
            "module": module,
            "exp_type": exp_type,
            "description": description,
            "confidence": confidence,
            "abstraction": abstraction,
            "validations": 0,
            "last_validated": "",
        })
        self._write_soul_file(fixed_text, dynamic_entries)
        self._fire_on_memory_write(description)

    def get_experiences(
        self,
        module: str | None = None,
        exp_type: str | None = None,
    ) -> list[dict]:
        soul = self.read_soul()
        entries = soul["dynamic"]
        if module is not None:
            entries = [e for e in entries if e["module"] == module]
        if exp_type is not None:
            entries = [e for e in entries if e["exp_type"] == exp_type]
        return entries

    def count_similar_experiences(self, module: str, exp_type: str) -> int:
        return len(self.get_experiences(module=module, exp_type=exp_type))

    def _write_soul_file(self, fixed_text: str, dynamic_entries: list[dict]) -> None:
        parts: list[str] = []
        parts.append(_FIXED_SECTION_HEADER)
        parts.append("")
        if fixed_text:
            parts.append(fixed_text)
        parts.append("")
        parts.append(_DYNAMIC_SECTION_HEADER)
        parts.append("")

        for entry in dynamic_entries:
            header = f"### {entry['date']} | module:{entry['module']} | type:{entry['exp_type']}"
            abstraction = entry.get("abstraction", "")
            if abstraction:
                header += f" | abstraction:{abstraction}"
            source = entry.get("source", "")
            if source:
                header += f" | source:{source}"
            parts.append(header)
            parts.append("")
            parts.append(entry["description"])
            parts.append(f"confidence: {entry['confidence']}")
            validations = entry.get("validations", 0)
            if validations:
                parts.append(f"validations: {validations}")
            last_validated = entry.get("last_validated", "")
            if last_validated:
                parts.append(f"last_validated: {last_validated}")
            deprecated = entry.get("deprecated", False)
            if deprecated:
                parts.append(f"deprecated: true")
            parts.append("")

        self._soul_file().write_text("\n".join(parts), encoding="utf-8")
