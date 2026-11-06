# PR #204 — Release Acknowledgment & Named Provenance

**Status:** draft implementation, 6 November 2026. **NOT a legal electronic signature or court-filing certificate.** Target: existing merged PR #203 security boundary.

## Decision

Distinguish three actors: (1) human finding reviewers identified by their existing persisted signed review IDs, (2) the authenticated **release actor**, and (3) an optional professional approver (not implemented in PR204). Signing into an account is not a substitute for explicit release intent; however, a checkbox is **not** proof against misuse of an unattended unlocked session.

There is no organization-verified professional-name directory in the current schema. PR204 **never** claims a professional name from editable JWT metadata or browser request data. The release actor is an Auth-verified UUID; for readability the backend may attach the **confirmed Auth email** as an account label. Otherwise it uses `Account <UUID>`. Neither label establishes lawyer credentials. Professional names and optional reauthentication/approval policy require a separate organization-governed feature.

## New release contract

- `POST .../dossier/releases` now requires `release_acknowledged: true` and `acknowledgement_version: "caseproof-release-ack-v1"`. The typed JSON body rejects false, missing or unexpected fields. The frontend provides **one deliberate second step** (review details, then acknowledge and create), with the existing distinct partial-review checkbox retained.
- No client-supplied `actor_id`, `signature_name`, timestamp or signoff certificate is accepted.
- The signed backend checks the actor against Supabase Auth and resolves a confirmed-email account label, then freezes an acknowledgment containing actor ID/label type, release ID, snapshot SHA-256, scope, versioned notice, and UTC timestamp **inside** the existing server-HMAC/SHA-256 manifest.
- SQL `release_acknowledgement_fence` independently checks the bound actor against the trusted release-row `actor_id`, exact release ID, snapshot, release type and a time-bounded timestamp on INSERT. There are no changes to old frozen rows.
- DOCX appendix, JSON and inert Markdown disclose the released-by identity with limitations; they do not rewrite the original draft, attest that the actor checked every finding, or claim filing/approval.
- Existing lost-response reconciliation returns the same frozen release. Historical downloads do not request fresh acknowledgment; existing releases without this field remain explicitly legacy.

## Testing / rollout

- Exact offline F6 release contract, DOCX extraction, missing/false acknowledgment, historical HMAC tampering, actor-specific replay.
- Browser release confirmation and partial-scope flow, signed genuine-JWT workflow, cold-reopen, revocation and cleanup.
- Disposable SQL migration test must cover a genuine actor/snapshot match and reject mismatches. No production deployment based solely on this PR.
- **Before merge:** check all CI and signed-browsing gates; before any practitioner confidential-client pilot, require independent security and practitioner approval.

## Follow-on intentionally out of scope

Firm-controlled verified legal name directory; organization-level policy for formal approvers, fresh reauthentication/passkeys, second-lawyer separation-of-duties, and qualified signatures. Those must not be implied by this release-intent receipt.
