"""Project analyzer — detect tech stack, environment, and structure."""

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import re
import subprocess


@dataclass
class ProjectAnalysis:
    """Detected project properties."""

    project_root: Path
    language: str = ""              # "python", "nodejs", "rust", "go", "polyglot"
    language_version: str = ""      # "3.13", "22.x"
    package_manager: str = ""       # "uv", "poetry", "pip", "npm", "pnpm", "yarn"
    venv_path: str = ""             # absolute path to venv bin
    framework: str = ""             # "fastapi", "nextjs", "", etc.
    test_command: str = ""          # absolute test command
    lint_command: str = ""          # absolute lint command
    format_command: str = ""        # absolute format command
    build_command: str = ""         # build command
    project_structure: str = ""     # "standard", "monorepo", "src-layout"
    source_dir: str = ""            # "src/", "lib/", package name
    languages: list[str] = field(default_factory=list)  # for polyglot
    directory_tags: dict[str, list[str]] = field(default_factory=dict)
    # Maps: relative_dir_path -> list of tags
    # e.g., {"rn/page/content/pages/company-circle": ["同事圈", "公司圈"]}


def analyze_project(project_dir: Path) -> ProjectAnalysis:
    """Analyze project directory to detect tech stack and environment.

    Detection is non-interactive and deterministic: checks file existence,
    parses config files, and runs version commands when safe.
    """
    analysis = ProjectAnalysis(project_root=project_dir)
    languages: list[str] = []

    # Detect each language
    has_python = _detect_python(project_dir, analysis)
    if has_python:
        languages.append("python")

    has_nodejs = _detect_nodejs(project_dir, analysis)
    if has_nodejs:
        # _detect_nodejs sets analysis.language to "typescript" or "nodejs"
        languages.append(analysis.language)

    has_rust = _detect_rust(project_dir, analysis)
    if has_rust:
        languages.append("rust")

    has_go = _detect_go(project_dir, analysis)
    if has_go:
        languages.append("go")

    analysis.languages = languages
    if len(languages) == 1:
        analysis.language = languages[0]
    elif len(languages) > 1:
        analysis.language = "polyglot"
        # Primary language is the first detected
    else:
        analysis.language = "unknown"

    # Detect project structure
    _detect_structure(project_dir, analysis)

    # Detect source directory
    _detect_source_dir(project_dir, analysis)

    # Scan directory structure and generate tag mappings
    _scan_project_structure(project_dir, analysis)

    return analysis


# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------


def _detect_python(project_dir: Path, analysis: ProjectAnalysis) -> bool:
    """Detect Python project and fill analysis fields."""
    pyproject = project_dir / "pyproject.toml"
    setup_py = project_dir / "setup.py"
    requirements = project_dir / "requirements.txt"

    if not (pyproject.exists() or setup_py.exists() or requirements.exists()):
        return False

    # Package manager
    if (project_dir / "uv.lock").exists():
        analysis.package_manager = "uv"
    elif (project_dir / "poetry.lock").exists():
        analysis.package_manager = "poetry"
    elif (project_dir / "Pipfile.lock").exists():
        analysis.package_manager = "pipenv"
    else:
        analysis.package_manager = "pip"

    # Language version
    analysis.language_version = _get_python_version(project_dir, pyproject)

    # Virtual environment path
    analysis.venv_path = _find_venv(project_dir)

    # Framework
    analysis.framework = _detect_python_framework(project_dir, pyproject)

    # Test command
    analysis.test_command = _detect_python_test(project_dir, pyproject, analysis.venv_path)

    # Lint command
    analysis.lint_command = _detect_python_lint(project_dir, pyproject, analysis.venv_path)

    # Format command
    analysis.format_command = _detect_python_format(project_dir, pyproject, analysis.venv_path)

    # Build command
    analysis.build_command = _detect_python_build(project_dir, pyproject, analysis.venv_path)

    return True


def _get_python_version(project_dir: Path, pyproject: Path) -> str:
    """Get Python version from pyproject.toml or runtime."""
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            # Extract version number from spec like ">=3.11" or "==3.13.*"
            version_match = re.search(r"(\d+\.\d+)", match.group(1))
            if version_match:
                return version_match.group(1)

    # Fallback: run python3 --version
    try:
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.search(r"(\d+\.\d+)", result.stdout)
        if match:
            return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return ""


def _find_venv(project_dir: Path) -> str:
    """Find virtual environment path (absolute)."""
    for venv_dir in [".venv", "venv", ".env"]:
        venv_path = project_dir / venv_dir
        if venv_path.is_dir():
            bin_dir = venv_path / "bin"
            if bin_dir.is_dir():
                return str(bin_dir.resolve()) + "/"
            scripts_dir = venv_path / "Scripts"
            if scripts_dir.is_dir():
                return str(scripts_dir.resolve()) + "\\"
    return ""


def _detect_python_framework(project_dir: Path, pyproject: Path) -> str:
    """Detect Python framework from dependencies."""
    deps = _read_python_deps(project_dir, pyproject)
    dep_names_lower = {d.lower() for d in deps}

    frameworks = [
        ("fastapi", "fastapi"),
        ("django", "django"),
        ("flask", "flask"),
        ("langchain", "langchain"),
        ("langgraph", "langgraph"),
        ("starlette", "starlette"),
        ("pydantic-ai", "pydantic-ai"),
        ("litestar", "litestar"),
        ("sanic", "sanic"),
        ("aiohttp", "aiohttp"),
    ]
    for dep_name, fw_name in frameworks:
        if dep_name in dep_names_lower:
            return fw_name
    return ""


def _read_python_deps(project_dir: Path, pyproject: Path) -> list[str]:
    """Read Python dependency names from config files."""
    deps: list[str] = []

    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        # Parse [project] dependencies (PEP 621)
        # Handle both multi-line and single-line formats:
        #   dependencies = ["fastapi", "pytest"]
        #   dependencies = [\n    "fastapi",\n    "pytest",\n  ]
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if not in_deps:
                # Look for dependencies = [ anywhere on the line
                if "dependencies" in stripped and "= [" in stripped:
                    in_deps = True
                    # Extract deps from the same line (single-line format)
                    bracket_content = stripped[stripped.index("[") + 1 :]
                    for dep_match in re.finditer(r'"([a-zA-Z0-9._-]+)"', bracket_content):
                        deps.append(dep_match.group(1).split(".")[0])  # Take root package name
                    if "]" in bracket_content:
                        in_deps = False
                    continue
            if in_deps:
                if "]" in stripped:
                    # Extract any remaining deps before the closing bracket
                    before_bracket = stripped[: stripped.index("]")]
                    for dep_match in re.finditer(r'"([a-zA-Z0-9._-]+)"', before_bracket):
                        deps.append(dep_match.group(1).split(".")[0])
                    break
                # Extract package name from dependency spec
                for dep_match in re.finditer(r'"([a-zA-Z0-9._-]+)"', stripped):
                    deps.append(dep_match.group(1).split(".")[0])

    # Also check requirements.txt
    req_file = project_dir / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                match = re.match(r"([a-zA-Z0-9_-]+)", line)
                if match:
                    deps.append(match.group(1))

    return deps


def _detect_python_test(project_dir: Path, pyproject: Path, venv_path: str) -> str:
    """Detect test command."""
    if venv_path:
        pytest = Path(venv_path) / "pytest"
        if pytest.exists():
            return f"{venv_path}pytest"

    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[tool.pytest" in content:
            if venv_path:
                return f"{venv_path}pytest"
            return "pytest"

    # Check if pytest is in dependencies
    deps = _read_python_deps(project_dir, pyproject)
    if "pytest" in [d.lower() for d in deps]:
        if venv_path:
            return f"{venv_path}pytest"
        return "pytest"

    return "python -m unittest"


def _detect_python_lint(project_dir: Path, pyproject: Path, venv_path: str) -> str:
    """Detect lint command."""
    # Check for ruff first (most common modern choice)
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[tool.ruff" in content:
            if venv_path:
                return f"{venv_path}ruff check"
            return "ruff check"

    deps = _read_python_deps(project_dir, pyproject)
    dep_names_lower = {d.lower() for d in deps}

    if "ruff" in dep_names_lower:
        if venv_path:
            return f"{venv_path}ruff check"
        return "ruff check"

    if "flake8" in dep_names_lower:
        if venv_path:
            return f"{venv_path}flake8"
        return "flake8"

    if "pylint" in dep_names_lower:
        if venv_path:
            return f"{venv_path}pylint"
        return "pylint"

    return ""


def _detect_python_format(project_dir: Path, pyproject: Path, venv_path: str) -> str:
    """Detect format command."""
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[tool.ruff" in content:
            if venv_path:
                return f"{venv_path}ruff format"
            return "ruff format"

    deps = _read_python_deps(project_dir, pyproject)
    dep_names_lower = {d.lower() for d in deps}

    if "ruff" in dep_names_lower:
        if venv_path:
            return f"{venv_path}ruff format"
        return "ruff format"

    if "black" in dep_names_lower:
        if venv_path:
            return f"{venv_path}black"
        return "black"

    return ""


def _detect_python_build(project_dir: Path, pyproject: Path, venv_path: str) -> str:
    """Detect build command."""
    if venv_path:
        return f"{venv_path}python -m build"
    return "python -m build"


# ---------------------------------------------------------------------------
# Node.js detection
# ---------------------------------------------------------------------------


def _has_typescript(project_dir: Path, pkg: dict) -> bool:
    """Detect if a Node.js project uses TypeScript."""
    # Check for tsconfig.json
    if (project_dir / "tsconfig.json").exists():
        return True

    # Check devDependencies for typescript
    dev_deps = {d.lower() for d in pkg.get("devDependencies", {})}
    if "typescript" in dev_deps:
        return True

    # Monorepo: check sub-packages for tsconfig.json
    packages_dir = project_dir / "packages"
    if packages_dir.is_dir():
        for sub_pkg in packages_dir.iterdir():
            if sub_pkg.is_dir() and (sub_pkg / "tsconfig.json").exists():
                return True

    return False


def _detect_nodejs(project_dir: Path, analysis: ProjectAnalysis) -> bool:
    """Detect Node.js project and fill analysis fields."""
    package_json = project_dir / "package.json"
    if not package_json.exists():
        return False

    try:
        pkg = json.loads(package_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

    # Package manager
    if (project_dir / "pnpm-lock.yaml").exists():
        analysis.package_manager = "pnpm"
    elif (project_dir / "yarn.lock").exists():
        analysis.package_manager = "yarn"
    else:
        analysis.package_manager = "npm"

    # Language version
    engines = pkg.get("engines", {})
    node_version = engines.get("node", "")
    if node_version:
        match = re.search(r"(\d+)", node_version)
        if match:
            analysis.language_version = match.group(1) + ".x"
    else:
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            match = re.search(r"v(\d+\.\d+)", result.stdout)
            if match:
                analysis.language_version = match.group(1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Detect TypeScript usage
    if _has_typescript(project_dir, pkg):
        analysis.language = "typescript"
    else:
        analysis.language = "nodejs"

    # Framework
    analysis.framework = _detect_nodejs_framework(project_dir, pkg)

    # Commands from scripts
    scripts = pkg.get("scripts", {})
    bin_prefix = "npx " if analysis.package_manager == "npm" else f"{analysis.package_manager} "

    if "test" in scripts:
        analysis.test_command = f"{analysis.package_manager} test"
    if "lint" in scripts:
        analysis.lint_command = f"{analysis.package_manager} run lint"
    if "format" in scripts:
        analysis.format_command = f"{analysis.package_manager} run format"
    if "build" in scripts:
        analysis.build_command = f"{analysis.package_manager} run build"

    # venv_path equivalent for Node.js
    node_modules_bin = project_dir / "node_modules" / ".bin"
    if node_modules_bin.is_dir():
        analysis.venv_path = str(node_modules_bin) + "/"

    return True


def _detect_nodejs_framework(project_dir: Path, pkg: dict) -> str:
    """Detect Node.js framework from dependencies and config files.

    For monorepo projects, scans packages/* subdirectories to detect
    frameworks used in each sub-package, returning a comma-separated list.
    """
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    # Check config files first (more reliable)
    if list(project_dir.glob("next.config.*")):
        return "nextjs"
    if list(project_dir.glob("nuxt.config.*")):
        return "nuxt"
    if list(project_dir.glob("vite.config.*")):
        return "vite"
    if list(project_dir.glob("remix.config.*")):
        return "remix"

    # Check root dependencies
    dep_names_lower = {d.lower() for d in deps}
    frameworks = [
        ("react", "react"),
        ("vue", "vue"),
        ("svelte", "svelte"),
        ("express", "express"),
        ("koa", "koa"),
        ("fastify", "fastify"),
        ("nestjs", "nestjs"),
        ("@hono/node-server", "hono"),
    ]
    for dep_name, fw_name in frameworks:
        if dep_name in dep_names_lower:
            return fw_name

    # Monorepo: scan packages/* subdirectories
    packages_dir = project_dir / "packages"
    if packages_dir.is_dir():
        found_frameworks: list[str] = []
        for sub_pkg in sorted(packages_dir.iterdir()):
            if not sub_pkg.is_dir():
                continue
            sub_pkg_json = sub_pkg / "package.json"
            if not sub_pkg_json.exists():
                continue
            try:
                sub_pkg_data = json.loads(sub_pkg_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # Check sub-package config files
            if list(sub_pkg.glob("next.config.*")):
                if "nextjs" not in found_frameworks:
                    found_frameworks.append("nextjs")
                continue
            if list(sub_pkg.glob("nuxt.config.*")):
                if "nuxt" not in found_frameworks:
                    found_frameworks.append("nuxt")
                continue
            if list(sub_pkg.glob("vite.config.*")):
                if "vite" not in found_frameworks:
                    found_frameworks.append("vite")
                continue

            # Check sub-package dependencies
            sub_deps = {
                **sub_pkg_data.get("dependencies", {}),
                **sub_pkg_data.get("devDependencies", {}),
            }
            sub_dep_names_lower = {d.lower() for d in sub_deps}
            for dep_name, fw_name in frameworks:
                if dep_name in sub_dep_names_lower and fw_name not in found_frameworks:
                    found_frameworks.append(fw_name)

        if found_frameworks:
            return ", ".join(found_frameworks)

    return ""


# ---------------------------------------------------------------------------
# Rust detection
# ---------------------------------------------------------------------------


def _detect_rust(project_dir: Path, analysis: ProjectAnalysis) -> bool:
    """Detect Rust project."""
    cargo_toml = project_dir / "Cargo.toml"
    if not cargo_toml.exists():
        return False

    analysis.package_manager = "cargo"
    analysis.test_command = "cargo test"
    analysis.lint_command = "cargo clippy"
    analysis.format_command = "cargo fmt"
    analysis.build_command = "cargo build"

    # Try to get Rust version
    try:
        result = subprocess.run(
            ["rustc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.search(r"(\d+\.\d+)", result.stdout)
        if match:
            analysis.language_version = match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return True


# ---------------------------------------------------------------------------
# Go detection
# ---------------------------------------------------------------------------


def _detect_go(project_dir: Path, analysis: ProjectAnalysis) -> bool:
    """Detect Go project."""
    go_mod = project_dir / "go.mod"
    if not go_mod.exists():
        return False

    analysis.package_manager = "go"
    analysis.test_command = "go test ./..."
    analysis.lint_command = "golangci-lint run"
    analysis.build_command = "go build ./..."

    try:
        result = subprocess.run(
            ["go", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.search(r"go(\d+\.\d+)", result.stdout)
        if match:
            analysis.language_version = match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return True


# ---------------------------------------------------------------------------
# Project structure detection
# ---------------------------------------------------------------------------


def _detect_structure(project_dir: Path, analysis: ProjectAnalysis) -> None:
    """Detect project structure type."""
    # Monorepo indicators
    package_json = project_dir / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text(encoding="utf-8"))
            if "workspaces" in pkg:
                analysis.project_structure = "monorepo"
                return
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    pnpm_workspace = project_dir / "pnpm-workspace.yaml"
    if pnpm_workspace.exists():
        analysis.project_structure = "monorepo"
        return

    lerna_json = project_dir / "lerna.json"
    if lerna_json.exists():
        analysis.project_structure = "monorepo"
        return

    # Python monorepo
    if (project_dir / "packages").is_dir() and (project_dir / "pyproject.toml").exists():
        analysis.project_structure = "monorepo"
        return

    # src-layout (Python)
    if (project_dir / "src").is_dir() and (project_dir / "pyproject.toml").exists():
        analysis.project_structure = "src-layout"
        return

    analysis.project_structure = "standard"


def _detect_source_dir(project_dir: Path, analysis: ProjectAnalysis) -> None:
    """Detect primary source directory."""
    # Check common source directory names
    for candidate in ["src", "lib", "app", "aw"]:
        if (project_dir / candidate).is_dir():
            analysis.source_dir = candidate + "/"
            return

    # For Python, try to find package directory from pyproject.toml
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        # Look for [tool.setuptools.packages.find] where = "src"
        match = re.search(r'where\s*=\s*\["([^"]+)"\]', content)
        if match:
            analysis.source_dir = match.group(1) + "/"
            return

        # Try to find package name from [project] name
        match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            pkg_name = match.group(1).replace("-", "_")
            if (project_dir / pkg_name).is_dir():
                analysis.source_dir = pkg_name + "/"
                return

    # For Node.js, common directories
    for candidate in ["pages", "components", "routes"]:
        if (project_dir / candidate).is_dir():
            analysis.source_dir = candidate + "/"
            return

    analysis.source_dir = ""


# ---------------------------------------------------------------------------
# Directory tag scanning
# ---------------------------------------------------------------------------


# Common directory-name-to-tag heuristics
DIRECTORY_TAG_HEURISTICS: dict[str, list[str]] = {
    # Social / community
    "company_circle": ["同事圈", "公司圈"],
    "company-circle": ["同事圈", "公司圈"],
    "gossip": ["职言", "匿名圈"],
    "circle": ["圈子"],
    "community": ["社区"],
    "forum": ["论坛"],
    # Career / job
    "job": ["职位", "招聘"],
    "internship": ["实习"],
    "recruit": ["招聘"],
    "career": ["职业"],
    # Features
    "wish": ["许愿卡"],
    "feed": ["动态", "信息流"],
    "moment": ["动态"],
    "content": ["内容"],
    "search": ["搜索"],
    "profile": ["个人主页"],
    "login": ["登录", "认证"],
    "auth": ["认证", "授权"],
    "setting": ["设置"],
    "notification": ["通知"],
    "message": ["消息"],
    "chat": ["聊天"],
    "payment": ["支付"],
    "order": ["订单"],
    "user": ["用户"],
    "home": ["首页"],
    "main": ["主页"],
    "network": ["人脉"],
    "major": ["专业"],
    "profession": ["职业"],
    "headline": ["头条"],
    "collection": ["收藏"],
    "contact": ["通讯录"],
    "member": ["会员"],
    "platform": ["平台"],
    "playground": ["调试"],
    "vajra": ["金刚位"],
    "banner": ["横幅", "Banner"],
    "tab": ["标签页"],
    "modal": ["弹窗"],
    "detail": ["详情"],
    "list": ["列表"],
    "form": ["表单"],
    "card": ["卡片"],
    "combo": ["组合圈"],
    "combination": ["组合圈"],
}

# Directories to skip during scanning
SKIP_DIRS = {
    "node_modules", ".git", "build", "dist", "__tests__", "__test__",
    "test", "tests", ".next", ".nuxt", "coverage", ".cache", "vendor",
    "target", "bin", "obj", ".tox", ".mypy_cache", ".pytest_cache",
    "egg-info", ".eggs", "static", "public", "assets", "images",
    "fonts", "icons", "styles", ".claude",
}

MAX_SCAN_DEPTH = 4


def _scan_project_structure(
    project_dir: Path,
    analysis: ProjectAnalysis,
    user_tags: dict[str, list[str]] | None = None,
) -> None:
    """Scan project directory structure and generate tag mappings.

    Scans within the detected source_dir, inferring tags from directory
    names using DIRECTORY_TAG_HEURISTICS. User-provided tags from
    .agent-flow/config.yaml are merged with priority.

    Args:
        project_dir: Project root directory.
        analysis: ProjectAnalysis to populate directory_tags on.
        user_tags: User-provided tag overrides from config.yaml.
    """
    # Determine scan roots
    scan_roots: list[Path] = []
    if analysis.source_dir:
        root = project_dir / analysis.source_dir.rstrip("/")
        if root.is_dir():
            scan_roots.append(root)

    # Also scan top-level directories that look like source dirs
    for candidate in ["rn", "app", "pages", "src", "lib"]:
        candidate_path = project_dir / candidate
        if candidate_path.is_dir() and candidate_path not in scan_roots:
            # Only add if it's not already covered by source_dir
            if not analysis.source_dir or not (
                str(candidate_path).startswith(
                    str(project_dir / analysis.source_dir.rstrip("/"))
                )
            ):
                scan_roots.append(candidate_path)

    if not scan_roots:
        # Fallback: scan project root itself
        scan_roots = [project_dir]

    tags: dict[str, list[str]] = {}

    for scan_root in scan_roots:
        root_depth = len(scan_root.parts)
        for dirpath, dirnames, filenames in os.walk(scan_root):
            # Calculate depth relative to scan root
            current_depth = len(Path(dirpath).parts) - root_depth
            if current_depth > MAX_SCAN_DEPTH:
                dirnames.clear()
                continue

            # Skip unwanted directories
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]

            rel = os.path.relpath(dirpath, project_dir)
            if rel == ".":
                continue

            dir_name = os.path.basename(dirpath)
            inferred = _infer_tags_for_dir(dir_name, filenames)
            if inferred:
                tags[rel] = inferred

    # Merge user-provided tags (priority)
    if user_tags:
        for dir_path, user_tag_list in user_tags.items():
            if dir_path in tags:
                # Merge: user tags first, then inferred tags not already present
                merged = list(user_tag_list)
                for t in tags[dir_path]:
                    if t not in merged:
                        merged.append(t)
                tags[dir_path] = merged
            else:
                tags[dir_path] = user_tag_list

    analysis.directory_tags = tags


def _infer_tags_for_dir(dir_name: str, filenames: list[str]) -> list[str]:
    """Infer tags for a directory based on its name and file contents.

    Uses DIRECTORY_TAG_HEURISTICS for name-based matching, and checks
    component filenames for additional domain hints.
    """
    tags: list[str] = []

    # Check directory name against heuristics (try variants)
    name_variants = [dir_name, dir_name.replace("-", "_"), dir_name.replace("_", "-")]
    for variant in name_variants:
        if variant.lower() in DIRECTORY_TAG_HEURISTICS:
            tags.extend(DIRECTORY_TAG_HEURISTICS[variant.lower()])
            break

    # Check component filenames for domain hints
    for fname in filenames[:20]:  # Sample first 20 files
        fname_lower = fname.lower()
        if "vajra" in fname_lower and "金刚位" not in tags:
            tags.append("金刚位")
        if "banner" in fname_lower and "横幅" not in tags and "Banner" not in tags:
            tags.append("Banner")

    return list(dict.fromkeys(tags))  # Deduplicate preserving order
