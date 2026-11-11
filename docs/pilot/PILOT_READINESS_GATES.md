# Pilot readiness follow-ups

## Frontend bundle-size follow-up

The 4 November 2026 production Vite build warned that an application chunk exceeded 500 kB after minification (about 529 kB before gzip in the local build). Measure production load time and memory on the supported pilot device and network profile, inspect the bundle composition, and split or defer code where measurements justify it. Record the measured baseline, target, resulting build and reviewer decision. Do not change the warning threshold or claim a performance problem is resolved without measurements.

This is a performance follow-up, not a substitute for the separate security, accessibility, representative corpus, operational and practitioner acceptance gates in [the P5/P6 acceptance matrix](P5_P6_ACCEPTANCE_MATRIX.md).


## 5 November 2026 independent pilot handoff

Engineering PR #198 is merged, but **does not approve confidential pilot
processing or 150/200-page capacity**. The current preflight register is
[PILOT_EXTERNAL_GATE_REGISTER.json](PILOT_EXTERNAL_GATE_REGISTER.json)
and the operational handoff is
[PILOT_EXTERNAL_ACCEPTANCE_RUNBOOK.md](PILOT_EXTERNAL_ACCEPTANCE_RUNBOOK.md).

Priorities: T70 actual independent security review, T73 deployment-specific
privacy/egress permission, T74 actual operational restore, T61 real Microsoft
Word host testing, T75 manual assistive technology. Then T76 rights-cleared
corpus, T78 two-lawyer study and T79 owner declaration. Separate D01 capacity
approval is blocked until signed full-product 50–200-page measurements for
the chosen exhibit shape. See
[CAPACITY_EXPANSION_DECISION.md](CAPACITY_EXPANSION_DECISION.md).

The public gate validator explicitly returns
\`machine_approves_pilot=false\` and
\`machine_authorizes_client_data=false\`, regardless of submitted
metadata. Actual reviewer signatures, environment approvals and permission
must be checked outside CI by authorized humans.


## Supabase MCP 5 November 2026 — T74 operational constraint

The development organization's Supabase plan is **Free** (verified through
connected project + organization metadata). Managed daily backups cannot
be presumed present; operational restore has not been tested. Supabase
database backups do **not** contain private Storage object bytes. T74 is
**BLOCKED** pending a funded/approved database **and Storage** backup
strategy, independent signed access and hash validation after isolated
restore, re-erasure and retention policy verification. No plan change,
backup export or restore was performed.
