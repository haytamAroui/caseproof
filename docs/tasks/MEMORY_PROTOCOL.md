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
## Rolling memory and JSONL archive
- Read root `MEMORY.md` at the beginning of every coding session.
- After **every bounded task**, append a JSON object as one line in `docs/memory/tasks.jsonl` and update its detailed task record.
- Required event fields: `schema_version`, `event_id`, `task_id`, `status`, `summary`, `branch`, `commits`, `pr_url`, `tests`, `next_action`. Use actual SHAs and test outcomes; never invent them.
- Keep only the latest task, active blockers and next action in `MEMORY.md` (target 150 lines or less).
- Before agent handoff, long pauses or context compaction, save a checkpoint: branch, HEAD, dirty files, test results, blockers and next exact action.
- Correct history by appending a new event with `corrects_event_id`, not silently rewriting prior entries.
- Architecture decisions remain in `docs/adr/`; JSONL is the machine-readable history, CSV only a generated export.
- A memory update is durable only when committed; a future agent must cross-check Git and CI.
