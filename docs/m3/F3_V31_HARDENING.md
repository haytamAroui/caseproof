# F3 v3.1 hardening — PR #175

**2 November 2026 · Proposed engineering change; review required.**

Base: `main` after PR #174. Branch: `feat/m3-f3-v31-intake-hardening`.
Scope: preserve **one DOCX + UTF-8 inventory + two PDFs**, current parser limits, immutable originals, signed Auth, matter-level authorization, confirmation and immutable snapshot fencing. No production deployment, public MCP upgrade, generalized exhibit intake, new SQL migration or independent legal/security approval.

## Evidence-first acceptance matrix

| Gap | Code and acceptance | Constraint |
|---|---|---|
| Inventory detector misses / unsupported notation | Versioned `InventoryReviewException`, exact signed original inventory text anchor, mandatory rationale, 64-entry cap, duplicate validation, React control and Python/browser regressions | Pending review never becomes a verified identity; `inventory_complete` is forbidden and `not_in_inventory` is suppressed |
| Partial transfer | Manifest registration plus per-original fresh signed Storage read: `verified`, `unknown`, `integrity_mismatch` | No readback state is inferred from HTTP 409, registration or a successful upload response; recover only with original bytes |
| Source ambiguity | Form explains missing binding, multiple candidate bindings and an unsaved human selection independently | No selection upgrades an identity before durable readback |
| Printed/bundle page labels | Numeric or case-preserving canonical Roman labels, distinct physical page index, generated Pydantic/Schema/TS/AJV gate | No guessed offsets, no Unicode-confusable/noncanonical Roman labels, physical page remains bounded |
| Processing transparency | Per-file processing and readback displayed independently, partial/unavailable OCR disclosed | Full queued/running/failed/retry lifecycle requires a separately authorized page-job ID and is **not inferred** from preservation |
| Cross-flow tests | Offline mapped printed p.4 → PDF p.6 + viewer authorization/revocation; six-page synthetic original included in protected F3 signed browser journey | Real protected run must pass on exact PR HEAD before claiming signed E2E acceptance |
| Sessions and recovery | Existing session controller, stale read/error banner and retry design, plus browser interruption/revocation tests | No stale receipt is proof of current source availability |
| Contract parity | `scripts.generate_frontend_contract` → versioned JSON Schema → TypeScript → AJV validators | No duplicated independent verifier authority, no schema hand edits |

## Test and review policy

- Required automatic: frontend-foundation pytest + Python schema check, mypy, Ruff, generated TS/AJV parity, frontend TypeScript/lint/Vitest/Playwright, and dossier disposable PostgreSQL/adversarial regression.
- Protected signed acceptance: same-repository PR head only, `caseproof-dev` environment; ephemeral Auth, Storage and org/matter registered and removed in `finally`; independent zero-residual verification. Never expose credentials or private uploaded bytes in logs.
- The protected fixture uses a **six-page** original text PDF containing literal `PRINTED PAGE 4` on physical page 6; the DOCX references `Stuk 1, printed p. 4`. It tests upload → confirmed mapping → report → original source viewer page six. Scanned second PDF remains unchanged.
- Owner and independent security/privacy, representative NL/FR/EN corpus and production egress/retention acceptance remain separately OPEN. No claim that signed developer tests establish court compliance or legal support.

## Rollback

Revert PR #175. No migrations, grants or Storage buckets introduced. Existing persisted `exceptions` are plain JSON confirmation payload fields; rollback clients must fail closed rather than silently treat an exception-bearing confirmation as complete. Do not delete historical reviews or mutate preserved sources.
