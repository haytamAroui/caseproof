# ADR 0020 — API contract validation architecture

Status: Accepted for the current CaseProof frontend/backend boundary.

## Decision

CaseProof uses Pydantic as the authority for backend-owned API contracts.
JSON Schema, TypeScript types, and AJV runtime validators are generated artifacts.
Changes to this validation architecture require demonstrated correctness, security,
compatibility, or operational benefits, not library preference.

Strict API request DTOs reject unknown fields via `ConfigDict(extra="forbid")`.
Versioned or intentionally extensible response/domain projections retain their
documented extension semantics. Do not globally change `extra` settings.

The existing Python and frontend contract generation/check commands are authoritative:
`uv run --locked python -m scripts.generate_frontend_contract --check` and
`npm run contracts:check` in `frontend/`. The Frontend foundation workflow
runs both checks before its test/build stages.

## Validation requirements

For each new request DTO, test the real HTTP boundary as well as direct Pydantic
validation. For each generated response contract, test valid and invalid payloads
against the generated AJV validator and compile TypeScript consumers. Preserve
explicit version tags and test rejection of invalid enum states.

Do not introduce Zod, Orval, or speculative citation payload unions without a
documented concrete need. This ADR does not freeze future API evolution or
preclude a future justified technology change.
