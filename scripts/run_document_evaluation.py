"""Synthetic-only evaluation runner. Live mode requires existing disposable PG context.

At most 8 Requesty calls, 512 output tokens each, no retry/fallback. No customer
paths or custom source input. Reuse --run-id to resume saved checkpoints.
"""

import argparse
import json
import os
from uuid import UUID

from application.extraction.contracts import ExtractionError, Scope
from apps.api.disposable_extraction_journal import DisposablePostgresJournal
from evals.document_extraction import evaluate
from scripts.extraction_fixtures import SCOPE
from scripts.verify_vault_integration import connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-requesty", action="store_true")
    parser.add_argument("--run-id", default="document-eval-v1")
    args = parser.parse_args()
    try:
        journal = None
        scope = SCOPE
        if args.live_requesty:
            scope = Scope(UUID(os.environ["CASEPROOF_EVAL_ORG"]), UUID(os.environ["CASEPROOF_EVAL_CASE"]))
            actor = UUID(os.environ["CASEPROOF_EVAL_ACTOR"])
            # connect() rejects non-local/non-ephemeral database settings and ambient PG overrides.
            with connect():
                pass
            journal = DisposablePostgresJournal(connect, actor_id=actor)
        print(
            json.dumps(
                evaluate(live=args.live_requesty, journal=journal, scope=scope, run_id=args.run_id),
                indent=2,
                allow_nan=False,
            )
        )
    except (ExtractionError, KeyError, ValueError):
        raise SystemExit(
            "Evaluation blocked: missing Requesty/disposable DB settings or invalid checkpoint state."
        ) from None


if __name__ == "__main__":
    main()
