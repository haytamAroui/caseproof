"""Vérification hors ligne d'un « review record » exporté (fichier seul).

Rejoue l'intégrité du journal exporté (caseproof-review-record-v1) SANS base
ni serveur : digests des payloads de contrôle recalculés, chaîne de hash des
décisions de revue rejouée depuis la genèse, digest global du corps vérifié.
Toute altération échoue fermée. Ceci prouve l'intégrité et la rejouabilité du
contenu ; ce n'est ni une signature ni une approbation juridique.
"""

from __future__ import annotations

import hashlib
import json
import sys

ZERO_HASH = "0" * 64
SCHEMA = "caseproof-review-record-v1"
HEX = set("0123456789abcdef")


class RecordVerificationError(ValueError):
    """Fail closed on any replay or digest mismatch in an exported record."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest_text(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _hash(value: object) -> str:
    return _digest_text(_canonical(value))


def _sha(value: object, name: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in HEX for c in value):
        raise RecordVerificationError(f"{name} must be a sha256 hex digest")
    return value


def verify_record_document(body: object) -> tuple[str, ...]:
    """Replay an exported review record from its content alone.

    Returns the verified steps. Raises RecordVerificationError on any
    inconsistency; nothing is trusted from the file beyond what replays.
    """
    if not isinstance(body, dict) or body.get("schema") != SCHEMA:
        raise RecordVerificationError("not a caseproof-review-record-v1 document")
    record_sha = _sha(body.get("record_sha256"), "record_sha256")
    unsigned = {k: v for k, v in body.items() if k != "record_sha256"}
    if _hash(unsigned) != record_sha:
        raise RecordVerificationError("record body digest mismatch")

    brief = body.get("brief")
    if not isinstance(brief, dict):
        raise RecordVerificationError("recorded brief head missing")
    _sha(brief.get("graph_sha256"), "brief.graph_sha256")
    _sha(brief.get("original_sha256"), "brief.original_sha256")
    if type(brief.get("head_revision")) is not int or brief["head_revision"] < 1:
        raise RecordVerificationError("recorded brief head revision invalid")

    checks = body.get("checks")
    reviews = body.get("reviews")
    if not isinstance(checks, list) or not isinstance(reviews, list):
        raise RecordVerificationError("recorded checks/reviews missing")
    steps = [f"brief head revision {brief['head_revision']} · original {brief['original_sha256'][:12]}…"]

    for entry in checks:
        if not isinstance(entry, dict):
            raise RecordVerificationError("recorded check entry malformed")
        payload_sha = _sha(entry.get("payload_sha256"), "check.payload_sha256")
        snapshot_sha = _sha(entry.get("snapshot_sha256"), "check.snapshot_sha256")
        run = entry.get("run")
        if not isinstance(run, dict):
            raise RecordVerificationError("recorded check run missing")
        if _digest_text(_canonical(run)) != payload_sha:
            raise RecordVerificationError("recorded check payload digest mismatch")
        steps.append(f"check {snapshot_sha[:12]}… payload digest replayed")

    for review in reviews:
        if not isinstance(review, dict):
            raise RecordVerificationError("recorded review entry malformed")
        snapshot_sha = _sha(review.get("snapshot_sha256"), "review.snapshot_sha256")
        head_sha = _sha(review.get("head_sha256"), "review.head_sha256")
        decisions = review.get("decisions")
        if not isinstance(decisions, list):
            raise RecordVerificationError("recorded review decisions missing")
        current = ZERO_HASH
        for expected, event in enumerate(decisions, 1):
            if not isinstance(event, dict) or event.get("revision") != expected:
                raise RecordVerificationError("broken recorded review chain")
            event_sha = _sha(event.get("event_sha256"), "review.event_sha256")
            decision = event.get("decision")
            actor = event.get("actor_id")
            request = event.get("request_id")
            if not isinstance(decision, dict) or decision.get("actor_id") != actor:
                raise RecordVerificationError("recorded review decision malformed")
            digest = _digest_text(_canonical({
                "run": snapshot_sha,
                "revision": expected,
                "request": request,
                "actor": actor,
                "previous_sha": current,
                "decision": decision,
            }))
            if digest != event_sha:
                raise RecordVerificationError("tampered recorded review event")
            current = digest
        if current != head_sha:
            raise RecordVerificationError("recorded review head mismatch")
        steps.append(
            f"review chain for {snapshot_sha[:12]}… replayed from genesis "
            f"({len(decisions)} decision(s), head {head_sha[:12]}…)"
        )
    steps.append(f"record body digest {record_sha[:12]}… verified")
    return tuple(steps)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_review_record_file.py RECORD.json", file=sys.stderr)
        return 2
    try:
        body = json.loads(open(argv[1], encoding="utf-8").read())
        steps = verify_record_document(body)
    except (OSError, ValueError) as exc:
        print(f"RECORD VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("RECORD VERIFIED (integrity replay, not a signature):")
    for step in steps:
        print(f"  - {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
