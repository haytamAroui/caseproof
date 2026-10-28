"""Signed matter discovery uses the invoker view and never exposes org IDs."""
import json
from unittest.mock import patch

import pytest

from apps.api.access_control import AccessRejected
from apps.api.signed_supabase_matter_catalog import SignedMatterCatalog

CASE = "11111111-1111-4111-8111-111111111111"


class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def read(self, limit):
        return self.body[:limit]


class Connection:
    def __init__(self, body):
        self.response = Response(body)
        self.request_args = None

    def request(self, *args, **kwargs):
        self.request_args = (args, kwargs)

    def getresponse(self):
        return self.response

    def close(self):
        pass


def test_catalog_uses_signed_identity_and_limits_returned_fields():
    conn = Connection(json.dumps([{"case_id": CASE, "case_revision": 1,
                                   "state": "open", "org_id": "ignored"}]).encode())
    with patch("apps.api.signed_supabase_matter_catalog.http.client.HTTPSConnection",
               return_value=conn):
        result = SignedMatterCatalog("sb_publishable_test").list_matters("signed-token")
    assert result == [{"case_id": CASE, "case_revision": 1, "state": "open"}]
    assert conn.request_args[1]["headers"]["Authorization"] == "Bearer signed-token"
    assert "caseproof_private_matters" in conn.request_args[0][1]


def test_catalog_refuses_malformed_or_unbounded_results():
    catalog = SignedMatterCatalog("sb_publishable_test")
    for body in (b'[{"case_id":"not-a-uuid","case_revision":1,"state":"open"}]',
                 b"[" + b"{}," * 101 + b"{}]", b"invalid"):
        with patch("apps.api.signed_supabase_matter_catalog.http.client.HTTPSConnection",
                   return_value=Connection(body)), pytest.raises(AccessRejected):
            catalog.list_matters("signed-token")
    with pytest.raises(AccessRejected):
        catalog.list_matters("bad\nheader")
