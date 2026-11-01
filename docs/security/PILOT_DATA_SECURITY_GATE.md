# CaseProof — pilot data security and professional-secrecy release checklist

**Status: OPEN / NOT APPROVED**, 28 October 2026. This appendix is an **individually evidenced authorization gate** for accessing any real client/legal matter evidence. Passing synthetic CI, using a private Supabase bucket, claiming EU hosting or using self-hosted OCR **does not approve** confidential documents. [ROADMAP M1/M5](../ROADMAP.md) · [product workflow](../PRODUCT_WORKFLOW.md) · [pre-M3 OCR topology](../contracts/PRE_M3_VERIFICATION_SPEC.md).

**Purpose:** replace the vague phrase “security sign-off” with auditable, falsifiable requirements. Every item requires status `OPEN` / `EVIDENCED` / `APPROVED` / `BLOCKED`, a named accountable reviewer, dated artifact reference (file, change, pentest report, receipt), environment, and permitted data class. A missing approval is **BLOCKED** for real customer evidence, not an assumed pass. “Not applicable” requires written rationale approved by security/privacy reviewer. Never put confidential customer content or credentials in the checklist or CI artifacts.

**Acceptance clarification:** [ADR 0025](../adr/0025-deployment-data-retention-and-model-authority.md) specifies per-mode network capture, explicit retention schedules, model-note authority and unsupported-English evidence. It does not approve any SEC item.

## Data-flow and authority inventory

Before assessment, record: actual application version/commit; deployment environment/region; data controller/processor roles; legal client, law firm and authorized actors; exact sources and confidentiality class; source file bytes, OCR representations, crops, translations, exported DOCX/reports, metadata/logs/backups, hashes, reference strings, IDs, verdicts and timing (all treated as potentially personal/confidential for handling); all services/subprocessors and cross-border transfers; retention and deletion mechanisms; intended test dates and authorized reviewers. Separate firm-managed custody from CaseProof-managed processing and immutable provenance. Identify whether source materials may contain privileged, personal, special-category or third-party data. Obtain written permission for each use and an appropriate legal basis; a redacted file is not automatically anonymous.

## Mandatory evidence checklist

| ID | Control / acceptable proof | Starting status |
|---|---|---|
| **SEC-01** | **Threat model and trust map.** Concrete architecture with diagram of browser → auth/API → private Storage/DB → isolated OCR worker → export; entry points, trust boundaries, attack scenarios for prompt injection, file bombs, cross-tenant bleed, OCR spill and stolen review links; reviewed risk owners and mitigations | **OPEN** |
| **SEC-02** | **Encryption in transit.** TLS/HTTPS on all client/service/internal paths, enforcement/test evidence and no insecure fallback for document bytes, crops, tokens or reports | **OPEN** |
| **SEC-03** | **Encryption at rest and keys.** Storage, DB, derived OCR, logs, queues, backups and temp storage protection, key ownership/rotation and secret storage; tested access controls; document what is not encrypted | **OPEN** |
| **SEC-04** | **Authentication / authorization.** Signed identity, per-matter and per-action permissions, refresh/logout/expiry, server-controlled tenancy, Supabase RLS policy inspection plus genuine signed-user denial across same/cross tenants, revocation and stale signed URLs | **OPEN** |
| **SEC-05** | **Original-byte provenance.** Immutable preserved originals with SHA-256 readback, representation and crop lineage, source versioning, audit event append-only/tamper-evidence and recovery on restart; no claim that hashing authenticates a third-party document | **OPEN** |
| **SEC-06** | **OCR location and egress.** Named approved runtime/hosting/worker/version; prove client source pixels processed inside approved restricted boundary with denied unauthorised outbound OCR/AI, controlled temp files and worker isolation; if any third-party OCR/model: named provider + documented data flow, processor review and separate approval | **OPEN** |
| **SEC-07** | **Data minimization.** No raw documents, OCR passages, crops, complete legal quotes, tokens, prompts or personal data in generic tracing, exception trackers, analytics, staging support tools or shared test accounts; tested log sanitization | **OPEN** |
| **SEC-08** | **Retention/deletion.** Customer-visible schedule stating what is kept, where, actual duration and permitted access roles across originals, derivatives, audit, reports, temporary files, backups and caches; verified delete/revoke export behavior and documented legal-hold or backup exceptions | **OPEN** |
| **SEC-09** | **Subprocessor / transfers.** Inventory of hosting, storage, logging, OCR, AI and support vendors; contract/DPA where required, location, onward transfer and international safeguards review; record any subprocessors not yet approved | **OPEN** |
| **SEC-10** | **Lawful role and professional-secrecy signoff.** Document controller/processor roles, confidentiality terms, legal basis and DPA/firm authorization; verify bar/professional-secrecy expectations with appropriate Belgian counsel or authorized firm reviewer; record GDPR DPIA assessment and DPIA if required | **OPEN** |
| **SEC-11** | **File and model security.** Malware/zip/decompression-bomb handling, parser isolation, file size/page count/job time budgets, PDF action/link sanitation, prompt injection rejection, MIME/content validation, known parser advisories and failure states; adversarial test receipts | **OPEN** |
| **SEC-12** | **Penetration/security test.** Independent risk-proportionate security assessment (penetration test or justified equivalent), authenticated tenant isolation, OWASP-style web/API risks, Storage policy, OCR worker, reviewer/edit/export; findings triaged and critical/high issues remediated before client uploads | **OPEN** |
| **SEC-13** | **Incident response.** Named incident owner/contact and escalation process, breach assessment/documentation, notice criteria/time frames under GDPR/contracts, tested response path, no unsupported guarantee of 24/72-hour reporting in all cases | **OPEN** |
| **SEC-14** | **Backup, disaster recovery and availability.** Restore test of permitted evidence, hash and reviewer/audit lineage; recover from incomplete OCR/check/export, loss of process and unknown acknowledgment; recovery objectives and documented data loss risks | **OPEN** |
| **SEC-15** | **Reviewer/export control.** Actor role and current-action approval checks, immutable scoped manifest and report, no unintended recipient share, expiring URLs, correct source links, demonstrated non-replay/stale-version rejection and negative logout tests | **OPEN** |
| **SEC-16** | **Support and deployment runbook.** Version-pinned deployment, rollback, on-call/support procedure, package dependency scanning, patch cadence, monitoring without sensitive data, customer deletion/offboarding, operational authority and pilot incident contacts | **OPEN** |

## Explicit data-use gate

- **Synthetic-only development:** permitted under ordinary repo/dev controls and fixture license; **does not grant permission to process client evidence**.
- **Rights-cleared material that is actually non-confidential:** require verified rights/source provenance and documented restrictions; do not infer this from the label “redacted.”
- **Client or confidential legal material:** **BLOCKED** until SEC-01..16 are reviewed, appropriate legal/security controls are approved for the *exact* environment, signed pilot terms/permissions exist, and the named firm owner acknowledges the scope. Any material unresolved/high security issue blocks. Reviewer records can approve a specific pilot configuration, not the whole product or all future clients.
- **Commercial release:** separate gate after M4 technical acceptance and M5 practitioner/commercial evidence; a signed paid-pilot interest letter does not authorize uploads by itself.

## Signoff record template

```text
Environment + region:
App commit / parser OCR version:
Authorized matter/data class + permitted pilot dates:
File types, page budget and intended user actions:
SEC-01 .. SEC-16 status, owner, dated evidence links:
Subprocessor data-flow map + DPA review:
Professional-secrecy / GDPR reviewer decision:
Security reviewer decision + unresolved findings:
Law-firm authorized sponsor decision:
Scope expiry, rollback and incident owner:
Final disposition: BLOCKED / APPROVED FOR THIS EXACT PILOT
```

This checklist does **not** replace advice from a Belgian qualified professional or constitute legal approval. It defines what engineering and pilot operators must demonstrably produce before real data is processed.
