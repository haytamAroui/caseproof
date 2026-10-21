# Test matrix
| Domain | Expected success tests | Mandatory negative/adversarial tests |
|---|---|---|
| Tenant isolation | member accesses own case | IDOR/cross-org source download; privileged bypass |
| Intake | valid document/hash | malware, path traversal, oversized, content type mismatch |
| Parser | exact source location | corrupt/rotated/scanned documents, encoding, missing spans |
| Extraction | quote-anchored typed candidates | fake quotes, prompt injection, out-of-scope blocks |
| Reconciliation | payment/invoice consistency | duplicate names, contradictory amendments, credit notes |
| Finance | exact Decimal totals | rounding, currency, rate/date boundaries |
| Legal rule packs | approved applicability | wrong jurisdiction, outdated rate, uncertain facts |
| Workflow | single idempotent output | worker kill, concurrent retry, expired lease, audit failure |
| Review | scoped signed decision | stale approval, unauthorized reviewer |
| Dossier | reproducible source index | unsupported claim, missing source, altered source version |
| Privacy | minimum data retention | leaked raw document in logs, expired signed URLs |
Run tests in CI; record critical recall and false negatives per scenario rather than marketing percentages.
