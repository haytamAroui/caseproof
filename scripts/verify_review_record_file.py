"""Vérification hors ligne d'un « review record » exporté (fichier seul).

Rejoue l'intégrité du journal exporté (caseproof-review-record-v1) SANS base
ni serveur : digests des payloads de contrôle recalculés, chaîne de hash des
décisions de revue rejouée depuis la genèse, digest global du corps vérifié.
Toute altération PONCTUELLE d'un champ échoue fermée.

Modèle de menace explicite :
- Sans reçu, la chaîne n'est pas signée : un modificateur peut recalculer
  TOUS les digests internes et le digest du corps après une modification
  arbitraire. La vérification d'intégrité seule ne détecte pas une
  falsification complète, ne prouve ni l'exhaustivité ni l'auteur.
- Avec un reçu Ed25519, trois issues possibles, sans repli silencieux :
  NON SIGNÉ (intégrité seule), SIGNÉ NON AUTHENTIFIÉ (signature
  mathématiquement valide mais émetteur auto-déclaré : la clé publique
  embarquée peut être remplacée par un faussaire), ou VÉRIFIÉ PAR CLÉ DE
  CONFIANCE (la clé publique du reçu égale une clé de confiance fournie par
  un canal indépendant ET la signature vérifie : prouve la production par
  le détenteur de cette clé d'installation et l'intégrité depuis la
  signature). Fournir une clé de confiance pour un record non signé, une
  signature invalide ou une clé substituée échoue fermé.
- Le reçu est une signature d'installation, jamais une signature
  personnelle, juridique ou eIDAS. Cycle de vie des clés (rotation,
  révocation, compromission) hors périmètre de ce vérificateur.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ZERO_HASH = "0" * 64
SCHEMA = "caseproof-review-record-v1"
SIGNATURE_DOMAIN = "caseproof-review-record-signature-v1"
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


def verify_record_document(
    body: object, *, trusted_public_key: bytes | None = None
) -> tuple[str, ...]:
    """Replay an exported review record from its content alone.

    trusted_public_key: raw 32-byte Ed25519 installation key obtained through
    an independent trusted channel. When supplied, the record MUST carry a
    receipt signed under exactly that key; anything less fails closed.
    Returns the verified steps. Raises RecordVerificationError otherwise.
    """
    if trusted_public_key is not None and (
        type(trusted_public_key) is not bytes or len(trusted_public_key) != 32
    ):
        raise RecordVerificationError("trusted public key must be 32 raw bytes")
    if not isinstance(body, dict) or body.get("schema") != SCHEMA:
        raise RecordVerificationError("not a caseproof-review-record-v1 document")
    record_sha = _sha(body.get("record_sha256"), "record_sha256")
    signed_record = {k: v for k, v in body.items() if k != "receipt"}
    unsigned = {k: v for k, v in signed_record.items() if k != "record_sha256"}
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

    receipt = body.get("receipt")
    if receipt is None:
        if trusted_public_key is not None:
            raise RecordVerificationError(
                "trusted key supplied but record carries no receipt: unsigned record"
            )
        steps.append("no receipt: integrity-only record (unsigned, unauthenticated issuer)")
        return tuple(steps)
    if (
        not isinstance(receipt, dict)
        or set(receipt) != {"scheme", "domain", "public_key", "signature"}
        or receipt["scheme"] != "ed25519"
        or receipt["domain"] != SIGNATURE_DOMAIN
    ):
        raise RecordVerificationError("malformed or unknown receipt")
    try:
        public = bytes.fromhex(receipt["public_key"])
        signature = bytes.fromhex(receipt["signature"])
    except (TypeError, ValueError):
        raise RecordVerificationError("malformed receipt key or signature") from None
    if len(public) != 32 or len(signature) != 64:
        raise RecordVerificationError("malformed receipt key or signature")
    signed_doc = {"domain": SIGNATURE_DOMAIN, "record": signed_record}
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, _canonical(signed_doc).encode("utf-8")
        )
    except InvalidSignature:
        raise RecordVerificationError("invalid receipt signature") from None
    if trusted_public_key is None:
        steps.append(
            "receipt signature mathematically valid, issuer SELF-ASSERTED "
            "(untrusted: the embedded key can be substituted by a forger; "
            "supply the trusted installation key to authenticate)"
        )
    elif not hmac.compare_digest(public, trusted_public_key):
        raise RecordVerificationError(
            "untrusted issuer: receipt key does not match the trusted key "
            "(key substitution rejected even though the signature is internally valid)"
        )
    else:
        steps.append(
            f"receipt VERIFIED against the trusted installation key "
            f"({public.hex()[:12]}…): produced by that key holder, unchanged since signing"
        )
    return tuple(steps)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Offline replay of an exported caseproof review record."
    )
    parser.add_argument("record", help="path to the exported RECORD.json")
    parser.add_argument(
        "--trusted-key-file",
        help="file holding the trusted installation Ed25519 public key (64 hex chars), "
        "obtained through an independent trusted channel",
    )
    args = parser.parse_args(argv[1:])
    trusted = None
    if args.trusted_key_file:
        try:
            trusted = bytes.fromhex(open(args.trusted_key_file, encoding="utf-8").read().strip())
        except (OSError, ValueError):
            print("RECORD VERIFICATION FAILED: unreadable trusted key file", file=sys.stderr)
            return 1
    try:
        body = json.loads(open(args.record, encoding="utf-8").read())
        steps = verify_record_document(body, trusted_public_key=trusted)
    except (OSError, ValueError) as exc:
        print(f"RECORD VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("RECORD VERIFIED (integrity replay; signature level as stated, never a legal signature):")
    for step in steps:
        print(f"  - {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
