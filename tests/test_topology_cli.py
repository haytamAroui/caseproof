"""No implicit paid calls; explicit loopback DB and exact call acknowledgments."""

from argparse import Namespace

import pytest

from application.extraction.contracts import ExtractionError
from scripts.run_topology_comparison import run, validate_live_configuration


def args(**values):
    defaults = dict(
        acknowledge_max_calls=None, org_id=None, case_id=None, actor_id=None,
        run_id="scripted-paired-v1",
    )
    return Namespace(**{**defaults, **values})


def test_preflight_never_uses_model_credentials():
    report = run(["--show-call-budget"])
    assert report["mode"] == "preflight_only"
    assert report["max_requesty_calls"] >= 28
    assert report["provider_invoked"] is False


def test_live_guard_rejects_missing_explicit_acknowledgment():
    with pytest.raises(ExtractionError, match="acknowledgement"):
        validate_live_configuration(args())


def test_cli_does_not_accept_billing_flags_without_live_mode():
    with pytest.raises(ExtractionError, match="live-only"):
        run(["--acknowledge-max-calls", "1"])


def test_live_scope_requires_disposable_case_and_actor():
    from evals.topology_comparison import planned_call_cap

    with pytest.raises(ExtractionError, match="org, case and actor"):
        validate_live_configuration(args(acknowledge_max_calls=planned_call_cap()))


def test_live_rejects_remote_dsn_even_with_explicit_opt_in(monkeypatch):
    from evals.topology_comparison import planned_call_cap

    monkeypatch.setenv(
        "CASEPROOF_EVAL_DISPOSABLE_POSTGRES_DSN",
        "host=example.invalid dbname=test user=synthetic",
    )
    arguments = args(
        acknowledge_max_calls=planned_call_cap(),
        org_id="00000000-0000-0000-0000-000000000001",
        case_id="00000000-0000-0000-0000-000000000002",
        actor_id="00000000-0000-0000-0000-000000000003",
        run_id="unique-live-test-abc",
    )
    with pytest.raises(ExtractionError, match="non-loopback"):
        validate_live_configuration(arguments)
