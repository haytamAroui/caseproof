# PR #203 — Signed Export Rights Manifest

**Status:** draft engineering change; pilot and independent legal/security acceptance pending.
**Basis:** PR #202 enforced Data Rights Ledger, ADR 0032 reviewed release and ADR 0034 review-completeness scope.

## Contract

When `ENFORCE_DOCUMENT_RIGHTS=true`, a new reviewed release includes a
`rights_attestation` object in the existing
`caseproof-reviewed-release-v1` manifest. It is immutable with the release
and covered by the **existing server-side HMAC receipt** and independent
`manifest_sha256`. No client key, new portability claim or court filing
certificate is introduced.

Example **synthetic** envelope:

```json
{
  "rights_attestation": {
    "schema": "caseproof-export-rights-v1",
    "action": "export",
    "scope": "same_matter",
    "decision": "allow",
    "sources": [
      {
        "document_id": "11111111-1111-4111-8111-111111111111",
        "version_id": "22222222-2222-4222-8222-222222222222",
        "original_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "policy_version": 3,
        "decision": "allow"
      }
    ]
  }
}
```

Each source comes from the **server-frozen snapshot**, not the browser.
IDs, SHA-256, decision and exact child source-policy revision are checked. No
rights authorization reference, source text, policy JSONB or bearer is exposed.

## Release-boundary order

1. Verify signed actor, matter export grant, immutable source bundle, current
   draft and inventory confirmation through existing F6 boundaries.
2. Require ALLOW for export on **all** frozen source versions; missing or
   denied policy fails closed. Build the deterministic attestation from those
   evaluated `Evaluation` objects.
3. Validate human review completeness and explicit partial acknowledgment.
   Preserve text-coverage uncertainty rather than treating complete review as
   complete discovery.
4. Generate and independently parse bounded JSON, Markdown, DOCX; compute
   artifact digests/lengths. Bind the rights attestation into the overall
   signed manifest and digest.
5. Before the trusted write, re-evaluate and reject any changed policy version,
   not merely a still-ALLOW result.
6. The new SQL `rights_z_export_manifest_fence` trigger executes inside
   the release INSERT transaction. Existing `rights_export_release` enforces
   current export rights on the full active bundle. The PR203 trigger then
   checks a complete matching source set, SHA-256, same-matter scope, export
   decision, and **exact latest policy_version** of each source. The shared
   case lock serializes with `rights:manage` revocation.
7. On status, list, replay and artifact read, validate the historical
   attestation structure, complete receipt/HMAC and manifest hash. Original
   artifact bytes are checked against the frozen artifact SHA-256 and size.

## Historical and migration behavior

- **Do not rewrite old HMAC-signed releases.** Legacy manifests lacking
  `rights_attestation` reopen under their original signed historical-release
  contract; they are not to be labeled "rights attested."
- Rights attestations describe decisions **at the time of release**. They
  are not reusable permission grants or current-rights approvals.
- When the DB enforcement switch is ON, the new trigger requires the rights
  attestation for **every new** inserted release. When OFF, it preserves
  pre-enforcement disposable fixtures; that mode is not evidence of a
  rights-attested product. Development composition uses the PR202 rights gate
  when `ENFORCE_DOCUMENT_RIGHTS=true`.
- SQL `_rights_require_source` handles latest ancestor restrictions on
  derived DOCX sources, and the signed projection exposes effective parent
  constraints. The PR203 per-source `policy_version` refers to the **child
  source's own policy revision**; ancestor policy lineage is enforced live but
  is not yet separately serialized as a version chain in this manifest.
- The server receipt is a **server-verifiable HMAC**, not an asymmetric digital
  signature, external timestamp authority or qualified electronic signature.
  Claims of independently verifiable portable signature are out of scope.
- No production migration, existing dossier backfill, external egress, RAG,
  new AI call, policy grant, or rights elevation is authorized here.

## Negative and acceptance checks

- Offline unit tests: ALLOW/UNKNOWN/DENY, malformed policy version, forged
  SHA and document/version identity, duplicate/extra source, wrong scope,
  tampered HMAC-covered proof, replay and historical read, and policy-change
  race between artifact generation and release POST.
- Disposable PostgreSQL: valid complete attestation passes; missing proof,
  stale policy version, swapped digest, and a DENY-labelled proof are refused
  by the SQL trigger. Existing revocation and retention guards must remain
  green.
- Real signed browser: approved four-source NL/FR fixture, reviewed release,
  receipt and rights source-version digest match, Word-compatible DOCX
  readback, cold reopen, export-grant revocation and whole-matter revoke.
  Genuine-JWT run must prove teardown and `ZERO_RESIDUAL_VERIFIED`.

## Release gates

- [ ] CI exact-head suite green with no failed tests
- [ ] PR203 disposable PostgreSQL positive and negative proofs green
- [ ] Development SQL migration installed and security advisors reviewed
- [ ] Genuine signed PR203 F3–F6 workflow green, with no skipped signed acceptance
- [ ] Existing historical signed releases still readable under valid current grants
- [ ] Independent security/practitioner sign-off (pilot policy)

Keep the PR draft until these checks are completed. Document the actual
GitHub Actions run URLs, not placeholder or synthetic PASS markers.
