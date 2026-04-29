"""Memory index — unified FTS5 search across Soul.md, Wiki, Recall, and Skills.

Indexes existing memory files into SQLite for fast cross-source search.
Enables the MCP memory_search tool to query all sources uniformly.
"""

import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from agent_flow.core.config import project_skills_dirs, project_wiki_dirs

# --- Schema ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memory_index (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT,
    module TEXT,
    category TEXT,
    abstraction TEXT,
    confidence REAL,
    layer TEXT DEFAULT 'project',
    content_summary TEXT,
    tags TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_mem_type ON memory_index(source_type);
CREATE INDEX IF NOT EXISTS idx_mem_module ON memory_index(module);
CREATE INDEX IF NOT EXISTS idx_mem_category ON memory_index(category);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    title, content_summary, tags,
    content='memory_index', content_rowid='rowid'
);
"""

# Soul.md experience header regex (same as MemoryManager)
_EXPERIENCE_HEADER_RE = re.compile(
    r"^###\s+(?P<date>\S+)\s*\|\s*module:(?P<module>\S+)\s*\|\s*type:(?P<exp_type>\S+)"
    r"(?:\s*\|\s*abstraction:(?P<abstraction>\S+))?"
    r"(?:\s*\|\s*source:(?P<source>\S+))?\s*$"
)

# Confidence regex within experience body
_CONFIDENCE_RE = re.compile(r"confidence:\s*([0-9.]+)")


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Get SQLite connection with WAL mode."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def _determine_layer(path: Path, project_dir: Path) -> str:
    """Determine if a path is global or project level."""
    try:
        rel = path.relative_to(project_dir)
        return "project"
    except ValueError:
        # Outside project dir = global
        return "global"


# --- Soul.md Indexing ---

def index_soul(project_dir: Path, db_path: str) -> int:
    """Index Soul.md dynamic section entries into memory_index."""
    conn = _get_connection(db_path)
    count = 0

    # Find Soul.md files
    soul_paths = []
    for pattern in [".agent-flow/memory/*/Soul.md"]:
        soul_paths.extend(project_dir.glob(pattern))

    # Global Soul.md
    global_soul = Path.home() / ".agent-flow" / "memory" / "main" / "Soul.md"
    if global_soul.is_file():
        soul_paths.append(global_soul)

    for soul_path in soul_paths:
        layer = _determine_layer(soul_path, project_dir)
        rel_path = str(soul_path.relative_to(project_dir)) if soul_path.is_relative_to(project_dir) else str(soul_path)

        try:
            content = soul_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Parse dynamic section
        entries = _parse_soul_entries(content)
        for entry in entries:
            entry_id = f"soul-{entry['date']}-{entry['module']}-{entry['exp_type']}"
            # Remove existing entry
            conn.execute("DELETE FROM memory_index WHERE id = ?", (entry_id,))

            conn.execute(
                """INSERT INTO memory_index
                (id, source_type, source_path, title, module, category, abstraction,
                 confidence, layer, content_summary, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    "soul",
                    rel_path,
                    entry.get("title", f"{entry['date']} {entry['module']} {entry['exp_type']}"),
                    entry["module"],
                    entry["exp_type"],
                    entry.get("abstraction"),
                    entry.get("confidence", 0.5),
                    layer,
                    entry.get("body", "")[:500],
                    json.dumps([entry["module"], entry["exp_type"]], ensure_ascii=False),
                    entry["date"],
                    datetime.now().isoformat(),
                ),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def _parse_soul_entries(content: str) -> list[dict]:
    """Parse Soul.md dynamic section into structured entries."""
    entries = []
    lines = content.split("\n")
    current_entry = None
    body_lines = []

    for line in lines:
        m = _EXPERIENCE_HEADER_RE.match(line)
        if m:
            # Save previous entry
            if current_entry is not None:
                current_entry["body"] = "\n".join(body_lines).strip()
                # Extract title from body
                if body_lines:
                    first_line = body_lines[0].strip()
                    if first_line:
                        current_entry["title"] = first_line[:100]
                # Extract confidence
                conf_match = _CONFIDENCE_RE.search(current_entry["body"])
                if conf_match:
                    try:
                        current_entry["confidence"] = float(conf_match.group(1))
                    except ValueError:
                        pass
                entries.append(current_entry)

            current_entry = {
                "date": m.group("date"),
                "module": m.group("module"),
                "exp_type": m.group("exp_type"),
                "abstraction": m.group("abstraction"),
                "source": m.group("source"),
                "title": "",
                "body": "",
                "confidence": 0.5,
            }
            body_lines = []
        elif current_entry is not None:
            body_lines.append(line)

    # Save last entry
    if current_entry is not None:
        current_entry["body"] = "\n".join(body_lines).strip()
        if body_lines:
            first_line = body_lines[0].strip()
            if first_line:
                current_entry["title"] = first_line[:100]
        conf_match = _CONFIDENCE_RE.search(current_entry["body"])
        if conf_match:
            try:
                current_entry["confidence"] = float(conf_match.group(1))
            except ValueError:
                pass
        entries.append(current_entry)

    return entries


# --- Wiki Indexing ---

def index_wiki(project_dir: Path, db_path: str) -> int:
    """Index wiki directory entries into memory_index."""
    conn = _get_connection(db_path)
    count = 0

    wiki_dirs = [(d, _determine_layer(d, project_dir)) for d in project_wiki_dirs(project_dir)]

    # Global wiki
    global_wiki = Path.home() / ".agent-flow" / "wiki"
    if global_wiki.is_dir():
        wiki_dirs.append((global_wiki, "global"))

    for wiki_dir, layer in wiki_dirs:
        for md_file in wiki_dir.rglob("*.md"):
            # Skip INDEX.md and recall directory
            if md_file.name == "INDEX.md":
                continue
            if "recall" in str(md_file.relative_to(wiki_dir)):
                continue

            rel_path = str(md_file.relative_to(project_dir)) if md_file.is_relative_to(project_dir) else str(md_file)
            entry_id = f"wiki-{md_file.stem}"

            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # Parse YAML frontmatter
            metadata = _parse_frontmatter(content)
            title = metadata.get("title", md_file.stem)

            # Infer category from directory structure
            rel_to_wiki = md_file.relative_to(wiki_dir)
            parts = rel_to_wiki.parts
            category = parts[0] if len(parts) > 1 else "general"

            # Extract content summary (skip frontmatter)
            body = _strip_frontmatter(content)
            summary = body[:500] if body else ""

            # Remove existing and re-index
            conn.execute("DELETE FROM memory_index WHERE id = ?", (entry_id,))
            conn.execute(
                """INSERT INTO memory_index
                (id, source_type, source_path, title, module, category, abstraction,
                 confidence, layer, content_summary, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    "wiki",
                    rel_path,
                    title,
                    category,
                    category,
                    metadata.get("abstraction"),
                    metadata.get("confidence", 0.5),
                    layer,
                    summary,
                    json.dumps(metadata.get("tags", []), ensure_ascii=False),
                    metadata.get("created_at", ""),
                    datetime.now().isoformat(),
                ),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


# --- Recall Indexing ---

def index_recall(project_dir: Path, db_path: str) -> int:
    """Index recall summaries into memory_index."""
    conn = _get_connection(db_path)
    count = 0

    recall_dirs = []
    for base in [".agent-flow/wiki/recall"]:
        d = project_dir / base
        if d.is_dir():
            recall_dirs.append(d)

    for recall_dir in recall_dirs:
        for md_file in recall_dir.glob("*.md"):
            if md_file.name == "INDEX.md":
                continue

            entry_id = f"recall-{md_file.stem}"

            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            metadata = _parse_frontmatter(content)
            title = metadata.get("task", md_file.stem)

            body = _strip_frontmatter(content)
            summary = body[:500] if body else ""

            conn.execute("DELETE FROM memory_index WHERE id = ?", (entry_id,))
            conn.execute(
                """INSERT INTO memory_index
                (id, source_type, source_path, title, module, category, abstraction,
                 confidence, layer, content_summary, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    "recall",
                    str(md_file.relative_to(project_dir)) if md_file.is_relative_to(project_dir) else str(md_file),
                    title,
                    "recall",
                    "session",
                    None,
                    metadata.get("confidence", 0.5),
                    "project",
                    summary,
                    json.dumps(metadata.get("experiences", []), ensure_ascii=False),
                    metadata.get("date", ""),
                    datetime.now().isoformat(),
                ),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


# --- Skills Indexing ---

def index_skills(project_dir: Path, db_path: str) -> int:
    """Index skill handler.md files into memory_index."""
    conn = _get_connection(db_path)
    count = 0

    skill_dirs = [(d, _determine_layer(d, project_dir)) for d in project_skills_dirs(project_dir)]

    # Global skills
    global_skills = Path.home() / ".agent-flow" / "skills"
    if global_skills.is_dir():
        skill_dirs.append((global_skills, "global"))

    for skill_dir, layer in skill_dirs:
        if not skill_dir.is_dir():
            continue

        for skill_subdir in skill_dir.iterdir():
            if not skill_subdir.is_dir():
                continue

            handler_file = skill_subdir / "handler.md"
            if not handler_file.is_file():
                continue

            skill_name = skill_subdir.name
            entry_id = f"skill-{skill_name}"

            try:
                content = handler_file.read_text(encoding="utf-8")
            except Exception:
                continue

            metadata = _parse_frontmatter(content)
            title = metadata.get("name", skill_name)
            description = metadata.get("description", "")

            body = _strip_frontmatter(content)
            summary = (description + "\n" + body)[:500] if description else body[:500]

            rel_path = str(handler_file.relative_to(project_dir)) if handler_file.is_relative_to(project_dir) else str(handler_file)

            conn.execute("DELETE FROM memory_index WHERE id = ?", (entry_id,))
            conn.execute(
                """INSERT INTO memory_index
                (id, source_type, source_path, title, module, category, abstraction,
                 confidence, layer, content_summary, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    "skill",
                    rel_path,
                    title,
                    skill_name,
                    "skill",
                    None,
                    0.8,
                    layer,
                    summary,
                    json.dumps(metadata.get("triggers", []), ensure_ascii=False),
                    "",
                    datetime.now().isoformat(),
                ),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


# --- Mtime Cache for Incremental Indexing ---

_MTIME_CACHE_FILENAME = "observations.db.mtime_cache"

# --- TTL Search Cache ---

# In-memory cache for search_index() results.
# Key: (db_path, query, source_type, category, limit)
# Value: list[dict] (search results)
_search_cache: dict[tuple, list[dict]] = {}

# Timestamps for each cache entry (monotonic time)
_cache_timestamps: dict[tuple, float] = {}

# Monotonic timestamp of last index_all() run; entries cached before this are stale
_last_index_time: float = 0.0

# Thread lock for cache access
_cache_lock = threading.Lock()

# --- TTL Mtime Scan Cache ---

# In-memory cache for get_source_mtimes() filesystem walk results.
# Avoids expensive glob + os.path.getmtime walks when called repeatedly
# within a short time window (e.g. on every UserPromptSubmit hook).
_last_mtime_scan_time: float = 0.0
_cached_source_mtimes: dict[str, str] = {}


def _get_mtime_scan_ttl() -> float:
    """Return the mtime scan TTL in seconds from env var, default 30."""
    try:
        return float(os.environ.get("AGENT_FLOW_MTIME_SCAN_INTERVAL", "30"))
    except (ValueError, TypeError):
        return 30.0


def _get_persisted_index_probe_ttl() -> float:
    """Return cross-process cache freshness window in seconds, default 5."""
    try:
        return float(os.environ.get("AGENT_FLOW_PERSISTED_INDEX_PROBE_TTL", "5"))
    except (ValueError, TypeError):
        return 5.0


def clear_mtime_scan_cache() -> None:
    """Clear the TTL-based mtime scan cache. Useful for testing and forced refresh."""
    global _last_mtime_scan_time, _cached_source_mtimes
    _last_mtime_scan_time = 0.0
    _cached_source_mtimes = {}


def ensure_index_ready(
    project_dir: Path,
    db_path: str | None = None,
    *,
    force_reindex: bool = False,
) -> tuple[int, str]:
    """Ensure the unified memory index is available with minimal churn.

    Returns ``(count, status)`` where status is one of:
    - ``reindexed``: a full rebuild occurred
    - ``persisted-cache-hit``: a recent persisted cache snapshot was reused
    - ``mtime-cache-hit``: ``index_all()`` confirmed source mtimes are unchanged

    On the fast path (persisted-cache-hit), **no filesystem walk is performed** —
    we only check the mtime cache file's own modification time.  This makes
    repeated calls from hooks (UserPromptSubmit) cheap even though the
    underlying ``get_source_mtimes()`` walk is relatively expensive.
    """
    if db_path is None:
        db_path = os.path.join(str(project_dir), ".agent-flow", "observations.db")

    cache_path = os.path.join(os.path.dirname(db_path), _MTIME_CACHE_FILENAME)

    # Fast path: if the mtime cache file itself was written recently, trust it
    # without walking the filesystem.  This avoids get_source_mtimes() entirely.
    if not force_reindex and os.path.isfile(db_path) and os.path.isfile(cache_path):
        try:
            cache_age = time.time() - os.path.getmtime(cache_path)
        except OSError:
            cache_age = _get_persisted_index_probe_ttl() + 1
        if cache_age <= _get_persisted_index_probe_ttl():
            cached = load_mtime_cache(cache_path)
            if isinstance(cached.get("last_count"), int):
                return cached["last_count"], "persisted-cache-hit"

    before = load_mtime_cache(cache_path) if os.path.isfile(cache_path) else {}
    count = index_all(project_dir, db_path, force_reindex=force_reindex)
    after = load_mtime_cache(cache_path) if os.path.isfile(cache_path) else {}
    if (
        not force_reindex
        and before
        and after
        and before.get("source_mtimes") == after.get("source_mtimes")
    ):
        return count, "mtime-cache-hit"
    return count, "reindexed"


def _get_cache_ttl() -> int:
    """Return the cache TTL in seconds from env var, default 60."""
    try:
        return int(os.environ.get("AGENT_FLOW_INDEX_CACHE_TTL", "60"))
    except (ValueError, TypeError):
        return 60


def _is_cache_disabled() -> bool:
    """Return True if search cache is disabled via env var."""
    return os.environ.get("AGENT_FLOW_INDEX_CACHE_DISABLED", "").lower() in (
        "1", "true", "yes",
    )


def _invalidate_search_cache() -> None:
    """Invalidate all search cache entries (called when index is rebuilt)."""
    global _last_index_time
    with _cache_lock:
        _search_cache.clear()
        _cache_timestamps.clear()
        _last_index_time = time.monotonic()


def load_mtime_cache(cache_path: str) -> dict:
    """Load the mtime cache JSON, returning empty dict if not found or corrupt."""
    if not os.path.isfile(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def save_mtime_cache(cache_path: str, cache: dict) -> None:
    """Write the mtime cache JSON atomically."""
    try:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        tmp_path = cache_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, cache_path)
    except OSError:
        pass


def get_source_mtimes(project_dir: Path) -> dict[str, str]:
    """Collect mtime strings for all indexable source files.

    Uses a TTL-based cache to avoid expensive filesystem walks
    when called repeatedly within a short time window.

    Returns a dict mapping relative (or absolute for global) file paths
    to ISO-format mtime strings.
    """
    global _last_mtime_scan_time, _cached_source_mtimes

    # Check TTL cache — return cached result if still fresh
    now = time.time()
    if _cached_source_mtimes and (now - _last_mtime_scan_time) < _get_mtime_scan_ttl():
        return _cached_source_mtimes

    mtimes: dict[str, str] = {}

    def _record(p: Path) -> None:
        try:
            mtime = os.path.getmtime(p)
            key = str(p.relative_to(project_dir)) if p.is_relative_to(project_dir) else str(p)
            mtimes[key] = datetime.fromtimestamp(mtime).isoformat()
        except OSError:
            pass

    # Soul.md files
    for pattern in [".agent-flow/memory/*/Soul.md"]:
        for p in project_dir.glob(pattern):
            _record(p)
    global_soul = Path.home() / ".agent-flow" / "memory" / "main" / "Soul.md"
    if global_soul.is_file():
        _record(global_soul)

    # Wiki files (excluding recall)
    for wiki_dir in project_wiki_dirs(project_dir):
        if wiki_dir.is_dir():
            for md_file in wiki_dir.rglob("*.md"):
                if md_file.name == "INDEX.md":
                    continue
                if "recall" in str(md_file.relative_to(wiki_dir)):
                    continue
                _record(md_file)
    global_wiki = Path.home() / ".agent-flow" / "wiki"
    if global_wiki.is_dir():
        for md_file in global_wiki.rglob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            if "recall" in str(md_file.relative_to(global_wiki)):
                continue
            _record(md_file)

    # Recall files
    for base in [".agent-flow/wiki/recall"]:
        recall_dir = project_dir / base
        if recall_dir.is_dir():
            for md_file in recall_dir.glob("*.md"):
                if md_file.name == "INDEX.md":
                    continue
                _record(md_file)

    # Skill handler.md files
    for skill_dir in project_skills_dirs(project_dir):
        if skill_dir.is_dir():
            for skill_subdir in skill_dir.iterdir():
                handler = skill_subdir / "handler.md"
                if handler.is_file():
                    _record(handler)
    global_skills = Path.home() / ".agent-flow" / "skills"
    if global_skills.is_dir():
        for skill_subdir in global_skills.iterdir():
            handler = skill_subdir / "handler.md"
            if handler.is_file():
                _record(handler)

    # Update TTL cache
    _last_mtime_scan_time = time.time()
    _cached_source_mtimes = mtimes

    return mtimes


# --- Unified Index ---

def index_all(project_dir: Path, db_path: str | None = None, *, force_reindex: bool = False) -> int:
    """Index all memory sources into SQLite.

    Uses mtime-based caching to skip re-indexing when no source files have
    changed since the last index run. If *force_reindex* is True, the cache
    is bypassed and a full reindex is performed.

    Returns total number of entries indexed.
    """
    if force_reindex:
        clear_mtime_scan_cache()

    if db_path is None:
        db_path = os.path.join(str(project_dir), ".agent-flow", "observations.db")

    # --- mtime-based incremental check ---
    cache_path = os.path.join(os.path.dirname(db_path), _MTIME_CACHE_FILENAME)
    current_mtimes = get_source_mtimes(project_dir)
    if not force_reindex and os.path.isfile(db_path):
        cached = load_mtime_cache(cache_path)
        if cached.get("source_mtimes") == current_mtimes:
            # All mtimes match — skip indexing
            return cached.get("last_count", 0)

    total = 0
    total += index_soul(project_dir, db_path)
    total += index_wiki(project_dir, db_path)
    total += index_recall(project_dir, db_path)
    total += index_skills(project_dir, db_path)

    # Invalidate search cache since the index has been rebuilt
    _invalidate_search_cache()

    # Persist mtime cache after successful indexing (re-snapshot post-index)
    new_cache = {
        "last_index_time": datetime.now().isoformat(),
        "source_mtimes": get_source_mtimes(project_dir),
        "last_count": total,
    }
    save_mtime_cache(cache_path, new_cache)

    return total


# --- Search ---

def search_index(
    db_path: str,
    query: str,
    source_type: str | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search the memory index using FTS5 full-text search.

    Results are cached in memory with a configurable TTL. The cache is
    automatically invalidated when ``index_all()`` rebuilds the index or
    when the TTL expires.
    """
    if not os.path.isfile(db_path):
        return []

    # --- TTL cache check ---
    if not _is_cache_disabled():
        cache_key = (db_path, query, source_type, category, limit)
        now = time.monotonic()
        ttl = _get_cache_ttl()

        with _cache_lock:
            if cache_key in _search_cache:
                cached_at = _cache_timestamps.get(cache_key, 0)
                # Valid if: TTL not expired AND cached after last index rebuild
                if (now - cached_at) < ttl and cached_at >= _last_index_time:
                    return _search_cache[cache_key]

    # --- Query SQLite ---
    conn = _get_connection(db_path)
    results = []

    try:
        fts_query = query.replace('"', '""')
        sql = """
            SELECT mi.* FROM memory_index mi
            JOIN memory_fts mf ON mi.rowid = mf.rowid
            WHERE memory_fts MATCH ?
        """
        params: list[Any] = [f'"{fts_query}"']

        if source_type:
            sql += " AND mi.source_type = ?"
            params.append(source_type)
        if category:
            sql += " AND mi.category = ?"
            params.append(category)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        for r in rows:
            results.append(dict(r))
    except sqlite3.OperationalError:
        # FTS table might not exist yet
        pass

    conn.close()

    # --- Store in cache ---
    if not _is_cache_disabled():
        with _cache_lock:
            _search_cache[cache_key] = results
            _cache_timestamps[cache_key] = time.monotonic()

    return results


# --- Helpers ---

def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}

    try:
        end = content.index("---", 3)
        fm_str = content[3:end].strip()
    except ValueError:
        return {}

    # Simple YAML parsing (avoid importing yaml for this)
    metadata = {}
    current_key = None
    current_list = []

    for line in fm_str.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item
        if stripped.startswith("- ") and current_key:
            current_list.append(stripped[2:].strip().strip('"').strip("'"))
            continue

        # Save previous list
        if current_key and current_list:
            metadata[current_key] = current_list
            current_list = []

        # Key-value pair
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if value:
                # Try to parse as number
                try:
                    value = float(value) if "." in value else int(value)
                except ValueError:
                    pass
                metadata[key] = value
            else:
                current_key = key
                current_list = []

    # Save last list
    if current_key and current_list:
        metadata[current_key] = current_list

    return metadata


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return content
    try:
        end = content.index("---", 3)
        return content[end + 3:].strip()
    except ValueError:
        return content
