from application.data_rights import Decision, RightsPolicy, evaluate


def test_missing_policy_is_unknown():
    assert evaluate(None, 'process', same_matter=True) == Decision.UNKNOWN


def test_cross_matter_export_denied():
    policy = RightsPolicy(1, 'firm-authorization', {'export': True})
    assert evaluate(policy, 'export', same_matter=False) == Decision.DENY


def test_process_requires_authorization_reference():
    policy = RightsPolicy(1, None, {'process': True})
    assert evaluate(policy, 'process', same_matter=True) == Decision.DENY
