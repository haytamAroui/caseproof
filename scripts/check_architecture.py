"""Enforce pragmatic hexagonal dependency direction (Python 3.11+).

Only forbid cross-boundary imports; do not require one port per class or
prescribe directories, frameworks, or deployment topology.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "packages/evidence_kernel": {"domains", "apps", "application", "infrastructure", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
    "domains/finance": {"apps", "application", "infrastructure", "domains.disputes", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
    "domains/disputes": {"apps", "application", "infrastructure", "domains.finance", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
    "application": {"apps", "infrastructure", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
}


def forbidden(module: str, banned: set[str]) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in banned)


def scan_source(source: str, *, filename: str, banned: set[str]) -> list[str]:
    """Return boundary violations; literal dynamic imports are checked too."""
    try:
        tree = ast.parse(source, filename=filename)
    except (SyntaxError, UnicodeError) as exc:
        return [f"{filename}: invalid Python: {exc}"]

    errors: list[str] = []
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            # Relative imports stay within their current package by convention.
            # Cross-package relative imports should be rejected by package-level
            # review; do not guess the resolved module from an isolated snippet.
            if not node.level:
                modules = [node.module or ""]
        elif isinstance(node, ast.Call):
            dynamic = (
                isinstance(node.func, ast.Name) and node.func.id == "__import__"
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            )
            if dynamic:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    modules = [node.args[0].value]
                else:
                    errors.append(f"{filename}:{node.lineno}: nonliteral dynamic import requires review")
        for module in modules:
            if forbidden(module, banned):
                errors.append(f"{filename}:{node.lineno}: forbidden import {module}")
    return errors


def check(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for folder, banned in RULES.items():
        for path in sorted((root / folder).rglob("*.py")):
            relative = str(path.relative_to(root))
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeError as exc:
                errors.append(f"{relative}: invalid Python: {exc}")
                continue
            errors.extend(scan_source(source, filename=relative, banned=banned))
    return errors


if __name__ == "__main__":
    violations = check()
    if violations:
        raise SystemExit("\n".join(violations))
    print("Architecture boundary: PASS")
