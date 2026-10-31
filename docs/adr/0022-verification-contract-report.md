# ADR 0022 — Executable verification contracts and one scoped dossier report

Decision: owner-authorized implementation proposal, 31 October 2026. Extends
ADR 0018/0019/0020 without new product category, kernel interface or database schema.
Review evidence belongs to the PR; no customer or legal approval is implied.

## Problem and decisions

The pre-M3 contracts existed as specifications but the signed dossier path bypassed
some pure inventory rules and discarded DOCX region details. Translation review had
no signed input or state. The result could disagree with the intended report contract.

1. `build_findings` consumes the existing pure InventoryStatus/identity policy. Missing,
   unreadable, unconfirmed and incomplete inventory stay not_assessed, even for a
   known candidate. Page mapping remains independent. Confirmed complete scope alone
   permits not_in_inventory; absence is not proof of noncommunication or nonfiling.
2. A signed POST `.../dossier/checks` accepts only bounded declared draft/source
   languages. Source IDs must be authorized bundle members. These declarations can
   require review, never confirm a translation or change permissions. Explicit
   traduction/vertaling/translation markers cannot be cleared by same-language input.
   Unanchored translated prose retains bounded original-language text and an authenticated source-page download; the panel requires source availability plus explicit human inspection attestation before review; download availability is not proof that a person read it. Language detection is not automated; undeclared languages are explicitly unknown.
3. Literal text and visual assessment remain separate. Translated prose never becomes
   a literal exact match because of semantic similarity. OCR/conflict takes display
   priority while independent translation_review_required remains true. Source text,
   draft quote and languages retain their own fields. Numeric normalization remains
   the separate existing same-role policy, not a translation checker.
4. DOCX discovery carries the inventory ledger through snapshots and all exports.
   Nested tables and supported stories are scanned; structured descendants and hidden
   runs are excluded from supported text rather than duplicated. Hidden/structured,
   revisions and unknown parts remain explicit omissions. A story is the counting
   unit; table paragraphs are inside the main story, not independent story totals.
5. Every known exhibit page has a processing record. NOT_PROCESSED/FAILED cannot be
   a pass. Unknown page counts remain unknown. Independent raster/OCR engine/image
   versions are recorded; no raw OCR score becomes a probability. Existing network-
   isolated runner remains mandatory; customer hosting/provider approval stays open.
6. JSON, Markdown and derivative DOCX share one frozen report, coverage, reasons,
   translation flags and human decisions. Existing receipt, original/hash, current
   grant, bundle and confirmation checks remain authoritative. No new approval or
   migration, and no model/provider connection.

## Compatibility and consumers

Adds report fields under the existing dossier-v1 envelope and versions the finding
algorithm to dossier-v3 and report contract to verification-contracts-v1. Existing
snapshot hashes are immutable; declarations and ledgers are bound into new hashes
and server receipts. Legacy snapshots can still be reopened as their original
version; missing detail must display as not recorded, not inferred complete.
Existing GET keeps its signature; default languages are undeclared. POST does not
supply identity, tenant or approval. MCP/headless contracts remain unchanged.

The deliberate behavioral change rejects a positive identity/page technical_check
under incomplete inventory. Old tests that permitted it are corrected against P3-04,
with direct policy-to-dossier regressions. Original files and historical exports are
never rewritten. Rollback removes the new check route/panel additions and restores
previous code; preserved snapshots remain versioned records, not a new-schema migration.

## Acceptance and remaining gates

Real parser/HTTP/restart/export tests cover inventory status variants, supported and
unsupported stories, translated negations/qualifiers, OCR priority and denied actors.
Cloud executable OCR and browser jobs plus signed dev acceptance are required on
this head. Real DOCX bytes are reopened and inspected, not only JSON mocks.
No generic full-reference recall, representative client corpus, commercial calibration,
bilingual practitioner approval, professional-secrecy approval or complete M3/M4
release is claimed. Independent engineering review cannot substitute for those gates.
