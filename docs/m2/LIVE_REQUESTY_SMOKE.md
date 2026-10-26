# CaseProof — live Requesty evaluation runbook

Status: manual synthetic model smoke implemented; real Requesty calls NOT YET RUN. Optional model quality does not block deterministic litigation checking.

## Setup and run

GitHub Settings > Environments > caseproof-dev-model. Restrict environment to main only, keep it separate from caseproof-dev-live-auth and limit bypass access.

Environment secret CASEPROOF_REQUESTY_API_KEY is the Requesty API key. Environment variable CASEPROOF_EXTRACTION_MODEL is the exact concrete model route, observed as mistral/mistral-small-2603 on 2026-10-26. Credentials and model availability are not independently verified.

After merge: GitHub Actions > CaseProof dev Requesty trilingual extraction smoke > Run workflow > main.

Uses the existing Requesty-only EU HTTP adapter and the EvidenceIntelligence proposal pipeline. Runs three tiny fixed synthetic NL/FR/EN legal-excerpt fixtures. Every proposal must have an exact resolvable source quote and a verified scalar value. No customer data or production DB used.

One request per language, no retries/fallback/repair; max three calls, max 384 output tokens/call, max 320 source chars/fixture, 25 sec API timeout, 5 min workflow timeout. Reported USD spend threshold 0.02, checked AFTER replies. Not a guaranteed vendor-side billing cap; an individual request can already exceed it. Configure provider-side spend cap if available. Missing cost telemetry aborts subsequent calls.

Reports only sanitized candidate counts, source-anchor correctness, gold-value presence, model ID, input/output tokens and Requesty-reported cost. Raw response, prompts, actual documents and secrets are not printed or persisted. JSON action receipt retained seven days.

Model success on these three fixtures does not establish legal veracity, semantic recall, authorized production access, Auth/RLS, permanent storage, durable review, professional validation or customer readiness. Synthetic CI does not validate a live provider; only a completed manual run can do that.

Scope: scripts/verify_live_requesty_litigation.py and apps/api/requesty_extraction.py.
