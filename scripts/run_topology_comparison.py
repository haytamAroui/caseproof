"""Explicit, bounded, synthetic-only live Requesty extraction comparison.

Default is a nonbillable scripted smoke test. Live mode demands three explicit
UUIDs, an exact call ceiling and a loopback disposable DB; no production URLs,
secrets or customer paths are accepted as CLI arguments.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from application.extraction.contracts import ExtractionError, Scope
from evals.topology_comparison import compare_topologies, planned_call_cap


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Synthetic paired QAE extraction evaluation")
    p.add_argument("--live-requesty", action="store_true", help="Opt in to billable Requesty inference")
    p.add_argument("--acknowledge-max-calls", type=int)
    p.add_argument("--org-id")
    p.add_argument("--case-id")
    p.add_argument("--actor-id")
    p.add_argument("--run-id", default="scripted-paired-v1")
    p.add_argument("--show-call-budget", action="store_true")
    return p


def validate_live_configuration(args: argparse.Namespace) -> tuple[Scope, UUID, str]:
    expected = planned_call_cap()
    if args.acknowledge_max_calls != expected:
        raise ExtractionError(f"explicit exact billable call acknowledgement required: {expected}")
    if not args.org_id or not args.case_id or not args.actor_id:
        raise ExtractionError("explicit disposable org, case and actor UUIDs required")
    try:
        scope = Scope(UUID(args.org_id), UUID(args.case_id))
        actor = UUID(args.actor_id)
    except ValueError:
        raise ExtractionError("invalid scope or actor UUID") from None
    if actor.int == 0:
        raise ExtractionError("nonzero reviewer actor required")
    if args.run_id == "scripted-paired-v1" or not args.run_id.strip():
        raise ExtractionError("unique explicit live run ID required")
    dsn = os.environ.get("CASEPROOF_EVAL_DISPOSABLE_POSTGRES_DSN", "")
    if not dsn:
        raise ExtractionError("disposable PostgreSQL DSN environment required")
    # Import only on explicit live path; this CLI is never a production gateway.
    from psycopg.conninfo import conninfo_to_dict

    try:
        opts = conninfo_to_dict(dsn)
    except Exception:
        raise ExtractionError("invalid disposable DSN") from None
    if opts.get("host") not in {"127.0.0.1", "localhost", "::1"}:
        raise ExtractionError("non-loopback or socket-based database forbidden")
    database = opts.get("dbname")
    if not isinstance(database, str) or database.lower() in {
        "postgres", "template0", "template1", "caseproof", "production"
    }:
        raise ExtractionError("explicit nonproduction evaluation database required")
    return scope, actor, dsn


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parser().parse_args(argv)
    if args.show_call_budget:
        return {
            "mode": "preflight_only",
            "corpus": "four_synthetic_documents",
            "max_requesty_calls": planned_call_cap(),
            "provider_invoked": False,
        }
    if not args.live_requesty:
        if any(
            value is not None
            for value in (args.acknowledge_max_calls, args.org_id, args.case_id, args.actor_id)
        ):
            raise ExtractionError("live-only arguments require explicit --live-requesty")
        return compare_topologies()
    scope, actor, dsn = validate_live_configuration(args)
    import psycopg

    from apps.api.disposable_extraction_journal import DisposablePostgresJournal

    def connect() -> psycopg.Connection[Any]:
        return psycopg.connect(dsn, connect_timeout=5, autocommit=False)

    # Fail before any inference if DB identity/scope/permissions/checkpoint tables
    # are not ready. A new unique run ID is required for changed configurations.
    with connect() as conn:
        ok = conn.execute(
            "select exists("
            "select 1 from caseproof.organization_members m "
            "join caseproof.cases c on c.org_id=m.org_id "
            "where m.org_id=%s and c.id=%s and m.user_id=%s and m.active "
            "and m.actions @> array['case:read','finding:write']::text[])",
            (scope.org_id, scope.case_id, actor),
        ).fetchone()
        if ok is None or ok[0] is not True:
            raise ExtractionError("disposable benchmark case authorization unavailable")
        conn.execute("select 1 from caseproof._ei_steps limit 0")
    return compare_topologies(
        live=True,
        journal=DisposablePostgresJournal(connect, actor_id=actor),
        scope=scope,
        run_id=args.run_id,
        authorized_billable_calls=planned_call_cap(),
    )


def main() -> None:
    print(json.dumps(run(), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
