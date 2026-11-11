"""Administrative live acceptance is never evaluated from PR-controlled workflow code."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

CONTAINED_LIVE_WORKFLOWS = {
    "intake-f3-live.yml",
    "review-f4-live.yml",
    "review-f5-live.yml",
    "review-f6-live.yml",
    "rights-pr202-signed-live.yml",
    "rights-pr203-signed-export-live.yml",
    "pr204-signed-release-ack.yml",
    "pr174-signed-historical-live.yml",
}

PR_EVENT = re.compile(r"(?m)^  pull_request(?:_target)?:")
MANUAL_MAIN = (
    "github.event_name == 'workflow_dispatch' && "
    "github.ref == 'refs/heads/main' && "
    "github.repository == 'haytamAroui/caseproof'"
)


def test_no_administrative_secret_in_pr_triggered_workflows() -> None:
    privileged = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        source = path.read_text(encoding="utf-8")
        if "CASEPROOF_DEV_AUTH_ADMIN_KEY" not in source:
            continue
        privileged.append(path.name)
        if source.lstrip().startswith("{"):
            triggers = json.loads(source).get("on", {})
            assert not any(k in triggers for k in ("pull_request", "pull_request_target")), path.name
        else:
            assert not PR_EVENT.search(source), path.name
    assert CONTAINED_LIVE_WORKFLOWS <= set(privileged)


def test_contained_live_workflows_are_dispatch_only_on_main() -> None:
    for name in CONTAINED_LIVE_WORKFLOWS:
        source = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert re.search(r"(?m)^  workflow_dispatch:\s*$", source), name
        assert not PR_EVENT.search(source), name
        assert not re.search(r"(?m)^  push:", source), name
        assert MANUAL_MAIN in source, name
