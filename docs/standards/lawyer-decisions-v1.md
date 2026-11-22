# Lawyer decisions v1 (roadmap task 3)

Status: decision model + development-only API implemented
(`application/litigation/lawyer_decisions.py`,
`apps/api/lawyer_decisions_api.py`, tests in `tests/test_lawyer_decisions.py`).
No production mount, no persistence (signed actor authorization and atomic
persistent events remain the integration gate, as with the M2 review cycle).
What an accepted waiver PERMITS is the user's pending product decision
(task 2) and is not decided here.

## The four dispositions

`confirmed`, `qualified`, `rejected`, `waived` — recorded over ONE exact
machine rule result (task 1 contract), with motive (`rationale`) and scope.

Hard rules enforced by the model:

- The original machine finding is preserved verbatim on the decision
  (`machine_status`, `machine_reason`, `input_hashes`) and is never
  rewritten. A waived FAIL stays a FAIL; views and API responses always
  carry the machine status separately from the disposition.
- A waiver answers an exception, i.e. any non-PASS result (FAIL,
  UNDETERMINED or UNVERIFIED): the lawyer decides on every exception, and a
  PASS has nothing to except. It records that the lawyer accepts the
  exception, with motive and scope. It grants nothing: export behavior and
  any "ready with exceptions" state belong to task 2 (user-owned).
- Every decision carries a `content_hash` (sha256 over the canonical
  decision content) for traceability.

## Binding and invalidation on recompute

A decision binds the exact result it answers: `rule_id`, `rule_version`,
`reference`, `input_hashes` AND `result_fingerprint`, a sha256 over the full
canonical result (status, reason, scope, preconditions, sub-results).
`validate_decision` re-checks it against the current result after any
recompute:

- `rule_version_changed` — the rule version moved;
- `inputs_changed` — the input hashes differ;
- `machine_status_changed` — the machine verdict moved;
- `result_no_longer_produced` — the result disappeared;
- `result_content_changed` — same rule, version, inputs and status, but the
  finding's reason, scope, preconditions or sub-results moved.

An invalidated decision surfaces as invalidated; it never silently carries
over to a new machine state. Validating a decision against a different rule
or reference is rejected.

## API (development-only, no production mount)

`POST /v2/rule-runs/{run_id}/decisions` records a disposition: the client
names only the rule and reference; the server binds to its OWN stored
result, derives the actor from the bearer via the injected resolver, and
returns the decision with its traceability hash.
`GET /v2/rule-runs/{run_id}/decisions` lists decisions re-validated against
the current results, plus the results that still have no decision.

## Explicitly not done

- No persistence, no signed authorization wiring (integration gate).
- No export gating or readiness semantics (task 2, user-owned).
- No React/interface wiring (roadmap tasks 9/10).
