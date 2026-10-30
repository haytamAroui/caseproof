# CaseProof M5 CLI demo (synthetic data only)

This tool connects to the **loopback development API** using an existing signed matter, registered bundle and bearer token. It does not create a new matter or authenticate users; use the existing protected fixture workflow for those operations. No real client dossier is permitted before M5 security sign-off.

```bash
export CASEPROOF_DEMO_BEARER='<short-lived signed user JWT>'
uv run python -m scripts.m5_demo_cli --case-id UUID --brief-id DRAFT_VERSION_UUID discover
uv run python -m scripts.m5_demo_cli --case-id UUID --brief-id DRAFT_VERSION_UUID review --reference-id ref-0000 --decision CONFIRMED_QUALIFIED --rationale "Needs human source check"
uv run python -m scripts.m5_demo_cli --case-id UUID --brief-id DRAFT_VERSION_UUID export
```

Upload a registered original using `upload --document-id UUID --version-id UUID --file ./synthetic.pdf`. Registration and ingestion must be completed separately via the existing signed Phase 2/3 API. A successful upload proves the original SHA-256 round trip, **not** a successful OCR ingestion or evidentiary verification.

Output is split into identity, page mapping, fidelity, and semantic support. OCR geometry is displayed as a **candidate** coordinate, not a verified crop file. It never invents EXACT_MATCH, never prints a global VERIFIED badge, and never claims semantic support from a human decision.

The JSON export contains potentially sensitive review metadata: use only synthetic fixtures, store in a protected directory and delete after the demo.
