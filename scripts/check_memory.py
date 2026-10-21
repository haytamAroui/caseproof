#!/usr/bin/env python3
"""Validate CaseProof's durable task log and require memory updates for code changes."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = "docs/memory/tasks.jsonl"
WORKING = "MEMORY.md"
REQUIRED = {"schema_version", "event_id", "task_id", "status", "summary", "branch", "commits", "pr_url", "tests", "next_action"}
STATUSES = {"planned", "in_progress", "blocked", "in_review", "merged", "verified", "reverted"}
CODE_PREFIXES = ("backend/", "frontend/", "infra/", "src/", "tests/", "scripts/")
CODE_FILES = {"Makefile", "pyproject.toml", "uv.lock", "package.json", "package-lock.json"}
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).splitlines()

def validate():
    path = ROOT / LOG
    if not path.exists():
        raise ValueError(f"Missing {LOG}")
    events = []
    ids = set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{LOG}:{n}: blank line")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{LOG}:{n}: invalid JSON: {exc}") from exc
        if not isinstance(event, dict) or REQUIRED - event.keys():
            raise ValueError(f"{LOG}:{n}: missing required fields: {sorted(REQUIRED - event.keys()) if isinstance(event, dict) else 'not an object'}")
        if event["schema_version"] != 1 or event["status"] not in STATUSES:
            raise ValueError(f"{LOG}:{n}: invalid schema version or status")
        if not all(isinstance(event[k], str) and event[k].strip() for k in ("event_id", "task_id", "summary", "branch", "next_action")):
            raise ValueError(f"{LOG}:{n}: empty required string")
        if event["event_id"] in ids:
            raise ValueError(f"{LOG}:{n}: duplicate event_id")
        ids.add(event["event_id"])
        if not isinstance(event["commits"], list) or any(not isinstance(s, str) or not HEX_SHA.fullmatch(s) for s in event["commits"]):
            raise ValueError(f"{LOG}:{n}: commits must be full 40-character SHAs")
        if event["pr_url"] is not None and not isinstance(event["pr_url"], str):
            raise ValueError(f"{LOG}:{n}: pr_url must be string or null")
        if not isinstance(event["tests"], list):
            raise ValueError(f"{LOG}:{n}: tests must be a list")
        events.append(event)
    if not events:
        raise ValueError(f"{LOG}: at least one event required")
    if not (ROOT / WORKING).exists():
        raise ValueError(f"Missing {WORKING}")
    if len((ROOT / WORKING).read_text(encoding="utf-8").splitlines()) > 150:
        raise ValueError(f"{WORKING} exceeds 150 lines; compact it")
    return events

def changed_files(mode, base):
    if mode == "staged":
        return git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if not base:
        raise ValueError("--base is required for PR mode")
    return git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD")

def check_gate(files, mode, base):
    changed = set(files)
    code = [p for p in changed if p.startswith(CODE_PREFIXES) or p in CODE_FILES]
    if not code:
        return
    if LOG not in changed or WORKING not in changed:
        raise ValueError(f"Code changes require both {LOG} and {WORKING} in the {mode} diff")
    if mode == "pr":
        added = git("diff", "--unified=0", f"{base}...HEAD", "--", LOG)
        if not any(line.startswith("+{") for line in added):
            raise ValueError("PR must append at least one JSONL event")
    else:
        added = git("diff", "--cached", "--unified=0", "--", LOG)
        if not any(line.startswith("+{") for line in added):
            raise ValueError("Staged code commit must append a JSONL event")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("validate", "staged", "pr"), default="validate")
    parser.add_argument("--base", help="Git base ref for PR comparison")
    args = parser.parse_args()
    try:
        events = validate()
        if args.mode != "validate":
            check_gate(changed_files(args.mode, args.base), args.mode, args.base)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"Memory protocol violation: {exc}", file=sys.stderr)
        return 1
    print(f"Memory protocol OK: {len(events)} events; mode={args.mode}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
