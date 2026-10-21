"""Fail closed on forbidden dependency edges in Python source.

Run from repository root: python scripts/check_architecture.py
Checks all Python files under packages/evidence_kernel; handles import and
from-import syntax, including absolute imports and common dynamic imports.
This is a guardrail, not a substitute for code review.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "packages" / "evidence_kernel"
FORBIDDEN = ("domains", "apps", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic")
errors: list[str] = []

for file in sorted(KERNEL.rglob("*.py")):
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    except (SyntaxError, UnicodeError) as exc:
        errors.append(f"{file.relative_to(ROOT)}: invalid source: {exc}")
        continue
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
            if node.level:
                # Kernel-relative imports are allowed.
                continue
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                modules = [node.args[0].value]
            else:
                errors.append(f"{file.relative_to(ROOT)}:{node.lineno}: dynamic __import__ requires review")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                modules = [node.args[0].value]
            else:
                errors.append(f"{file.relative_to(ROOT)}:{node.lineno}: dynamic import_module requires review")
        for module in modules:
            if module.split(".")[0] in FORBIDDEN:
                errors.append(f"{file.relative_to(ROOT)}:{node.lineno}: forbidden kernel dependency: {module}")
if errors:
    raise SystemExit("\n".join(errors))
print("Architecture boundary: PASS")
