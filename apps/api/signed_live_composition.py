"""Environment composition for the live signed workbench ports.

Wires LiveSignedBriefPublisher and LiveSignedReviewRecord into the
development app, and the bearer-bound ports (check store, review ledger,
checker, review workspace, source library, original reader) per request,
when, and only when, explicit configuration is present.
Absent configuration returns None so the app keeps its fail-closed 503
development semantics; nothing here creates accounts, keys or data, and the
live RPC surface is only reachable through the pinned transport with a
signed-user bearer. The publishable key is configuration, never a secret:
service keys are rejected by the transport itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_original_reader import AuthorizedOriginalReader
from apps.api.litigation_review_workspace import ReviewLedger, SignedReviewWorkspace
from apps.api.signed_supabase_brief_publisher import LiveSignedBriefPublisher
from apps.api.signed_supabase_check_store import LiveMatterCheckStore
from apps.api.signed_supabase_facts import LiveMatterFacts
from apps.api.signed_supabase_flags import LivePassageFlags
from apps.api.signed_supabase_originals import SignedOriginalsStorage
from apps.api.signed_supabase_review_ledger import LiveReviewLedger
from apps.api.signed_supabase_review_record import LiveSignedReviewRecord
from apps.api.signed_supabase_rpc import API_KEY, PROJECT_REF, call_rpc
from apps.api.signed_supabase_source_library import SignedSourceLibrary
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseAuthUserVerifier,
)

__all__ = [
    "LiveWorkbenchPorts",
    "RequestWorkbench",
    "assemble_live_workbench",
    "assemble_request_workbench",
    "live_signed_ports",
]

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


# Ports assemble_live_workbench cannot build from the environment alone:
# they are bound to one verified request bearer, so they are assembled by
# assemble_request_workbench instead. None remains without a live adapter.
_MISSING_PORTS: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequestWorkbench:
    """Every live port bound to ONE verified request bearer.

    The checker publishes to the exact ledger the workspace records into;
    the store re-derives every digest from verified bytes. Never mix these
    with disposable backends on the same matter.
    """

    store: LiveMatterCheckStore
    ledger: LiveReviewLedger
    checker: AuthorizedLitigationChecker
    workspace: SignedReviewWorkspace
    library: SignedSourceLibrary
    originals: AuthorizedOriginalReader


def legal_corpus_provider(environ: Mapping[str, str]) -> Callable[[str], Any]:
    """Per-matter corpus choice, explicit: CASEPROOF_LEGAL_CORPUS_BY_CASE is a
    JSON object mapping a case id to a corpus directory. A matter not listed
    has no corpus (its articles are reported unchecked); there is no default."""
    import json
    from pathlib import Path

    from application.litigation.legal_references import load_corpus_config
    raw = environ.get("CASEPROOF_LEGAL_CORPUS_BY_CASE", "")
    mapping: dict[str, str] = {}
    if raw:
        try:
            decoded = json.loads(raw)
        except ValueError:
            raise ValueError("CASEPROOF_LEGAL_CORPUS_BY_CASE must be JSON") from None
        if not isinstance(decoded, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in decoded.items()):
            raise ValueError("CASEPROOF_LEGAL_CORPUS_BY_CASE must map case id to directory")
        mapping = decoded
    cache: dict[str, Any] = {}

    def provider(case_id: str) -> Any:
        directory = mapping.get(str(case_id))
        if directory is None:
            return None
        if directory not in cache:
            cache[directory] = load_corpus_config(Path(directory))
        return cache[directory]

    return provider


def assemble_request_workbench(environ: Mapping[str, str], bearer: str) -> RequestWorkbench:
    """Assemble the bearer-bound live ports, refusing silently-mixed boots."""
    publishable = environ.get(_PUBLISHABLE_ENV, "")
    if not publishable:
        raise ValueError(f"{_PUBLISHABLE_ENV} required for the live workbench")
    if not API_KEY.fullmatch(publishable):
        raise ValueError("CASEPROOF_SUPABASE_PUBLISHABLE_KEY must be a publishable key")
    if not isinstance(bearer, str) or not 0 < len(bearer) <= 8192:
        raise ValueError("verified request bearer required")
    storage = SignedOriginalsStorage(publishable_key=publishable)
    library = SignedSourceLibrary(storage=storage)
    store = LiveMatterCheckStore(
        call_rpc=call_rpc, publishable_key=publishable, bearer=bearer, library=library
    )
    ledger = LiveReviewLedger(
        call_rpc=call_rpc, publishable_key=publishable, bearer=bearer
    )
    verifier = SupabaseAuthUserVerifier(
        project_ref=PROJECT_REF,
        user_lookup=HttpsSupabaseUserLookup(
            project_ref=PROJECT_REF, publishable_key=publishable
        ),
    )
    checker = AuthorizedLitigationChecker(
        verifier=verifier, store=store,
        issuer=f"https://{PROJECT_REF}.supabase.co/auth/v1",
        audience="authenticated", publisher=ledger,
        legal_corpus_for=legal_corpus_provider(environ),
        passage_flags_for=lambda b: LivePassageFlags(
            call_rpc=call_rpc, publishable_key=publishable, bearer=b),
        fact_ledger_for=lambda b: LiveMatterFacts(
            call_rpc=call_rpc, publishable_key=publishable, bearer=b),
    )
    # M2LedgerState carries revision+packet and satisfies ReviewState
    # structurally; the ledger keeps its richer return type for callers.
    workspace_ledger = cast(ReviewLedger, ledger)
    return RequestWorkbench(
        store=store,
        ledger=ledger,
        checker=checker,
        workspace=SignedReviewWorkspace(checker, workspace_ledger),
        library=library,
        originals=AuthorizedOriginalReader(checker, storage),
    )


def signed_dev_app_ports(environ: Mapping[str, str]) -> dict[str, Any]:
    """Keyword arguments that install the SIGNED workbench into the dev app.

    Explicit opt-in (CASEPROOF_SIGNED_WORKBENCH_DEV=YES) and a publishable key
    are both required; otherwise nothing is installed. Construction performs no
    network call: every adapter calls Supabase only when a request arrives with
    a verified bearer. Shared DEV credentials are used only by running the app.
    """
    if environ.get("CASEPROOF_SIGNED_WORKBENCH_DEV") != "YES":
        return {}
    key = environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
    if not key:
        raise ValueError("signed workbench requires CASEPROOF_DEV_PUBLISHABLE_KEY")
    env = {**environ, _PUBLISHABLE_ENV: key}
    ports = live_signed_ports(env)
    if ports is None:
        raise ValueError("signed workbench requires a publishable key")
    publisher, record = ports
    library = SignedSourceLibrary(storage=SignedOriginalsStorage(publishable_key=key))
    from apps.api.signed_live_brief_composer import ComposedSignedBriefPublisher

    return {
        "signed_originals": library,
        "signed_brief_publisher": ComposedSignedBriefPublisher(
            library=library, publisher=publisher, publishable_key=key),
        "signed_review_record": record,
        "signed_workbench_factory": lambda bearer: assemble_request_workbench(env, bearer),
    }


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
