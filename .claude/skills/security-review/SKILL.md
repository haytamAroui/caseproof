---
name: security-review
description: CaseProof security-review workflow
---

# security-review

Check input constraints, authorization and tenant containment, RLS including privileged code, storage policies, signed URLs, secure uploads, immutable audit and prompt privacy. Require negative cross-tenant tests.

## Quality gate
Every change must satisfy CONSTITUTION.md and the task-specific failure tests. Record proof and unknowns; escalate before crossing approval boundaries.
