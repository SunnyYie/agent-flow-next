"""Test framework detection — auto-detect and guide test framework installation.

Detects pytest, jest, vitest, rspec, go test, and other common frameworks.
When no framework is found, recommends one based on the project language.
"""

from pathlib import Path


# Test framework detection rules: (check_files, framework_name, test_command, language)
FRAMEWORK_RULES: list[tuple[list[str], str, str, str]] = [
    # Python
    (["pytest.ini", "conftest.py"], "pytest", "pytest", "python"),
    (["pyproject.toml"], "pytest", "pytest", "python"),  # Check content separately
    # Node.js — Jest
    (["jest.config.ts", "jest.config.js", "jest.config.mjs", "jest.config.cjs"], "jest", "npx jest", "nodejs"),
    # Node.js — Vitest
    (["vitest.config.ts", "vitest.config.js", "vitest.config.mjs"], "vitest", "npx vitest", "nodejs"),
    # Go
    (["go.mod"], "go-test", "go test ./...", "go"),
    # Ruby
    ([".rspec"], "rspec", "bundle exec rspec", "ruby"),
    # Rust
    (["Cargo.toml"], "cargo-test", "cargo test", "rust"),
]

# Recommended frameworks by language
RECOMMENDED_FRAMEWORKS: dict[str, tuple[str, str, str]] = {
    "python": ("pytest", "pip install pytest", "pytest"),
    "typescript": ("vitest", "npm install -D vitest", "npx vitest"),
    "nodejs": ("jest", "npm install -D jest", "npx jest"),
    "go": ("go-test", "(built-in)", "go test ./..."),
    "ruby": ("rspec", "bundle add rspec", "bundle exec rspec"),
    "rust": ("cargo-test", "(built-in)", "cargo test"),
}


class TestFrameworkInfo:
    """Detected test framework information."""

    def __init__(
        self,
        name: str,
        test_command: str,
        language: str,
        is_detected: bool = True,
        install_command: str = "",
    ) -> None:
        self.name = name
        self.test_command = test_command
        self.language = language
        self.is_detected = is_detected  # False if recommended but not yet installed
        self.install_command = install_command

    def __repr__(self) -> str:
        status = "detected" if self.is_detected else "recommended"
        return f"TestFrameworkInfo({self.name}, cmd={self.test_command}, {status})"


def detect_test_framework(project_dir: Path) -> TestFrameworkInfo:
    """Auto-detect the test framework used in a project.

    Priority:
    1. Check for framework-specific config files
    2. Check package.json / pyproject.toml for test dependencies
    3. Recommend based on project language

    Returns TestFrameworkInfo with detection status.
    """
    # Check each framework rule
    for check_files, fw_name, test_cmd, language in FRAMEWORK_RULES:
        for filename in check_files:
            filepath = project_dir / filename
            if not filepath.exists():
                continue

            # Special handling: pyproject.toml needs content check
            if filename == "pyproject.toml":
                if _has_pytest_config(filepath):
                    return TestFrameworkInfo(fw_name, test_cmd, language)
                continue

            return TestFrameworkInfo(fw_name, test_cmd, language)

    # Check package.json for test frameworks
    package_json = project_dir / "package.json"
    if package_json.exists():
        info = _check_package_json(package_json)
        if info:
            return info

    # Check pyproject.toml for pytest in dependencies
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        if _has_pytest_dep(pyproject):
            return TestFrameworkInfo("pytest", "pytest", "python")

    # Fallback: detect language and recommend
    language = _detect_project_language(project_dir)
    if language in RECOMMENDED_FRAMEWORKS:
        fw_name, install_cmd, test_cmd = RECOMMENDED_FRAMEWORKS[language]
        return TestFrameworkInfo(
            name=fw_name,
            test_command=test_cmd,
            language=language,
            is_detected=False,
            install_command=install_cmd,
        )

    # Unknown
    return TestFrameworkInfo("unknown", "", "unknown", is_detected=False)


def _has_pytest_config(pyproject: Path) -> bool:
    """Check if pyproject.toml has pytest configuration."""
    try:
        content = pyproject.read_text(encoding="utf-8")
        return "[tool.pytest" in content
    except Exception:
        return False


def _has_pytest_dep(pyproject: Path) -> bool:
    """Check if pyproject.toml lists pytest as a dependency."""
    try:
        content = pyproject.read_text(encoding="utf-8")
        return "pytest" in content.lower()
    except Exception:
        return False


def _check_package_json(package_json: Path) -> TestFrameworkInfo | None:
    """Check package.json for test framework dependencies."""
    import json

    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    dep_names_lower = {d.lower() for d in all_deps}

    # Check for specific test frameworks
    if "vitest" in dep_names_lower:
        return TestFrameworkInfo("vitest", "npx vitest", "nodejs")
    if "jest" in dep_names_lower:
        return TestFrameworkInfo("jest", "npx jest", "nodejs")
    if "mocha" in dep_names_lower:
        return TestFrameworkInfo("mocha", "npx mocha", "nodejs")

    # Check scripts for test commands
    scripts = data.get("scripts", {})
    test_script = scripts.get("test", "")
    if "vitest" in test_script:
        return TestFrameworkInfo("vitest", "npx vitest", "nodejs")
    if "jest" in test_script:
        return TestFrameworkInfo("jest", "npx jest", "nodejs")

    return None


def _detect_project_language(project_dir: Path) -> str:
    """Detect the primary language of the project for framework recommendation."""
    # Python indicators
    if (project_dir / "pyproject.toml").exists() or (project_dir / "setup.py").exists():
        return "python"

    # Node.js / TypeScript
    if (project_dir / "package.json").exists():
        if (project_dir / "tsconfig.json").exists():
            return "typescript"
        return "nodejs"

    # Go
    if (project_dir / "go.mod").exists():
        return "go"

    # Ruby
    if (project_dir / "Gemfile").exists():
        return "ruby"

    # Rust
    if (project_dir / "Cargo.toml").exists():
        return "rust"

    return "unknown"
