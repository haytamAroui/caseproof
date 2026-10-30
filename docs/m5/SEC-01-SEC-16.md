# CaseProof M5 security gate — evidence register

**Status:** NOT AUTHORIZED FOR REAL CLIENT DATA. These are evidence requests, not certifications. `PARTIAL` means only a subset is evidenced; `UNVERIFIED` and `FAIL` block release. Each control requires reviewer, timestamp, reproducible command, artifact URI, and independent sign-off.

| ID | Control | Existing evidence or target | Status | Exit criterion |
|---|---|---|---|---|
| SEC-01 | Matter authorization | Signed PostgREST ungranted/revoked denial tests | PARTIAL | Re-run with real client-role matrix |
| SEC-02 | Storage isolation | Private Storage signed read denial and SHA checks | PARTIAL | Threat model paths and public URL enumeration |
| SEC-03 | Encryption in transit | TLS endpoint configuration and worker transport | UNVERIFIED | Record independent TLS configuration evidence |
| SEC-04 | Encryption at rest | Supabase database, backups and object storage | UNVERIFIED | Obtain provider and project-specific evidence |
| SEC-05 | EU data residency | Project region, backups and OCR worker region | UNVERIFIED | Capture project region and processing topology |
| SEC-06 | Subprocessor inventory | Supabase, hosting, monitoring, email, OCR dependencies | UNVERIFIED | List legal entities, locations, purposes and transfer terms |
| SEC-07 | Professional secrecy | Belgian law firm confidentiality and access contract | UNVERIFIED | External Belgian counsel review |
| SEC-08 | DPA and roles | Controller/processor roles and GDPR Article 28 terms | DRAFT | Execute with pilot firm |
| SEC-09 | Retention schedule | Pilot expiry and document lifecycle | FAIL | Implement tested retention job and suspension/legal-hold policy |
| SEC-10 | Erasure | Source, derivatives, OCR, backups and logs | FAIL | Prove deletion and backup expiry with independent verification |
| SEC-11 | Audit integrity | Append-only review ledger and signed reviewer identity | PARTIAL | Adversarial audit and tamper testing |
| SEC-12 | Secrets management | GitHub environment secrets and no service-role client key | PARTIAL | Rotation and leak response rehearsal |
| SEC-13 | Incident response | Breach handling, triage and notice responsibilities | UNVERIFIED | Run tabletop and define contractual notification period |
| SEC-14 | Availability and recovery | Backup restore, RTO/RPO and failure handling | UNVERIFIED | Run restore drill |
| SEC-15 | Dependency and worker isolation | OCR sandbox, malware scanning, parser resource budgets | UNVERIFIED | Adversarial file and resource test |
| SEC-16 | Human review and accuracy | No unsupported verified state; uncertainty/crops | PARTIAL | Blinded dossier accuracy evaluation and error analysis |

## Required evidence form (repeat per control)
- Control ID, risk and affected systems
- Responsible engineer and independent reviewer
- Exact configuration and environment (`caseproof-dev` is not production)
- Test command, expected/actual result, CI run, date, evidence checksum
- Residual risk and acceptance decision

## Release rule
No real client upload until all sixteen controls are independently signed off, a DPA is executed, legal secrecy review is complete, and deletion/backup behavior is proven. Historical passing CI cannot substitute for these controls.
