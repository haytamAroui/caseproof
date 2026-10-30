# Integration audit — PR #138

Baseline: main `ae23e70`. Backend/API only; no new UI or production deployment.

| Task | Reused baseline | Integration change | Acceptance |
|---|---|---|---|
| 1. Inspect current flow | Signed Storage, OCR sidecars, Phase 4 reviews and fixture lifecycle | This audit and the integration contract identify the missing connected behavior | Baseline audit complete |
| 2. Fixed synthetic truth | Four-source fixture factory | Eight Stuk/Pièce references: 3 identity/page checks, 5 unresolved; unsupported DOCX region; separate unreadable DOCX run | Independent fixed expected identities/counts |
| 3. Reference/page verification | Bounded DOCX region extraction and explicit-reference detector | Human-confirmed inventory/source identities; physical PDF bounds; explicit printed/bundle maps; missing/duplicate/conflicting states | Domain and SQL adversarial tests; signed run required |
| 4. Source review | Original byte/hash checks; persisted OCR geometry and crop endpoint | Signed original-source PDF pages and original downloads; OCR uncertainty; no crop-to-pinpoint inference | Source hashes and PDF/PNG response checks |
| 5. Exact decision binding | Signed human review ledger | Immutable candidate snapshots bind all original versions/hashes, inventory and confirmation revision; stale decisions rejected | SQL source-change and confirmation-change tests; live revision test |
| 6. Export/reopen | Restart/sign-in helpers | Scoped JSON/Markdown and separate annotated DOCX; original unchanged; same exported report after cold restart | Parser/namespace tests and live byte/report equality |
| 7. Signed acceptance | Ephemeral GoTrue users, matter grants, private Storage and finally teardown | New protected complete-dossier and unreadable-draft workflow | Live evidence pending until an executed run passes |
| 8. Evidence/integration | Required GitHub cloud regressions and migration workflow | One PR, downloadable synthetic demo artifacts, dated run/commit/counts and denial/cleanup receipt | Merge only after final-head CI and signed acceptance |

New snapshots are **candidate derivations**, not professional certification.
The API recomputes them from signed, hash-checked originals before accepting a
review or producing output. The signed RPC checks the current source signature
and confirmation revision under a matter lock. Raw client-written candidate
snapshots cannot become an API export without matching the recomputed digest.
A human semantic decision is separate from technical identity/page checks and
quote fidelity. The initial confirmation is also a human assertion with recorded
actor/time, not automatic recognition of a filename as legal identity.

Inventory parser limits remain explicit. Complete confirmation must include
every detected inventory identity; loading also checks preserved inventory bytes
so an omitted row cannot create a false not-in-inventory finding. Plain p. is
ambiguous; unsupported page spaces and conflicting labels remain unmapped.

The new tables have composite tenant/case FKs, RLS, no client table grants and
retention write guards. Case erasure cascades their exact records. The new
SECURITY DEFINER advisory is intentional for the narrowly guarded signed RPC,
not a clean security certification. Production backup/restore, independent
security/privacy approval, worker isolation and commercial validation remain
separate gates. Historical `/verification` filename-candidate endpoints are not
the accepted complete-dossier interface; the integration uses `/dossier`.
