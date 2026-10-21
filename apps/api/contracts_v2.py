"""KRN-109: executable v2 I/O contracts and non-authoritative preflight.

These Pydantic models are boundary contracts, NOT live HTTP routes.
Do not register /v2 routes or use these preflight test doubles to authorize
a real actor, state transition, exception, audit write, or customer operation.
The existing development /v1 API remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "2.0.0-draft"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=256)]
PositiveRevision = Annotated[int, Field(ge=1)]
NonemptyReason = Annotated[str, Field(min_length=1, max_length=4000)]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TextSpanLocator(StrictContract):
    kind: Literal["text_span"]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    basis: Literal["unicode_codepoint_zero_based_half_open"]

    @model_validator(mode="after")
    def verify_bounds(self) -> TextSpanLocator:
        if self.end <= self.start:
            raise ValueError("text span must be nonempty and half-open")
        return self


class PdfRegionLocator(StrictContract):
    kind: Literal["pdf_region"]
    page_index: Annotated[int, Field(ge=0)]
    x0: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    y0: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    x1: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    y1: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    page_width: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    page_height: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    rotation: Literal[0, 90, 180, 270]
    basis: Literal["pdf_points_unrotated_bottom_left"]

    @model_validator(mode="after")
    def verify_geometry(self) -> PdfRegionLocator:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("nonempty PDF bounding box required")
        if self.x1 > self.page_width or self.y1 > self.page_height:
            raise ValueError("PDF bounding box must be inside page")
        return self


class SheetRangeLocator(StrictContract):
    kind: Literal["spreadsheet_range"]
    sheet_id: Identifier
    a1_range: Annotated[str, Field(pattern=r"^[A-Z]+[1-9][0-9]*:[A-Z]+[1-9][0-9]*$")]
    basis: Literal["spreadsheet_a1_sheet_id"]


class StructuredFieldLocator(StrictContract):
    kind: Literal["structured_field"]
    schema_id: Identifier
    path: Annotated[list[str | int], Field(min_length=1)]
    basis: Literal["json_path_v1"]

    @model_validator(mode="after")
    def check_path(self) -> StructuredFieldLocator:
        if any(
            type(value) is bool
            or (type(value) is int and value < 0)
            or (type(value) is str and not value)
            for value in self.path
        ):
            raise ValueError("structured path must contain nonempty keys or nonnegative indices")
        return self


Locator = Annotated[
    TextSpanLocator | PdfRegionLocator | SheetRangeLocator | StructuredFieldLocator,
    Field(discriminator="kind"),
]


class EvidenceAnchorInput(StrictContract):
    anchor_id: Identifier
    document_id: Identifier
    version_id: Identifier
    source_sha256_hex: Digest
    representation_id: Identifier
    representation_sha256_hex: Digest
    locator: Locator


class QuoteContent(StrictContract):
    kind: Literal["quote"]
    text: NonemptyReason


class JsonScalarContent(StrictContract):
    kind: Literal["json_scalar"]
    value: str | int | bool | None

    @model_validator(mode="after")
    def check_scalar(self) -> JsonScalarContent:
        if type(self.value) not in (str, int, bool, type(None)):
            raise ValueError("only exact JSON scalar string, integer, bool or null supported")
        return self


ExpectedContent = Annotated[QuoteContent | JsonScalarContent, Field(discriminator="kind")]


class CandidateRequest(StrictContract):
    case_id: Identifier
    finding_id: Identifier
    statement: NonemptyReason
    expected_case_revision: PositiveRevision
    idempotency_key: Identifier


class EvidenceLinkRequest(StrictContract):
    case_id: Identifier
    finding_id: Identifier
    statement_revision: PositiveRevision
    link_id: Identifier
    expected_assessment_revision: PositiveRevision
    anchor: EvidenceAnchorInput
    expected_content: ExpectedContent
    proposed_semantic_relation: Literal[
        "supports", "contradicts", "qualifies", "inconclusive", "not_assessed"
    ]
    rationale: NonemptyReason
    idempotency_key: Identifier


class LifecycleState(StrEnum):
    CANDIDATE = "candidate"
    EVIDENCE_GROUNDED = "evidence_grounded"
    REVIEW_READY = "review_ready"
    APPROVED_CONCLUSION = "approved_conclusion"


class PromotionRequest(StrictContract):
    case_id: Identifier
    target_state: LifecycleState
    expected_case_revision: PositiveRevision
    expected_manifest_revision: PositiveRevision
    expected_policy_version: Identifier
    idempotency_key: Identifier
    decision_rationale: NonemptyReason


class BusinessExceptionRequest(StrictContract):
    case_id: Identifier
    expected_case_revision: PositiveRevision
    expected_manifest_revision: PositiveRevision
    idempotency_key: Identifier
    reason: NonemptyReason
    affected_issue_ids: Annotated[list[Identifier], Field(min_length=1)]

    @model_validator(mode="after")
    def nonduplicate_issues(self) -> BusinessExceptionRequest:
        if len(self.affected_issue_ids) != len(set(self.affected_issue_ids)):
            raise ValueError("affected issue IDs cannot repeat")
        return self


class CoverageIssueResponse(StrictContract):
    issue_id: Identifier
    status: Literal["open", "supported", "qualified", "contradicted", "unresolved"]
    blocker_codes: list[str]


class CoverageResponse(StrictContract):
    case_id: Identifier
    scope_version: PositiveRevision
    manifest_revision: PositiveRevision
    policy_version: Identifier
    ordinary_complete: bool
    issues: list[CoverageIssueResponse]
    excluded_source_ids: list[Identifier]


class ApiError(StrictContract):
    code: Literal[
        "authentication_required", "permission_denied", "not_found",
        "stale_revision", "idempotency_conflict", "invalid_transition",
        "gate_blocked", "audit_unavailable", "invalid_request",
    ]
    message: str


class PreflightCode(StrEnum):
    AUTHENTICATION_REQUIRED = "authentication_required"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    STALE_REVISION = "stale_revision"
    INVALID_TRANSITION = "invalid_transition"
    GATE_BLOCKED = "gate_blocked"
    AUDIT_UNAVAILABLE = "audit_unavailable"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    APPLICATION_REVIEW_REQUIRED = "application_review_required"


@dataclass(frozen=True, slots=True)
class VerifiedPrincipalForTest:
    """Trusted-server *fixture only*. Construction does NOT authenticate anyone."""

    tenant_scope: str
    actor_ref: str
    permissions: frozenset[str]
    is_authenticated_human: bool


@dataclass(frozen=True, slots=True)
class AuthoritativeFactsForTest:
    """Fixture for would-be server-owned facts; NEVER accept from an HTTP body."""

    owner_tenant_scope: str
    current_case_revision: int
    current_manifest_revision: int
    effective_policy_version: str
    current_state: LifecycleState
    grounding_eligible: bool
    review_packet_ready: bool
    ordinary_complete: bool
    no_material_conflicts: bool
    policy_sufficiency_met: bool
    audit_write_available: bool


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """No positive authorization/result code: only denial or further review."""

    code: PreflightCode
    http_status_if_denied: int | None

    @property
    def requires_application_commit(self) -> bool:
        return self.code is PreflightCode.APPLICATION_REVIEW_REQUIRED


TRANSITIONS: dict[LifecycleState, LifecycleState] = {
    LifecycleState.CANDIDATE: LifecycleState.EVIDENCE_GROUNDED,
    LifecycleState.EVIDENCE_GROUNDED: LifecycleState.REVIEW_READY,
    LifecycleState.REVIEW_READY: LifecycleState.APPROVED_CONCLUSION,
}

ROUTE_MODELS: dict[str, type[BaseModel] | None] = {
    "POST /v2/evidence-anchors": EvidenceAnchorInput,
    "POST /v2/findings": CandidateRequest,
    "POST /v2/findings/{id}/evidence": EvidenceLinkRequest,
    "GET /v2/cases/{id}/coverage": None,
    "POST /v2/cases/{id}/promotion": PromotionRequest,
    "POST /v2/cases/{id}/exception-dispositions": BusinessExceptionRequest,
}


def request_fingerprint(payload: PromotionRequest) -> str:
    """Stable hash for an already validated request body, not actor authority."""
    raw = payload.model_dump_json(exclude_none=False).encode("utf-8")
    return sha256(b"krn109-promotion-v1\x00" + raw).hexdigest()


def promotion_preflight(
    request: PromotionRequest,
    *,
    principal: VerifiedPrincipalForTest | None,
    facts: AuthoritativeFactsForTest | None,
    prior_request_fingerprint: str | None = None,
) -> PreflightResult:
    """Contract-only deny/review matrix; NEVER authorizes or writes a transition.

    Principal and facts may only be supplied from an authenticated application
    in production, which is NOT present in this Stage 1 contract slice.
    """
    if not isinstance(request, PromotionRequest):
        raise TypeError("validated promotion request required")
    if principal is None:
        return PreflightResult(PreflightCode.AUTHENTICATION_REQUIRED, 401)
    if facts is None or principal.tenant_scope != facts.owner_tenant_scope:
        return PreflightResult(PreflightCode.NOT_FOUND, 404)

    required_permission = (
        "conclusion:approve" if request.target_state is LifecycleState.APPROVED_CONCLUSION
        else "finding:promote"
    )
    if required_permission not in principal.permissions or (
        request.target_state is LifecycleState.APPROVED_CONCLUSION
        and not principal.is_authenticated_human
    ):
        return PreflightResult(PreflightCode.PERMISSION_DENIED, 403)

    if prior_request_fingerprint is not None:
        if prior_request_fingerprint != request_fingerprint(request):
            return PreflightResult(PreflightCode.IDEMPOTENCY_CONFLICT, 409)
        # Identical retries must retrieve a DURABLE prior result from a
        # server-side store. This Stage 1 contract cannot assert success.
        return PreflightResult(PreflightCode.APPLICATION_REVIEW_REQUIRED, None)

    if (
        request.expected_case_revision != facts.current_case_revision
        or request.expected_manifest_revision != facts.current_manifest_revision
        or request.expected_policy_version != facts.effective_policy_version
    ):
        return PreflightResult(PreflightCode.STALE_REVISION, 409)

    if TRANSITIONS.get(facts.current_state) is not request.target_state:
        return PreflightResult(PreflightCode.INVALID_TRANSITION, 409)

    gate_met = (
        facts.grounding_eligible
        if request.target_state is LifecycleState.EVIDENCE_GROUNDED
        else facts.review_packet_ready
        if request.target_state is LifecycleState.REVIEW_READY
        else (
            facts.review_packet_ready
            and facts.ordinary_complete
            and facts.no_material_conflicts
            and facts.policy_sufficiency_met
        )
    )
    if not gate_met:
        return PreflightResult(PreflightCode.GATE_BLOCKED, 409)

    if not facts.audit_write_available:
        return PreflightResult(PreflightCode.AUDIT_UNAVAILABLE, 409)
    return PreflightResult(PreflightCode.APPLICATION_REVIEW_REQUIRED, None)


def draft_openapi() -> dict[str, object]:
    """Generate formal OpenAPI 3.1 request/response schemas for DESIGN review.

    This is not served by the running FastAPI v1 app. No v2 implementation
    should be inferred from these operation descriptions.
    """
    routes: dict[str, dict[str, object]] = {}
    for signature, model in ROUTE_MODELS.items():
        method, path = signature.split(" ", 1)
        request_body: dict[str, object] = {}
        if model is not None:
            request_body = {
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": model.model_json_schema()}
                    },
                },
            }
        response_schema = (
            CoverageResponse.model_json_schema() if method == "GET"
            else {"type": "object", "description": "Not implemented in Stage 1"}
        )
        routes.setdefault(path, {})[method.lower()] = {
            "summary": "Contract proposal only; endpoint is not enabled",
            "operationId": (
                method.lower() + "_"
                + path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
            ),
            **request_body,
            "responses": {
                "200": {
                    "description": "Proposed response shape; no live endpoint",
                    "content": {"application/json": {"schema": response_schema}},
                },
                **{
                    str(code): {
                        "description": "Failure response",
                        "content": {
                            "application/json": {"schema": ApiError.model_json_schema()}
                        },
                    }
                    for code in (401, 403, 404, 409, 422)
                },
            },
        }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "CaseProof Evidence API (non-deployed contract draft)",
            "version": SCHEMA_VERSION,
            "description": (
                "Schema only. No v2 routes are registered, no authorization "
                "or durable audit implemented."
            ),
        },
        "paths": routes,
    }
