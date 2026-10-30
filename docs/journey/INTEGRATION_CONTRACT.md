# Complete signed dossier acceptance

One backend/API integration PR, authorized by the owner. Synthetic development
only. Reuse signed immutable Storage, OCR sidecars, ephemeral Auth lifecycle and
retention. No new UI, forensic claims, legal research or production release.

Acceptance dossier: original DOCX, separate UTF-8 inventory, text PDF and
image-only scanned PDF. Independent seeded truth includes resolved, absent,
source-missing, ambiguous and unmapped references. Include unsupported DOCX
content and unreadable-input negatives. Discovery recall remains unmeasured
outside that fixture; no global verified/fully-checked certificate.

Explicit reviewer confirmation maps inventory labels to exact source versions
and page labels to physical PDF pages, with rationale. Filename and OCR-word
matches never establish identity or pinpoint accuracy. PDF bounds are checked
against preserved bytes. Printed/bundle mapping is human-confirmed evidence,
not inferred from a fixed offset. Original pages/crops remain inspectable.

Persist confirmation revisions, candidate snapshots and human decisions under
signed current matter grants. Hash every original and bind snapshots to all
source metadata, inventory bytes, confirmation revision and algorithm version.
Changed input makes old reviews stale. Export a scoped JSON/Markdown report and
an annotated DOCX derivative; never rewrite the original draft or auto-correct
legal content. Reopen after a cold API restart and fresh sign-in.

Database changes: two new private case-scoped tables with tenant composite FKs,
RLS, no client table grants and guarded signed RPCs. Both cascade on case erasure
and fixture teardown. Existing source/review authority remains unchanged.
Confirm/review/snapshot writes lock the case and recheck membership, source
signature and confirmation revision. Bounded indexes support latest revision and
snapshot lookup. Migration is additive; recovery stops new routes while keeping
recorded evidence. No production migration or administrator DB DSN.

Run offline/adversarial/disposable SQL tests and a real signed caseproof-dev
sequence. Record SHA, workflow, source hashes, detection/checked/unresolved and
unprocessed counts, restart, stale-review denials, ungranted/revoked access and
finally cleanup. A technical check and human disposition remain separate.
