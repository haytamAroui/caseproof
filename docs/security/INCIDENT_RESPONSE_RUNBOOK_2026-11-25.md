# SEC-13 — CaseProof Security Incident Response Runbook (25 November 2026)

**Status:** **DRAFT RUNBOOK — PENDING NAMED INCIDENT OWNER & TABLETOP REHEARSAL (`SEC-13` REMAINS OPEN).**  
**Authority:** [PILOT_DATA_SECURITY_GATE.md](PILOT_DATA_SECURITY_GATE.md) · [SEC_01_16_EVIDENCE_INVENTORY_2026-11-25.md](SEC_01_16_EVIDENCE_INVENTORY_2026-11-25.md) · [dpa-working-draft.md](../m5/dpa-working-draft.md)

> [!CAUTION]
> No client uploads are authorized until a named Incident Owner and Firm Sponsor are designated below and a tabletop rehearsal is completed for the locked pilot topology. Do **not** make unsupported SLA claims (e.g., guaranteed 24/72h resolution where contractual/legal thresholds differ).

---

## 1. Severity Classification

| Severity | Definition | Target Triage Start | Immediate Priority |
| --- | --- | --- | --- |
| **SEV-1 (Critical Confidentiality / Tenant Integrity)** | Suspected unauthorized access, cross-matter/cross-tenant exposure, leaked service/DB credential, or unauthorized OCR egress involving confidential dossier material | Immediate upon detection | Freeze access & isolate affected host/project; preserve forensic evidence; notify Incident Owner & DPO |
| **SEV-2 (High Auth / Integrity Defect)** | Exposed bearer token in logs, stale-snapshot bypass (`409` guard failure), receipt signing key exposure, or tampered/mismatched exported bytes | Same business day | Rotate affected credentials (`CASEPROOF_RECEIPT_HMAC_SECRET`, Auth/service keys); revoke active sessions; block exports |
| **SEV-3 (Medium Availability / Parser Failure)** | Corrupted archive DoS, OCR worker crash loop, or UI error without confirmed data exposure | Next business day | Isolate offending artifact hash; capture sanitized failure metrics (no raw quotes/PII) |

---

## 2. Immediate Containment Playbook

1. **Freeze Client Upload & Export Paths:**
   - Put target API behind maintenance / read-only response (`503`) or disable active matter grants on the impacted org/matter.
   - Preserve PostgreSQL `caseproof.audit_events` and immutable `caseproof.erasure_receipts` before modifying any state.
2. **Revoke & Rotate Compromised Credentials:**
   - **Receipt HMAC key (`BE-06`):** Rotate `CASEPROOF_RECEIPT_HMAC_SECRET` via zero-downtime key-ring (`CASEPROOF_RECEIPT_HMAC_PREVIOUS_SECRETS` only while draining valid receipts; remove compromised key immediately on active leak).
   - **Supabase / Auth / CI Secrets (see Issue `#214`):** Rotate Supabase `service_role` key, Management PAT, and Auth signing secrets; invalidate existing user sessions; verify rejected access with old keys.
3. **Quarantine Affected Artifacts:**
   - Never copy raw customer DOCX/PDF bytes, quotes, JWTs, or personal data into GitHub issues, CI logs, or chat transcripts. Record only opaque SHA-256 digests, timestamps, and control IDs.

---

## 3. Regulatory & Law-Firm Notification Criteria

1. **Personal Data Breach Assessment (GDPR Art. 33 / 34):**
   - Assess whether unauthorized access, disclosure, alteration, or loss of personal data occurred and document the technical risk assessment in an internal confidential incident log.
   - **Controller vs. Processor Duty:** Under the executed pilot DPA ([dpa-working-draft.md](../m5/dpa-working-draft.md)), notify the law firm (**Controller**) without undue delay after becoming aware of a personal-data breach affecting firm dossiers, supplying: nature of breach, affected data categories/matter IDs (never raw document text over unencrypted email), likely consequences, and containment actions taken.
   - Support the law firm in meeting any **Belgian APD/GBA (*Autorité de protection des données / Gegevensbeschermingsautoriteit*)** 72-hour notification deadline where required.
2. **Belgian Bar Professional Secrecy (*Secret professionnel / Beroepsgeheim*):**
   - Because litigated *conclusions* and *pièces* carry bar privilege, escalate SEV-1 events immediately to the firm's designated Partner / Bâtonnier advisor before any external third-party disclosure.

---

## 4. Tabletop Rehearsal & Sign-Off Record (`SEC-13`)

| Item | Status | Owner / Verifier | Date | Notes / Rehearsal Scenario |
| --- | --- | --- | --- | --- |
| Named Incident Owner & 1st/2nd Escalation Contacts | **OPEN** | — | — | Assign actual names & encrypted contact channels outside public Git |
| Tabletop Drill #1 (Compromised key / SEV-1 cross-tenant check) | **OPEN** | — | — | Verify `CASEPROOF_RECEIPT_HMAC_SECRET` rotation + session revocation + firm notice draft |
| Independent Reviewer Sign-Off (`SEC-13`) | **OPEN** | — | — | Required before real client data upload |
