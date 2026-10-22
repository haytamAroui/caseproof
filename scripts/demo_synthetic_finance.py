"""Export a synthetic-only, UNVERIFIED finance review packet as JSON.

This demo accepts NO user-supplied paths or customer uploads and makes no network calls.
Run: uv run --locked python -m scripts.demo_synthetic_finance > synthetic_packet.json
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.api.synthetic_finance import synthetic_review_packet


def main() -> None:
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "finance"
    invoice = (fixtures / "synthetic_invoice_mismatch_ubl21.xml").read_bytes()
    order = (fixtures / "synthetic_purchase_order_ubl21.xml").read_bytes()
    print(json.dumps(synthetic_review_packet(invoice, order), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
