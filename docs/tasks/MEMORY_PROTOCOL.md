# Durable task-memory protocol

The root `MEMORY.md` is a **short recovery index**. This directory holds the durable record for each bounded implementation task. Do not use chat history as the sole record of decisions or progress.

## Required task record

```markdown
# TASK-ID — concise title
Status: planned | in_progress | blocked | in_review | merged | verified | reverted
Roadmap: P#-##
Branch:
PR:
Commits: (full SHAs, only after created)
Last checked (UTC):

## Goal and why it matters
## Preconditions / approvals / dependencies
## Scope: files and modules allowed to change
## Non-goals / prohibited changes
## Acceptance criteria
## Implementation and decisions
## Tests actually run (commands, environment, outcomes)
## Security / tenancy / provenance / privacy review
## Known failures, blockers and risks
## What is NOT done
## Recovery checkpoint (branch, HEAD, dirty files, next exact action)
## Next task and handoff
```

## Rules
- One task record per bounded task; update it as the task evolves.
- A claim is `verified` only if code, tests, review and the applicable gate support it.
- Record actual SHAs and links; never predict a future merge SHA.
- Keep summaries factual and brief. Link to ADRs for architectural rationale.
- Avoid secrets, customer evidence and raw sensitive logs.
- Root `MEMORY.md` must be updated whenever the task changes durable state.
- If an agent crashes, a new agent checks Git and CI **before** trusting this record.
