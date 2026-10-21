# Agent orchestration

## Control plane
Founder chooses scope and accepts consequential tradeoffs. Tech lead owns ADR/dependency review and protects invariants. Implementers work in isolated branches or worktrees with exclusive file ownership. Reviewer is independently read-only; QA replays acceptance tests; release manager validates evidence and merges only after gates.

## Work sequence
1. Read CONSTITUTION, AGENTS/CLAUDE, ROADMAP and relevant ADR.
2. Open bounded task with business goal, acceptance and failure conditions, file ownership and prohibited changes.
3. Tech lead identifies impacted modules, security/legal dependencies and test requirements.
4. Implementer writes failure tests or fixtures, then least-change implementation.
5. Run targeted and broad checks; capture exact commands/results.
6. Reviewer challenges unsupported claims, boundaries, latency, tenancy, security, audit and migrations.
7. QA independently reproduces; release manager checks checklist and performs guarded merge.
8. Update ADR and release notes when behavior or boundaries change.

## Parallelization rules
Parallel work only with disjoint files, stable published contracts and approved migrations. One migration owner; one PR merges migrations first. Never parallel-edit shared schemas, workflow states or source-verification authority without coordination. Never let agent review its own consequential work as the only approval.

## Skill routing
- Evidence extraction and matching -> evidence-verification.
- Sensitive inputs, permissions, RLS, uploads -> security-review.
- Legal applicability, dates and monetary calculations -> legal-rules.
- AZComply adaptation -> azcomply-reuse.
- UX, accessibility, trust labels -> frontend-review.
- Every task -> caseproof-task.

## Escalation
Stop on legal ambiguity, source conflicts, privilege gaps, unknown customer data location, audit failure, schema drift and nondeterministic billing. The coordinator must ask for a scoped engineering/qualified professional decision rather than guessing.
