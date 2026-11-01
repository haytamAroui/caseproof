# ADR 0026 — Structured CaseProof frontend foundation

Date: 1 November 2026. Status: owner-requested engineering candidate in PR #162; no deployment or M3/M4 acceptance.

Decision: use a static React/Vite/strict-TypeScript client of the existing Python application API, with enforced app/feature/shared boundaries and backend-owned verification and review authority.

The single maintained UI foundation, design, interaction, security and acceptance specification is [frontend/BLUEPRINT.md](../../frontend/BLUEPRINT.md). Read and update that file for frontend work; this ADR records the decision and does not duplicate its rules. The repository constitution and evidence/security ADRs retain their authority.
