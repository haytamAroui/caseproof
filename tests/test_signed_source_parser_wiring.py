"""Live composition of the existing resource-limited product parser (pypdf text layer, no OCR) behind an explicit switch.
Real: composition code, the product parser, the evidence indexer, condition matching. FAKE: bearer, storage library, RPC."""
from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace as NS

import pytest

from application.litigation.library import EvidenceIndexer
from application.litigation.signed_conditions import _readable, match_conditions, normalise_input
from apps.api import signed_supabase_check_store as scs
from apps.api.signed_live_composition import assemble_request_workbench
from infrastructure.parsers.limited import LimitedDocumentParser

ENV = {"CASEPROOF_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_" + "D" * 24}


def pdf(pages: list[str]) -> bytes:
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"", b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    kids = []
    for n, t in enumerate(pages):
        c = f"BT /F1 14 Tf 40 700 Td ({t}) Tj ET".encode()
        objs.append(f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Resources<</Font<</F1 3 0 R>>>>/Contents {5 + 2 * n} 0 R>>".encode())
        objs.append(b"<</Length %d>>\nstream\n" % len(c) + c + b"\nendstream")
        kids.append(f"{4 + 2 * n} 0 R")
    objs[1] = f"<</Type/Pages/Count {len(pages)}/Kids[{' '.join(kids)}]>>".encode()
    out, offs = b"%PDF-1.4\n", []
    for k, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{k} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<</Size {len(objs) + 1}/Root 1 0 R>>\nstartxref\n{x}\n%%EOF\n".encode()


def test_parser_switch_is_off_by_default_and_validated():
    assert assemble_request_workbench(ENV, "jwt").store._indexer is None
    on = assemble_request_workbench({**ENV, "CASEPROOF_SIGNED_SOURCE_PARSER": "limited-v1"}, "jwt")
    assert isinstance(on.store._indexer, EvidenceIndexer) and isinstance(on.store._indexer.parser, LimitedDocumentParser)
    with pytest.raises(ValueError):
        assemble_request_workbench({**ENV, "CASEPROOF_SIGNED_SOURCE_PARSER": "ocr"}, "jwt")


def test_text_layer_pdf_gets_page_anchored_text_but_a_scan_stays_unread(monkeypatch):
    monkeypatch.setattr(scs, "valid_storage_binding", lambda *a, **k: True)
    layer = pdf(["Premiere page sans rien.", "Le paiement a bien ete recu le 3 mars."])
    scan = pdf([""])  # no text layer: the product parser has no OCR, so it must not become a read source
    docs = {}

    def store(indexer):
        lib = NS(read=lambda **k: docs[str(k["document_id"])])
        return scs.LiveMatterCheckStore(call_rpc=lambda **_: {}, publishable_key="k", bearer="b", library=lib, indexer=indexer)

    def source(data):
        d, v = str(uuid.uuid4()), str(uuid.uuid4())
        docs[d] = data
        return d, v, {"document_id": d, "version_id": v, "original_sha256_hex": hashlib.sha256(data).hexdigest(),
                      "media_type": "application/pdf", "byte_length": len(data), "source_binding": "x"}

    access = NS(org_id=str(uuid.uuid4()), case_id=str(uuid.uuid4()))
    d1, _v1, s1 = source(layer)
    d2, _v2, s2 = source(scan)
    off = store(None)._preview(access=access, source=s1)
    assert off.row.status == "partial" and off.text == ""  # unchanged default: unread, not "checked"
    on = store(EvidenceIndexer(LimitedDocumentParser()))
    ok = on._preview(access=access, source=s1)
    assert _readable(ok) and "paiement" in ok.text
    spec = normalise_input([{"id": "c1", "label": "L", "question": "", "trigger": ["courrier"],
                             "evidence": ["paiement"], "pieces": []}])
    labels = {ok.row.source_id: "Pièce 1"}
    m = match_conditions("Voir le courrier.", spec, [ok], labels)
    found = m["anchors"][0]["found"]
    assert found and found[0]["pdf_page"] == 2 and m["anchors"][0]["status"] == "UNDETERMINED"  # never PASS
    unread = on._preview(access=access, source=s2)
    assert not _readable(unread)
    m2 = match_conditions("Voir le courrier.", spec, [ok, unread], {**labels, unread.row.source_id: "Pièce 2"})
    assert m2["anchors"][0]["pieces_not_read"] == ["Pièce 2"]
    assert d1 and d2
