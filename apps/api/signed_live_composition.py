"""Environment composition for the live signed workbench ports.

Wires LiveSignedBriefPublisher and LiveSignedReviewRecord into the
development app when, and only when, explicit configuration is present.
Absent configuration returns None so the app keeps its fail-closed 503
development semantics; nothing here creates accounts, keys or data, and the
live RPC surface is only reachable through the pinned transport with a
signed-user bearer. The publishable key is configuration, never a secret:
service keys are rejected by the transport itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from apps.api.signed_supabase_brief_publisher import LiveSignedBriefPublisher
from apps.api.signed_supabase_review_record import LiveSignedReviewRecord
from apps.api.signed_supabase_rpc import API_KEY, call_rpc

__all__ = ["LiveWorkbenchPorts", "assemble_live_workbench", "live_signed_ports"]

_PUBLISHABLE_ENV = "CASEPROOF_SUPABASE_PUBLISHABLE_KEY"
_SIGNING_KEY_ENV = "CASEPROOF_REVIEW_RECORD_SIGNING_KEY_HEX"


@dataclass(frozen=True)
class LiveWorkbenchPorts:
    """Ports the live adapters cover, plus those still missing an adapter.

    missing names the port protocols with no live implementation yet; the
    caller must refuse to start rather than silently mix live and disposable
    backends on the same matter.
    """

    publisher: LiveSignedBriefPublisher
    review_record: LiveSignedReviewRecord
    missing: tuple[str, ...]


# Ports the workbench needs that have no live adapter today: the signed
# source library/originals exist as modules but are not assembled into this
# composition, and the check store / review workspace have no live adapter
# at all (legacy caseproof_dev_live_review is a different, uncabled surface).
_MISSING_PORTS = (
    "SignedSourceLibrary",
    "AuthorizedOriginalReader",
    "SignedReviewWorkspace",
    "AuthorizedLitigationChecker",
)


def assemble_live_workbench(environ: Mapping[str, str]) -> LiveWorkbenchPorts:
    """Assemble every live port the workbench can use, refusing silently-mixed boots."""
    ports = live_signed_ports(environ)
    if ports is None:
        raise ValueError(f"{_PUBLISHABLE_ENV} required for the live workbench")
    publisher, record = ports
    return LiveWorkbenchPorts(publisher=publisher, review_record=record, missing=_MISSING_PORTS)


def live_signed_ports(
    environ: Mapping[str, str],
) -> tuple[LiveSignedBriefPublisher, LiveSignedReviewRecord] | None:
    """Build the live ports from explicit configuration, or None.

    A present but malformed publishable key is a configuration error, not a
    reason to fall back silently: running the workbench on the wrong key
    shape would fail closed at call time anyway, so fail here instead.
    """
    publishable = environ.get(_PUBLISHABLE_ENV, "")
    if not publishable:
        return None
    if not API_KEY.fullmatch(publishable):
        raise ValueError("CASEPROOF_SUPABASE_PUBLISHABLE_KEY must be a publishable key")
    signing_key: bytes | None = None
    raw_signing = environ.get(_SIGNING_KEY_ENV, "")
    if raw_signing:
        try:
            signing_key = bytes.fromhex(raw_signing)
        except ValueError:
            raise ValueError("CASEPROOF_REVIEW_RECORD_SIGNING_KEY_HEX must be hex") from None
    publisher = LiveSignedBriefPublisher(call_rpc=call_rpc, publishable_key=publishable)
    record = LiveSignedReviewRecord(
        call_rpc=call_rpc, publishable_key=publishable, signing_key=signing_key
    )
    return publisher, record
