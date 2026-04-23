"""Rule-based observation compression pipeline.

Compresses raw observations from the SQLite database into structured summaries
by deduplicating, grouping, mapping types, computing confidence, and generating
narrative text. Uses only stdlib sqlite3 — no external dependencies.
"""

import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_flow.core.config import GLOBAL_DIR

# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

TYPE_MAP: dict[str, str] = {
    "read": "discovery",
    "write": "change",
    "search": "discovery",
    "install": "change",
    "execute": "change",
}

# ---------------------------------------------------------------------------
# Default database path
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = GLOBAL_DIR / "observations.db"


def _default_db_path_str() -> str:
    """Return the default database path as a string."""
    return str(_DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_CREATE_COMPRESSED_TABLE = """
CREATE TABLE IF NOT EXISTS compressed_observations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT,
    narrative TEXT,
    facts TEXT,              -- JSON array
    concepts TEXT,           -- JSON array
    obs_type TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source_observation_ids TEXT,  -- JSON array
    created_at TEXT NOT NULL
);
"""

_CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS compressed_fts USING fts5(
    title, narrative, facts, concepts,
    content='compressed_observations', content_rowid='rowid'
);
"""

# ---------------------------------------------------------------------------
# Module inference
# ---------------------------------------------------------------------------

# Patterns checked in order; first match wins.
_MODULE_RULES: list[tuple[re.Pattern[str], str | None]] = [
    # .agent-flow/Soul.md -> soul
    (re.compile(r"\.agent-flow[/\\]Soul\.md$", re.IGNORECASE), "soul"),
    # .agent-flow/wiki/<segment>/ -> extract segment
    (re.compile(r"\.agent-flow[/\\]wiki[/\\]([^/\\]+)"), None),  # extracted dynamically
    # .agent-flow/skills/<skill_name>/ -> extract skill name
    (re.compile(r"\.agent-flow[/\\]skills[/\\]([^/\\]+)"), None),
    # agent_flow/core/ -> core
    (re.compile(r"agent_flow[/\\]core[/\\]"), "core"),
    # agent_flow/cli/ -> cli
    (re.compile(r"agent_flow[/\\]cli[/\\]"), "cli"),
    # agent_flow/mcp/ -> mcp
    (re.compile(r"agent_flow[/\\]mcp[/\\]"), "mcp"),
    # agent_flow/adapters/ -> adapters
    (re.compile(r"agent_flow[/\\]adapters[/\\]"), "adapters"),
]


def infer_module(file_path: str) -> str:
    """Infer module name from a file path.

    Rules applied in order (first match wins):
      - .agent-flow/Soul.md -> 'soul'
      - .agent-flow/wiki/<segment>/ -> segment value (e.g. 'patterns')
      - .agent-flow/skills/<name>/ -> skill name
      - agent_flow/core/ -> 'core'
      - agent_flow/cli/ -> 'cli'
      - agent_flow/mcp/ -> 'mcp'
      - agent_flow/adapters/ -> 'adapters'
      - Default: first meaningful directory segment

    Args:
        file_path: Relative or absolute file path string.

    Returns:
        Lowercase module name string.
    """
    if not file_path:
        return "unknown"

    # Normalize separators
    normalized = file_path.replace("\\", "/")

    for pattern, fixed_value in _MODULE_RULES:
        m = pattern.search(normalized)
        if m:
            if fixed_value is not None:
                return fixed_value
            # Dynamic extraction from first capture group
            group = m.group(1)
            if group:
                return group.lower()

    # Default: first meaningful directory segment
    parts = [p for p in normalized.split("/") if p and p != "." and p != ".."]
    if len(parts) >= 2:
        # Use the directory containing the file, not the filename itself
        return parts[-2].lower()
    if parts:
        return parts[0].lower()

    return "unknown"


# ---------------------------------------------------------------------------
# Observation grouping
# ---------------------------------------------------------------------------


def _map_obs_type(observation_type: str) -> str:
    """Map raw observation type to compressed type using TYPE_MAP.

    Falls back to 'discovery' for unknown types.
    """
    return TYPE_MAP.get(observation_type, "discovery")


def group_observations(observations: list[dict]) -> dict[str, list[dict]]:
    """Group observations by (session_id, module, observation_type_mapped).

    Each observation dict is expected to have keys:
        session_id, file_path, observation_type, and other fields from the
        observations table.

    Returns:
        Dict mapping group_key string to list of observation dicts.
        group_key format: "{session_id}|{module}|{mapped_type}"
    """
    groups: dict[str, list[dict]] = {}

    for obs in observations:
        session_id = obs.get("session_id", "")
        file_path = obs.get("file_path", "") or ""
        obs_type_raw = obs.get("observation_type", "") or ""
        module = infer_module(file_path)
        mapped_type = _map_obs_type(obs_type_raw)

        key = f"{session_id}|{module}|{mapped_type}"
        groups.setdefault(key, []).append(obs)

    return groups


# ---------------------------------------------------------------------------
# Narrative / title / facts generation
# ---------------------------------------------------------------------------


def _extract_title_hint(summary: str) -> str:
    """Extract a short title hint from tool_input_summary.

    Returns up to the first 80 characters of the summary, stripped.
    """
    if not summary:
        return ""
    text = summary.strip().split("\n")[0]
    return text[:80]


def _count_by_type(obs_list: list[dict]) -> dict[str, int]:
    """Count observations by their raw observation_type in a group."""
    counts: dict[str, int] = {}
    for obs in obs_list:
        raw = obs.get("observation_type", "") or ""
        counts[raw] = counts.get(raw, 0) + 1
    return counts


def generate_compressed_entry(group_key: str, obs_list: list[dict]) -> dict:
    """Generate a compressed observation dict from a group of observations.

    Args:
        group_key: Format "{session_id}|{module}|{mapped_type}".
        obs_list: List of observation dicts belonging to this group.

    Returns:
        Dict with keys: id, session_id, title, subtitle, narrative, facts,
        concepts, obs_type, confidence, source_observation_ids, created_at.
    """
    parts = group_key.split("|", 2)
    session_id = parts[0] if len(parts) > 0 else ""
    module = parts[1] if len(parts) > 1 else "unknown"
    mapped_type = parts[2] if len(parts) > 2 else "discovery"

    n = len(obs_list)
    confidence = min(n * 0.2, 1.0)

    # Unique file paths in this group
    file_paths = sorted({obs.get("file_path", "") for obs in obs_list if obs.get("file_path")})
    unique_files = file_paths

    # Count by raw type
    type_counts = _count_by_type(obs_list)
    read_count = type_counts.get("read", 0)
    write_count = type_counts.get("write", 0)
    search_count = type_counts.get("search", 0)
    install_count = type_counts.get("install", 0)
    execute_count = type_counts.get("execute", 0)

    # First input summary for subtitle
    first_summary = ""
    for obs in obs_list:
        s = obs.get("tool_input_summary", "")
        if s:
            first_summary = s
            break

    # --- Title ---
    if len(unique_files) == 1:
        title = unique_files[0]
    else:
        title = f"{module} module ({len(unique_files)} files)"

    # --- Subtitle ---
    subtitle = _extract_title_hint(first_summary)

    # --- Narrative ---
    narrative = _generate_narrative(
        module=module,
        unique_files=unique_files,
        read_count=read_count,
        write_count=write_count,
        search_count=search_count,
        install_count=install_count,
        execute_count=execute_count,
        first_summary=first_summary,
    )

    # --- Facts ---
    facts: list[str] = []
    facts.extend(unique_files)
    tool_names = sorted({obs.get("tool_name", "") for obs in obs_list if obs.get("tool_name")})
    facts.extend(tool_names)
    # Extract error indicators from output summaries
    for obs in obs_list:
        output = obs.get("tool_output_summary", "") or ""
        if _is_error_indicator(output):
            facts.append(f"error: {output[:100]}")

    # --- Concepts ---
    concepts = _extract_concepts(module, mapped_type, obs_list)

    # --- Source observation IDs ---
    source_ids = [str(obs.get("id", "")) for obs in obs_list if obs.get("id") is not None]

    return {
        "id": uuid.uuid4().hex,
        "session_id": session_id,
        "title": title,
        "subtitle": subtitle,
        "narrative": narrative,
        "facts": json.dumps(facts, ensure_ascii=False),
        "concepts": json.dumps(concepts, ensure_ascii=False),
        "obs_type": mapped_type,
        "confidence": confidence,
        "source_observation_ids": json.dumps(source_ids),
        "created_at": datetime.utcnow().isoformat(),
    }


def _generate_narrative(
    *,
    module: str,
    unique_files: list[str],
    read_count: int,
    write_count: int,
    search_count: int,
    install_count: int,
    execute_count: int,
    first_summary: str,
) -> str:
    """Generate a 2-3 sentence narrative from grouped observations."""
    sentences: list[str] = []

    if len(unique_files) == 1:
        file_name = unique_files[0]
        if read_count > 0 and write_count == 0:
            sentences.append(f"Read {file_name} {read_count} time{'s' if read_count != 1 else ''} during session.")
        elif write_count > 0 and read_count == 0:
            hint = _extract_title_hint(first_summary)
            detail = f" -- {hint}" if hint else ""
            sentences.append(f"Modified {file_name}{detail}.")
        elif write_count > 0 and read_count > 0:
            sentences.append(
                f"Read and modified {file_name}: "
                f"{read_count} read{'s' if read_count != 1 else ''}, "
                f"{write_count} write{'s' if write_count != 1 else ''}."
            )
        else:
            action_parts: list[str] = []
            if search_count:
                action_parts.append(f"{search_count} search{'es' if search_count != 1 else ''}")
            if install_count:
                action_parts.append(f"{install_count} install{'s' if install_count != 1 else ''}")
            if execute_count:
                action_parts.append(f"{execute_count} execution{'s' if execute_count != 1 else ''}")
            action_str = ", ".join(action_parts) if action_parts else "interacted with"
            sentences.append(f"{action_str} on {file_name} during session.")
    else:
        # Multiple files in same module
        parts: list[str] = []
        if read_count:
            parts.append(f"read {read_count} file{'s' if read_count != 1 else ''}")
        if write_count:
            parts.append(f"wrote {write_count} file{'s' if write_count != 1 else ''}")
        if search_count:
            parts.append(f"searched {search_count} time{'s' if search_count != 1 else ''}")
        if install_count:
            parts.append(f"installed {install_count} package{'s' if install_count != 1 else ''}")
        if execute_count:
            parts.append(f"executed {execute_count} command{'s' if execute_count != 1 else ''}")

        if parts:
            detail = ", ".join(parts)
            sentences.append(f"Explored {module} module: {detail}.")
        else:
            sentences.append(f"Worked in {module} module across {len(unique_files)} files.")

    # Add context about scope if there are many files
    if len(unique_files) > 3:
        sentences.append(f"Spanned {len(unique_files)} distinct files in the {module} module.")

    return " ".join(sentences)


def _is_error_indicator(text: str) -> bool:
    """Check if an output summary contains error indicators."""
    if not text:
        return False
    lower = text.lower()
    error_keywords = ["error", "failed", "failure", "exception", "traceback", "fatal"]
    return any(kw in lower for kw in error_keywords)


def _extract_concepts(module: str, mapped_type: str, obs_list: list[dict]) -> list[str]:
    """Extract concept tags from the observations.

    Includes the module name, mapped type, and any distinctive patterns
    found in the tool names or summaries.
    """
    concepts: list[str] = []
    concepts.append(module)
    concepts.append(mapped_type)

    # Add observation type categories present
    raw_types = {obs.get("observation_type", "") for obs in obs_list if obs.get("observation_type")}
    for rt in sorted(raw_types):
        if rt not in concepts:
            concepts.append(rt)

    # Check for cross-cutting concerns
    for obs in obs_list:
        tool = (obs.get("tool_name", "") or "").lower()
        if "test" in tool and "testing" not in concepts:
            concepts.append("testing")
        if "docker" in tool and "docker" not in concepts:
            concepts.append("docker")
        if "git" in tool and "git" not in concepts:
            concepts.append("git")
        output = (obs.get("tool_output_summary", "") or "").lower()
        if "error" in output and "error-handling" not in concepts:
            concepts.append("error-handling")

    return concepts


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create compressed_observations and FTS tables if they don't exist."""
    conn.executescript(_CREATE_COMPRESSED_TABLE)
    # FTS5 virtual table creation may fail if already exists with different
    # schema; guard with try/except for robustness.
    try:
        conn.execute(_CREATE_FTS_TABLE.strip())
    except sqlite3.OperationalError:
        pass  # Already exists


def _fetch_uncompressed(conn: sqlite3.Connection, session_id: str | None = None) -> list[dict]:
    """Fetch all uncompressed observations, optionally filtered by session.

    Returns list of dicts with column names as keys.
    """
    if session_id is not None:
        rows = conn.execute(
            "SELECT * FROM observations WHERE compressed = 0 AND session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM observations WHERE compressed = 0 ORDER BY session_id, timestamp"
        ).fetchall()

    return [dict(row) for row in rows]


def _insert_compressed(conn: sqlite3.Connection, entry: dict) -> None:
    """Insert a compressed observation and update the FTS index."""
    conn.execute(
        """
        INSERT INTO compressed_observations
            (id, session_id, title, subtitle, narrative, facts, concepts,
             obs_type, confidence, source_observation_ids, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["id"],
            entry["session_id"],
            entry["title"],
            entry["subtitle"],
            entry["narrative"],
            entry["facts"],
            entry["concepts"],
            entry["obs_type"],
            entry["confidence"],
            entry["source_observation_ids"],
            entry["created_at"],
        ),
    )

    # Insert into FTS
    conn.execute(
        """
        INSERT INTO compressed_fts (rowid, title, narrative, facts, concepts)
        VALUES ((SELECT rowid FROM compressed_observations WHERE id = ?), ?, ?, ?, ?)
        """,
        (
            entry["id"],
            entry["title"],
            entry["narrative"],
            entry["facts"],
            entry["concepts"],
        ),
    )


def _mark_source_observations(conn: sqlite3.Connection, entry: dict) -> None:
    """Mark source observations as compressed and set their summary_id."""
    source_ids = json.loads(entry["source_observation_ids"])
    summary_id = entry["id"]

    for obs_id in source_ids:
        conn.execute(
            "UPDATE observations SET compressed = 1, summary_id = ? WHERE id = ?",
            (summary_id, obs_id),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compress_session(db_path: str, session_id: str) -> list[str]:
    """Compress all uncompressed observations for a given session.

    Groups observations by (session_id, module, mapped_type), generates
    a compressed entry for each group, inserts into compressed_observations,
    and marks source observations as compressed.

    Args:
        db_path: Path to the SQLite observations database.
        session_id: The session to compress.

    Returns:
        List of compressed observation IDs created.
    """
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)

        observations = _fetch_uncompressed(conn, session_id=session_id)
        if not observations:
            return []

        groups = group_observations(observations)
        compressed_ids: list[str] = []

        with conn:
            for group_key, obs_list in groups.items():
                entry = generate_compressed_entry(group_key, obs_list)
                _insert_compressed(conn, entry)
                _mark_source_observations(conn, entry)
                compressed_ids.append(entry["id"])

        return compressed_ids

    finally:
        conn.close()


def compress_all(db_path: str) -> int:
    """Compress all uncompressed observations across all sessions.

    Processes each session independently to keep transaction sizes manageable.

    Args:
        db_path: Path to the SQLite observations database.

    Returns:
        Total number of compressed observations created.
    """
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)

        # Get distinct session IDs with uncompressed observations
        rows = conn.execute(
            "SELECT DISTINCT session_id FROM observations WHERE compressed = 0"
        ).fetchall()

        session_ids = [row["session_id"] for row in rows]

    finally:
        conn.close()

    total = 0
    for sid in session_ids:
        ids = compress_session(db_path, sid)
        total += len(ids)

    return total
