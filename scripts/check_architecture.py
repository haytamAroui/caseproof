"""Enforce dependency direction; run with Python 3.11+."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "packages/evidence_kernel": {"domains", "apps", "application", "infrastructure", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
    "domains/finance": {"apps", "application", "infrastructure", "domains.disputes", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
    "domains/disputes": {"apps", "application", "infrastructure", "domains.finance", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
    # The application layer owns use-case coordination and abstract ports.
    # It must not import concrete delivery frameworks or infrastructure.
    "application": {"apps", "infrastructure", "fastapi", "supabase", "redis", "sqlalchemy", "openai", "anthropic"},
}
errors = []

def forbidden(module: str, banned: set[str]) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in banned)

for folder, banned in RULES.items():
    for path in sorted((ROOT / folder).rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid Python: {exc}")
            continue
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                modules = [node.module or ""]
            elif isinstance(node, ast.Call):
                dynamic = (
                    isinstance(node.func, ast.Name) and node.func.id == "__import__"
                ) or (
                    isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
                )
                if dynamic:
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        modules = [node.args[0].value]
                    else:
                        errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: nonliteral dynamic import requires review")
            for module in modules:
                if forbidden(module, banned):
                    errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: forbidden import {module}")

if errors:
    raise SystemExit("\n".join(errors))
print("Architecture boundary: PASS")
