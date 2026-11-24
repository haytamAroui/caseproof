"""'omission' is a reviewer statement ("a relevant passage or piece was not shown"). It never waives anything.

The SQL side is a DRAFT in db/proposals, not applied to any shared environment. These tests check parity
of the allow-lists and that the draft changes nothing but the allow-list. They do not execute the RPC.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from application.litigation.review_blockers import review_blockers
from application.litigation.unified_review import ReviewDisposition
from application.litigation.workspace_contract import ClearbriefDecisionView
from apps.api.litigation_review_app import ReviewBody

ROOT = Path(__file__).resolve().parents[1]
DRAFT = (ROOT / "db/proposals/SIGNED_review_omission_disposition.sql").read_text()
VALUES = {"confirmed_candidate", "dismissed", "needs_information", "omission"}


def test_every_allow_list_agrees():
    assert {d.value for d in ReviewDisposition} == VALUES
    assert set(get_args(ReviewBody.model_fields["disposition"].annotation)) == VALUES
    assert set(get_args(ClearbriefDecisionView.model_fields["disposition"].annotation)) == VALUES
    for name in ("clearbrief-command", "clearbrief-review"):
        text = (ROOT / f"frontend/src/shared/api/{name}.schema.json").read_text()
        assert '"omission"' in text, name
    lists = re.findall(r"p_disposition not in \(([^)]*)\)", DRAFT)
    assert len(lists) == 1 and set(re.findall(r"'([a-z_]+)'", lists[0])) == VALUES


def test_draft_is_a_single_function_replace_with_no_privilege_or_data_change():
    low = DRAFT.lower()
    assert low.count("create or replace function caseproof._rights_legacy_live_review(") == 1
    assert "-- draft, not applied" in low
    for forbidden in ("grant ", "revoke ", "drop ", "alter table", "insert into supabase_migrations", "delete from"):
        assert forbidden not in low.split("$function$", 1)[0] + low.split("$function$")[-1], forbidden


def test_omission_does_not_clear_a_blocker():
    from types import SimpleNamespace
    legal = SimpleNamespace(reference_id="r1", status="UNDETERMINED", reason="article_not_in_corpus")
    run = SimpleNamespace(citation_observations=(), factual_observations=(), event_observations=(),
                          passage_flags=(), incomplete=(), excluded=(), legal_observations=(legal,),
                          suitability_observations=(), snapshot_hash="a" * 64)
    decision = SimpleNamespace(observation_id="legal:r1", disposition=ReviewDisposition.OMISSION)
    out = review_blockers(run, (decision,))
    assert out["items"] == [{"observation_id": "legal:r1", "reason": "article_not_in_corpus",
                             "review_disposition": "omission"}]
    assert out["verdict"] == "not_computed" and out["release_authorized"] is False
