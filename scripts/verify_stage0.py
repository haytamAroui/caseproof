"""Stage 0 verification without uv, package registry, or GitHub Actions.

Run: python scripts/verify_stage0.py
This does not install dependencies or claim a locked environment.
"""
from __future__ import annotations

import compileall
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(label: str, args: list[str]) -> bool:
    print(f"\n=== {label} ===", flush=True)
    result = subprocess.run(args, cwd=ROOT, check=False)
    print(f"{label}: exit={result.returncode}", flush=True)
    return result.returncode == 0


def main() -> int:
    print(f"Python: {sys.version.split()[0]}", flush=True)
    print("Mode: independent Stage 0 checks (unlocked)", flush=True)
    ok = execute("architecture", [sys.executable, "scripts/check_architecture.py"])
    compiled = compileall.compile_dir(str(ROOT / "packages"), quiet=1)
    compiled &= compileall.compile_dir(str(ROOT / "domains"), quiet=1)
    compiled &= compileall.compile_dir(str(ROOT / "apps"), quiet=1)
    print(f"compileall: {'PASS' if compiled else 'FAIL'}", flush=True)
    ok = bool(compiled) and ok
    if importlib.util.find_spec("pytest") is None:
        print("pytest: BLOCKED (not installed)", flush=True)
        ok = False
    else:
        ok = execute("pytest", [sys.executable, "-m", "pytest", "-q"]) and ok
    for name in ("ruff", "mypy"):
        if importlib.util.find_spec(name) is None:
            print(f"{name}: BLOCKED (not installed)", flush=True)
            ok = False
        else:
            cmd = [sys.executable, "-m", name]
            cmd += ["check", "."] if name == "ruff" else ["packages/evidence_kernel"]
            ok = execute(name, cmd) and ok
    print(f"Stage 0 independent checks: {'PASS' if ok else 'INCOMPLETE OR FAILED'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
