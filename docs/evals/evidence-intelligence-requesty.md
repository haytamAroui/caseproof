# Running the Evidence Intelligence Requesty evaluation

Default commands have no billable inference:

```bash
uv run python -m scripts.run_topology_comparison --show-call-budget
uv run python -m scripts.run_topology_comparison
```

The four labeled repository-owned PDF, XML, EML and negated text sources
are **synthetic**. The default uses deterministic scripted responses, not a live
accuracy/cost baseline.

For live Requesty validation, provision an isolated **loopback disposable**
PostgreSQL database with the proposal EI-001 checkpoint schema and an active
test organization/case/member with case:read + finding:write. Set these
environment variables **without committing secrets**:

```bash
export CASEPROOF_EVAL_DISPOSABLE_POSTGRES_DSN="host=127.0.0.1 dbname=caseproof_eval_test user=..."
export CASEPROOF_REQUESTY_API_KEY="..."        # or REQUESTY_API_KEY
export CASEPROOF_EXTRACTION_MODEL="provider/model"
```

Read the preflight call budget first, then explicitly acknowledge its exact
count and provide trusted disposable UUIDs and a unique run ID:

```bash
uv run python -m scripts.run_topology_comparison --live-requesty \
  --acknowledge-max-calls <PREFLIGHT_CALL_CAP> \
  --org-id <TEST_ORG_UUID> --case-id <TEST_CASE_UUID> \
  --actor-id <TEST_ACTOR_UUID> --run-id <UNIQUE_RUN_ID>
```

This operation **may incur charges**. It preserves provider replies and
OUTCOME_UNKNOWN; never blindly retry an uncertain dispatch. The call ceiling
bounds requests, **not** the provider's final billing. Inspect Requesty's
pricing/model configuration and set an appropriate account budget before use.

Pair topology measures label matches, quote resolution and reported Requesty
tokens/cost. Four synthetic documents cannot prove statistical extraction
accuracy, four-pass benefit, legal/payment correctness, production latency or
customer ROI. A consented independently labeled holdout corpus and review of
misattribution/contradictions are required before any parity claim.
