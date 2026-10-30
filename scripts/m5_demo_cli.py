"""CaseProof M5 synthetic demo client. Never labels an entire finding VERIFIED.

Uses existing signed development endpoints. Credentials are read from env,
never CLI flags or logs. No service-role access.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


def request(base: str, token: str, method: str, path: str,
            data: dict | None = None) -> dict:
    url = base.rstrip("/") + path
    if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError("Demo CLI accepts loopback API only")
    payload = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url, data=payload, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json", "Cache-Control": "no-store"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read(16_000_000))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API returned HTTP {exc.code}; details suppressed") from None
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected API response")
    return result


def dimensions(finding: dict) -> tuple[str, str, str, str]:
    identity = str(finding.get("identity", "not_assessed")).upper()
    page = str(finding.get("page_mapping", "page_unmapped")).upper()
    fidelity = str(finding.get("fidelity", "not_assessed")).upper()
    if finding.get("ocr_uncertainty") not in (None, "not_assessed"):
        fidelity = "OCR_UNRELIABLE / " + fidelity
    support = str(finding.get("support", "not_assessed")).upper()
    return identity, page, fidelity, support


def show(findings: list[dict], color: bool) -> None:
    for finding in findings:
        identity, page, fidelity, support = dimensions(finding)
        label = f"[{finding.get('literal', 'Unknown reference')}]"
        if color and (identity != "RESOLVED" or page == "PAGE_UNMAPPED"):
            label = "\x1b[33m" + label + "\x1b[0m"
        print(label)
        print("  Identity: " + identity)
        print("  Page: " + page)
        print("  Fidelity: " + fidelity)
        print("  Semantic Support: " + support + " (Human confirmation required)")
        crop = finding.get("ocr_crop")
        if crop:
            print("  OCR candidate crop: " + json.dumps(crop, sort_keys=True))
        print()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8765")
    p.add_argument("--case-id", required=True)
    p.add_argument("--brief-id", required=True)
    p.add_argument("--output-dir", type=Path, default=Path("demo-exports"))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    sub.add_parser("export")
    review = sub.add_parser("review")
    review.add_argument("--reference-id", required=True)
    review.add_argument("--decision", choices=["CONFIRMED_SUPPORTED", "CONFIRMED_QUALIFIED",
                                                "CONFIRMED_CONTRADICTED"], required=True)
    review.add_argument("--rationale", required=True)
    upload = sub.add_parser("upload")
    upload.add_argument("--document-id", required=True)
    upload.add_argument("--version-id", required=True)
    upload.add_argument("--file", type=Path, required=True)
    args = p.parse_args()
    token = os.environ.get("CASEPROOF_DEMO_BEARER")
    if not token:
        p.error("CASEPROOF_DEMO_BEARER is required")
    root = f"/v2/matters/{args.case_id}/briefs/{args.brief_id}/verification"
    if args.command == "upload":
        # Source identities must already be registered by the signed bundle API.
        payload = {"content_base64": base64.b64encode(args.file.read_bytes()).decode()}
        path = (f"/dev/live/matters/{args.case_id}/sources/"
                f"{args.document_id}/{args.version_id}/upload")
        result = request(args.base_url, token, "POST", path, payload)
        if result.get("verified") is not True:
            raise RuntimeError("Original upload was not SHA-verified")
        print("Source original uploaded; SHA-256 round-trip verified")
        return 0
    discovered = request(args.base_url, token, "GET", root + "/discovery")
    show(discovered.get("findings", []), sys.stdout.isatty() and not os.getenv("NO_COLOR"))
    if args.command == "review":
        result = request(args.base_url, token, "POST", root + "/reviews", {
            "snapshot_hash": discovered["snapshot_hash"],
            "reference_id": args.reference_id,
            "request_id": str(uuid4()), "decision": args.decision,
            "rationale": args.rationale,
        })
        print("Human decision stored:", result.get("request_id", "<unknown>"))
    elif args.command == "export":
        result = request(args.base_url, token, "GET", root + "/export?format=json")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / f"caseproof-{args.case_id}-{args.brief_id}.json"
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        print("Scoped export saved:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
