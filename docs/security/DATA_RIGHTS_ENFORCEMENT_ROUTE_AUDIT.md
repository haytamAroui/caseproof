# PR #202 — Source-version protected-route audit

**Audited:** `apps/api/litigation_development_app.py`, its mounted routers,
`application/data_rights.py`, and the rights-trigger migrations on PR #202.
**Scope:** development loopback app only; separate offline ports have their own
authorization contracts. This is a source-and-use audit, not merely a grep for
the literal `SourceVersion` class.

**Important:** `evaluate_rights` is NOT the identifier in this repository.
The pure evaluator is `evaluate_detail`; the application enforcement port is
`SignedRightsGate.require/require_bundle`; SQL uses
`caseproof._rights_require_source/_rights_require_bundle`.
There is no `REQUIRES_REVIEW` policy status: decisions are ALLOW/DENY/UNKNOWN.
`useAcrossMatters` is not granted by Storage or RLS; separate signed scope
and explicit cross-matter policy checks are mandatory.

| Mounted route or operation | Protected use | Enforcement at this head | Classification |
| --- | --- | --- | --- |
| `POST /dev/live/matters/{case}/sources/{doc}/{ver}/ingest` | Process, parser/OCR | SignedRightsGate before parsing/promotion; SQL source/parsed-result triggers | API + SQL |
| `POST /dev/live/matters/{case}/briefs/{brief}/evidence/search` | Index/search | SignedRightsGate.indexForSearch before reading representation | API |
| `POST /dev/live/matters/{case}/sources/{doc}/{ver}/crop` | Crop scanned source | SignedRightsGate.process before geometry/bytes | API |
| `POST /v2/matters/{case}/briefs/{brief}/dossier/checks`, `recheck`, `GET dossier` | Dossier verification | DossierStore.load guards full signed bundle; SQL snapshot trigger | API + SQL for writes |
| `POST /v2/matters/{case}/briefs/{brief}/dossier/releases` | Signed reviewed release | API SignedRightsGate.export on frozen source list; SQL release trigger | API + SQL |
| `GET .../dossier/releases/preview` | New-release eligibility | API signed export policy gate | API |
| `GET .../dossier/releases/{id}/artifacts/{format}` | Historical signed release read | Existing scoped signed receipt; not a new use or release | Existing read |
| `GET .../dossier/export` | Immediate unsaved JSON/Markdown/DOCX export | SignedRightsGate.export on receipt-bound source list | API |
| `POST .../dossier/corrections/preview`, `commit` | Edit derived DOCX | API SignedRightsGate.process via reopen_for_mutation, latest policy recheck before reserve and activation | API; **SQL revision RPC not yet fenced** |
| `POST .../dossier/editor/preview`, `review`, `commit` | Document-wide edits | SignedRightsGate.process in editor's signed `bound` helper | API; **SQL editor RPC not yet fenced** |
| `POST .../dossier/editor/native/preview`, `review`, `commit` | Native Word edits | Editor `bound` and native commit guarded, including reserved retry | API; **SQL activation not yet fenced** |
| `GET .../dossier/sources/{ver}/pages/{page}` | PDF page derivative | SignedRightsGate.process before creating sliced PDF | API |
| `POST .../dossier/snapshots/{hash}/crops` and `GET .../crop` | Frozen visual crop retrieval | Existing signed snapshot + digest; **no independent rights gate on the frozen crop return** | Gap to resolve or explicitly exempt as historical read |
| `POST /v2/matters/{case}/page-jobs`, page leases, page results | Durable OCR processing | SQL page-jobs/result trigger enforces current process policy on inserts and active worker changes | SQL |
| `POST /dev/live/matters/{case}/briefs/{brief}/check` (live roundtrip) | Alternative signed check | Existing signed grant only; **no rights gate on this legacy RPC** | **GAP** |
| `POST /dev/live/matters/{case}/briefs/{brief}/corrections/{preview,commit}` | Alternate legacy correction | Existing signed grant only; **no process rights gate or SQL parent version fence** | **GAP** |
| `POST /v2/matters/{case}/briefs/{brief}/check` | Optional headless checker port | Optional `checker`; when wired, does not receive SignedRightsGate | **GAP when checker injected** |
| `POST /v2/matters/{case}/briefs/{brief}/evidence/search` | Optional headless lexical search | Optional checker; when wired, does not receive SignedRightsGate | **GAP when checker injected** |
| `POST /v2/workspace/intake/matters/{case}/sources` | Four-source intake/format preflight | Registration/Storage authorization; no rights policy exists until source version is registered; **security preflight parsing vs analysis must be explicitly distinguished** | Onboarding design gate |
| Source originals/viewer/history GETs | Authorized unchanged original viewing | Matter grants and digest verification; deliberately not treated as new analytic use | Existing read |
| `POST .../dossier/confirmation`, review decisions | Human inventory attestation and review receipts | Existing signed identity and matter grants; does not mint process/export policy | Existing write |

## Database / workflow findings

- Active `caseproof-dev`: 49 source versions, 15 active matters,
  **0 rights policy revisions**. Global enablement would cause protected
  operations to deny for all preexisting sources. Never auto-backfill them
  as approved.
- The private `_rights_enforcement_control` singleton currently has
  `enabled=false`, with six installed SQL guards. This is not proof of
  genuine signed enabled behavior.
- PR #202 exact-head CI previously had 21 successes and 6 skips.
  F3/F4/F5/F6 signed live acceptances **all skipped due to workflow branch
  predicates**. No `ZERO_RESIDUAL_VERIFIED` or signed F5/F6 acceptance
  markers were produced for this head.
- The proposed security-review claims regarding `REQUIRES_REVIEW` and
  RLS enforcement of `useAcrossMatters` do not match the actual code/schema.
- Existing protection of `Storage` and source-version reading is
  matter-scoped. Do not treat it as a substitute for the separate rights
  `useAcrossMatters` decision.
- **Do not turn on a global flag or merge as active** until the legacy
  alternative routes/direct RPCs have a transactional gate, and a genuine
  JWT acceptance workflow proves both allow and deny within an isolated,
  owner-approved synthetic source cohort, followed by verified teardown.

## CI follow-up

A PR-specific signed acceptance workflow must genuinely run on this branch,
not silently skip. It must generate approved synthetic policies through the
signed `rights:manage` RPC, test revoked membership and latest-deny policy,
verify that all database-derived content is refused after revocation, and
produce `ZERO_RESIDUAL_VERIFIED` only after confirming teardown. Keep
historical data unchanged.
