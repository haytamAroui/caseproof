# Signed dossier acceptance — 30 October 2026

Executed on **caseproof-dev**, real ephemeral signed development users, synthetic
originals only. No confidential client data or production release.

- Tested implementation: `aff400c28815622504b7b60bfecec7844503a141`.
- [Complete signed workflow, including unreadable-draft negative](https://github.com/haytamAroui/caseproof/actions/runs/41089564559).
- [Disposable dossier and retention adversarial SQL](https://github.com/haytamAroui/caseproof/actions/runs/41089564532).
- [Kernel, full unit/lint/type/browser and database regressions](https://github.com/haytamAroui/caseproof/actions/runs/41089575846).
- All 14 workflow runs on that revision passed. Later PR revisions must pass
  their own final-head checks before merge.
- Deployed migration: `20261030161844_complete_dossier_journey`; connected
  Supabase MCP installation, RLS, no client table grants, anonymous RPC denial,
  case erasure cascade FKs and retention write triggers verified separately.

| Measured result | Value |
|---|---:|
| Preserved originals uploaded/read back with matching SHA-256 | 4 |
| Explicit draft references detected | 8 |
| Identity + pinpoint checks completed | 3 |
| Unresolved detected references | 5 |
| Unprocessed DOCX parts/regions | 8 |
| Human decisions reopened after cold restart/fresh sign-in | 1 |
| Fully checked dossier / measured general reference recall | **No / No** |

The four originals are a DOCX draft, UTF-8 inventory, standards-compliant text
PDF, and image-only scanned PDF. Scope includes physical PDF page 1, explicitly
confirmed printed page 7 and bundle page 12. Missing source, absent inventory
entry, duplicate identity, out-of-range page and unspecified page space remain
unresolved. The unprocessed parts include the seeded comments part and seven metadata/style
parts that the conservative extractor does not certify. They stay in the
coverage disclosure; eight unprocessed parts does not mean eight missed references.

Executed assertions:

1. Signed upload and authorized original readback of every source; hashes match.
2. Initial unconfirmed inventory does not resolve identities or imply absence.
3. Explicit reviewer inventory/source/page confirmation yields the fixed counts.
4. Original-source PDF pages and real persisted-geometry scan crop return bytes;
   OCR stays uncertain, quote fidelity and automated semantic support unassessed.
5. Signed human decision references the exact persisted candidate snapshot.
6. JSON and Markdown include coverage and decisions; annotated DOCX is a separate
   derivative. Original draft hash remains unchanged after export.
7. Cold API restart and fresh sign-in return the **identical exported report**,
   including sources, finding states and the saved human decision.
8. A new confirmation revision rejects the old review with 409 and excludes it
   from the new snapshot's current decisions. Independent SQL tests also change
   source metadata and reject the old confirmation/snapshot.
9. Ungranted same-organization and foreign users cannot read the dossier, export,
   source original or source page, or write a confirmation. Revoked owner cannot
   read those endpoints or the crop using the previously valid JWT.
10. Scoped Storage-empty verification and zero-residual fixture/Auth/registry
    teardown pass in the finally wrapper, including on failed attempts.
11. A second live run uploads an unreadable DOCX original: no detected-reference
    result is promoted to complete text coverage or a fully checked dossier;
    that separate run also passes scoped teardown.

The workflow retains generated synthetic demo originals, JSON/Markdown report
and annotated DOCX as a downloadable artifact for seven days. This intentional
non-confidential artifact retention is separate from deletion of the development
fixture's database rows, private Storage objects and ephemeral Auth identities.
The final revision also includes the actual returned scan crop in that artifact.

Bounds: this is one synthetic acceptance case and one live unreadable-draft
negative, not a lawyer-adjudicated corpus benchmark, broad format/recall proof,
forensic authenticity certificate, measured time saving, or client-ready security
approval. Printed/bundle mappings and semantic decisions are explicit human
assertions. Full worker isolation/egress, backup expiry/restore, independent
security/privacy review and commercial discovery remain separate gates.


## Repeat the demonstration

Run **Complete signed dossier live acceptance** in GitHub Actions on the tested
feature branch, or on `main` after integration. The existing protected
`caseproof-dev` environment supplies development credentials. No manual user,
matter or source provisioning is required. The workflow creates fresh synthetic
identities, runs both scenarios, exports the demo artifact and always tears down
its owned resources. It is not enabled for fork PRs or arbitrary branch refs.
