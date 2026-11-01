# Remaining M1/M2 acceptance evidence

**Superseding live receipt:** PR #159 merged as `05576ba`; run [41258188700](https://github.com/haytamAroui/caseproof/actions/runs/41258188700) passed the genuine-user correction/recheck/cold-reopen/revocation path and zero-residual cleanup. Cleanup migration `20261101004423` is installed; exact failed-run recovery [41258188830](https://github.com/haytamAroui/caseproof/actions/runs/41258188830) also passed. Historical failures below remain failures, but no longer describe the latest acceptance status.


## Executed accuracy measurement

`scripts/evaluate_litigation_detection.py` runs the actual DOCX parser/reference
detector on brief-only documents from the 18 new v3 synthetic cases. Expected
references are manually enumerated separately. No answer labels or exhibit-label
appendix is added to detector inputs. Occurrence counts are retained (including
two references in the mixed-language case), not reduced to unique-document counts.

Local baseline measured on 1 November 2026:

| Cohort | Cases | TP | FP | FN | Detection recall |
|---|---:|---:|---:|---:|---:|
| NL | 4 | 4 | 0 | 0 | 100% |
| FR | 6 | 6 | 0 | 0 | 100% |
| Mixed | 2 | 3 | 0 | 0 | 100% |
| EN lettered Exhibit | 6 | 0 | 0 | 6 | 0% |

This is 13 detected reference occurrences out of 19 labelled occurrences. English
lettered Exhibit references are unsupported by the numbered Stuk/Pièce detector;
they remain unsupported-verification misses in the denominator. The new unsupported-reference detector flags all six for manual review, and canonical findings keep all their verification dimensions unassessed. This is disclosure, not support for verifying lettered Exhibit inventories. No coverage-complete flag is set.
These tiny author-labelled synthetic cohorts are **not representative-client
accuracy acceptance**, OCR accuracy or independently adjudicated semantic support.
Do not advertise their NL/FR point estimates as population guarantees.

## Independent submissions actually available

The supplied `caseproof-m0-blind-review.zip` was inspected in its current version.
It contains `REVIEWER_INSTRUCTIONS.md`, `blind_cases.json` and
`empty_review_submission.json`. The submission fields are blank; it contains no
returned reviewer assessments. Review instructions require two distinct human
assessments and Belgian procedural competence for relevant legal judgments.

Independent review cannot be closed by this implementation author filling in those
forms, by re-labelling author gold or by an AI self-review. Required evidence is
completed reviewer submissions with identity/competence verification, source hashes,
disagreements and adjudication, followed by named-owner acceptance. No such approval
is asserted here. The same distinction applies to independent security/tenant review.

## Live journey

The existing protected live workflow is enabled for the exact PR #159 branch,
while retaining the protected development environment and synthetic-only fixtures.
Its receipt must show correction commit/replay/recheck, cold process restart,
revocation, and zero-residual cleanup on the tested commit. A queued workflow,
catalog check or disposable PostgreSQL test is not this receipt.

### First protected correction execution

Run `41254845712` on commit `a675274` completed genuine Auth/private Storage,
correction commit/replay/recheck, cold reopen and revocation. It then failed the
guarded database teardown because the cleanup audit allowlist did not recognize
`dossier_draft_reserved` and `dossier_draft_activated`. Storage empty verification
passed, but zero-residual database/Auth cleanup did not. **The run is failed and
must not be called accepted.** The repeat run `41255290975` encountered the same
step. The proposed fix preserves the existing guards, allows only those two new
audit events and rejects revisions owned by another actor. Supabase requested
confirmation to replace the deletion-containing function; two confirmations
expired. No claim that this cleanup fix was installed is made.
