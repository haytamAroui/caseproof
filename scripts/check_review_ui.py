"""Project-owned static UI contract checks. Browser tests verify runtime behavior."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = (ROOT / "apps/web/review/index.html").read_text()
    js = (ROOT / "apps/web/review/workbench.js").read_text()
    css = (ROOT / "apps/web/review/workbench.css").read_text()
    design = (ROOT / "DESIGN.md").read_text()
    assert "novalidate" in source
    assert "resize:none" in css or "resize: none" in css
    assert "Array.from(content)" in js
    assert 'role="status"' in source and 'role="alert"' in source
    assert not re.search(r"\b(?:alert|confirm|prompt)\s*\(", js)
    assert "innerHTML" not in js and "localStorage" not in js
    assert ":focus-visible" in css and "prefers-reduced-motion" in css and "forced-colors" in css
    assert "scrollbar-color" in css and "scrollbar-thumb" in css
    for token in ("primary", "canvas", "text", "muted", "border", "highlight", "danger"):
        documented = re.search(r"^  " + token + r': "(#[a-fA-F0-9]+)"', design, re.M)[1].lower()
        runtime = re.search(r"--" + token + r":(#[a-fA-F0-9]+)", css)[1].lower()
        assert documented == runtime, (token, documented, runtime)
    for field in ("note", "correction", "action", "filter"):
        assert f'for="{field}"' in source
    assert "Discard draft" in source and "Keep editing" in source
    subprocess.run(["node", "--check", str(ROOT / "apps/web/review/workbench.js")], check=True)
    print(json.dumps({"review_ui_contract": "pass", "browser_evidence_required": True}))


if __name__ == "__main__":
    main()
