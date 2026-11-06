import logging

from application.data_rights import Decision, RightsPolicy, evaluate, evaluate_detail
from apps.api.data_rights_shadow import observe_authorized_read


def test_missing_policy_is_unknown():
    result = evaluate_detail(None, "process", same_matter=True)
    assert result.decision == Decision.UNKNOWN
    assert result.reason == "policy_missing"


def test_cross_matter_export_denied():
    policy = RightsPolicy(1, "firm-authorization", {"export": True})
    assert evaluate(policy, "export", same_matter=False) == Decision.DENY


def test_process_requires_authorization_reference():
    policy = RightsPolicy(1, None, {"process": True})
    assert evaluate(policy, "process", same_matter=True) == Decision.DENY


def test_explicit_permission_and_restricted_defaults():
    policy = RightsPolicy(1, "signed-contract", {"process": True})
    assert evaluate(policy, "process", same_matter=True) == Decision.ALLOW
    assert evaluate(policy, "indexForSearch", same_matter=True) == Decision.DENY
    assert evaluate(policy, "useAcrossMatters", same_matter=False) == Decision.DENY
    assert evaluate(policy, "unknown-action", same_matter=True) == Decision.DENY


def test_invalid_policy_fails_closed():
    policy = RightsPolicy(0, "signed-contract", {"process": True})
    assert evaluate(policy, "process", same_matter=True) == Decision.DENY
    policy = RightsPolicy(1, "signed-contract", {"process": 1})
    assert evaluate(policy, "process", same_matter=True) == Decision.DENY


def test_shadow_logs_missing_policy_without_identifiers(caplog):
    with caplog.at_level(logging.INFO, logger="caseproof.rights.shadow"):
        observe_authorized_read(policy_lookup=lambda: None)
    assert "policy_missing" in caplog.text
    assert "unknown" in caplog.text


def test_shadow_errors_do_not_propagate(caplog):
    def broken():
        raise RuntimeError("private data must never enter log")
    with caplog.at_level(logging.WARNING, logger="caseproof.rights.shadow"):
        observe_authorized_read(policy_lookup=broken)
    assert "evaluation_unavailable" in caplog.text
    assert "private data" not in caplog.text
