"""Keep critical disposable CI gates active on protected main pushes.

GitHub displays check counts per event: a passing pull request is not proof
that the squash/merge commit on main ran the same safeguards.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

MAIN_PUSH_GATES = (
    "page-worker-postgres-hosted-mcp.yml",
    "page-worker-resume.yml",
    "representation-fidelity.yml",
    "phase3-ocr-geometry-ci.yml",
    "retention-disposable.yml",
    "dossier-ci.yml",
)

PATH_FILTERED_GATES = (
    "page-worker-postgres-hosted-mcp.yml",
    "page-worker-resume.yml",
)


def _event_section(workflow: str, event: str) -> str:
    lines = (WORKFLOWS / workflow).read_text(encoding="utf-8").splitlines()
    assert "on:" in lines, f"{workflow}: expected YAML on: triggers"
    trigger_line = f"  {event}:"
    assert trigger_line in lines, f"{workflow}: missing {event} trigger"
    start = lines.index(trigger_line) + 1
    section = []
    for line in lines[start:]:
        if line and not line.startswith(("    ", "      ")) and not line.lstrip().startswith("#"):
            break
        section.append(line)
    return "\n".join(section)


@pytest.mark.parametrize("workflow", MAIN_PUSH_GATES)
def test_critical_disposable_gates_run_on_main(workflow: str) -> None:
    push = _event_section(workflow, "push")
    assert re.search(r"(?m)^    branches: \[[^\]\n]*\bmain\b", push), (
        f"{workflow}: critical gate must run after merge on main"
    )


@pytest.mark.parametrize("workflow", PATH_FILTERED_GATES)
def test_heavy_gates_keep_pr_and_main_paths_identical(workflow: str) -> None:
    def paths(event: str) -> list[str]:
        section = _event_section(workflow, event)
        return re.findall(r"(?m)^      - ['\"]?([^'\"]+?)['\"]?$", section)

    main_paths = paths("push")
    assert main_paths, f"{workflow}: no main paths selected"
    assert main_paths == paths("pull_request"), (
        f"{workflow}: push and pull_request path filters drifted"
    )
    assert "uv.lock" in main_paths
    assert "pyproject.toml" in main_paths
    assert f".github/workflows/{workflow}" in main_paths
