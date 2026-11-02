#!/usr/bin/env python3
"""Fail-closed validation for CaseProof skills. Standard library only."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".claude" / "skills"
REQUIRED = {
    "caseproof-router", "caseproof-foundation", "caseproof-frontend-engineering",
    "caseproof-landing-page", "caseproof-evidence-ui", "caseproof-tabular-review",
    "caseproof-document-correction", "caseproof-recovery-session",
    "caseproof-report-export", "caseproof-verification-workflow",
    "caseproof-case-pack-invoice", "caseproof-product-qa",
    "caseproof-landing-qa", "caseproof-claims-copy", "caseproof-motion",
    "caseproof-animation-review", "caseproof-diagram-flow",
    "caseproof-i18n-accessibility",
}
LEGACY_CONFLICTS = {
    "caseproof-verification-orchestrator",
    "caseproof-recovery-ux",
    "caseproof-legal-workflow-packs",
}
def main():
    errors = []
    actual = {p.name for p in SKILLS.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()} if SKILLS.exists() else set()
    for name in sorted(REQUIRED - actual):
        errors.append(f"Missing required v2 skill: {name}")
    for name in sorted(actual & LEGACY_CONFLICTS):
        errors.append(f"Legacy overlapping skill must be migrated/retired: {name}")
    for name in sorted(actual):
        path = SKILLS / name / "SKILL.md"
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---\n") or "\n---\n" not in raw[4:]:
            errors.append(f"{path}: missing YAML frontmatter")
            continue
        front = raw.split("\n---\n", 1)[0]
        match = re.search(r"(?m)^name:\s*([^\n]+)", front)
        if not match or match.group(1).strip().strip("'\"") != name:
            errors.append(f"{path}: frontmatter name differs from directory")
        if len(raw.splitlines()) > 500:
            errors.append(f"{path}: exceeds 500 lines; move detail to references/")
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", raw):
            if "://" in target or target.startswith(("mailto:", "#")):
                continue
            if not (path.parent / target).exists():
                errors.append(f"{path}: broken relative link {target}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"PASS: {len(REQUIRED)} required skills, names, links and no legacy collisions")
    return 0
if __name__ == "__main__":
    sys.exit(main())
