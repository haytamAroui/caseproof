# Lot 2, task 4: Belgian legal corpus ingestion — design (not implemented)

Status: design only. No code in this document is built. It exists so that the
pilot conversation with the user and the lawyer starts from written choices,
not from improvisation. Task text: `docs/standards` roadmap, task 4 ("Ingérer
un petit corpus belge réel").

## What the pilot ingests

A SMALL, chosen corpus: a few exact publications from the Moniteur belge /
Belgisch Staatsblad, selected because the pilot case actually cites them.
Never "all Belgian law". The corpus is chosen per case; the lawyer confirms
the temporal scope.

## Source facts that shape the design (verified 22 Nov 2026)

From the official ELI help page (https://www.ejustice.just.fgov.be/eli/):

- Belgian legislation is served through two databases run by the Moniteur
  belge services: the Moniteur belge / Belgisch Staatsblad (original official
  publications, online since June 1997) and Justel (consolidated versions).
- ELI is only a URI addressing scheme:
  `https://www.ejustice.just.fgov.be/eli/{type}/{YYYY}/{MM}/{DD}/{unique id}/{version}`
  where `type` is `wet`/`loi` (etc.), and `version` is `staatsblad`/`moniteur`
  (character text of the original publication) or `justel` (consolidated).
- The character-mode text of the Moniteur has NO legal value and may be
  incomplete; the publication image (PDF) is the authoritative original. The
  Justel consolidation is unofficial.

Consequence baked into every record below: a hash proves the IDENTITY of a
text, never its applicability. The original publication and the derived text
are stored as separate artefacts with an explicit relation.

## Records (data model, not code)

- `PublicationRecord`: ELI URI; act type and promulgation date; unique
  identifier; language (NL/FR; both when the case needs both); the original
  publication image (PDF) preserved byte-identical with its sha256 and
  acquisition timestamp; the character-mode text with its own sha256 and
  acquisition timestamp; relation `derived_text_of` linking text to image.
- `ConsolidatedRecord` (optional per act): Justel version, retrieval
  timestamp, declared temporal version ("text as it stood on date D"), same
  hashing and relation discipline. Marked unofficial in the model, not just
  in docs.
- `ArticleRecord`: act identity + article identifier + language; resolved
  from the corpus only. An article absent from the case's chosen corpus is a
  fact of the corpus, never "the article does not exist" (this is the
  reserved UNVERIFIED semantics of the rule result contract, task 1).
- `AmendmentRecord` / errata: links between publications when the pilot set
  includes a modifying act or an erratum.

## Rules the implementation must keep

1. Original first: the publication image is preserved unchanged; every
   derived representation points back to it.
2. Declared, not inferred: the temporal version in force for the case is
   recorded as a declaration confirmed by the lawyer, never guessed from
   dates.
3. Bounded and manual: the pilot set is a handful of acts, added
   deliberately. No crawling, no bulk download, no scheduled fetching.
4. Public material only until the environment is approved for confidential
   data (roadmap constraint). Ingestion here concerns public legislation, but
   the surrounding case data rule still applies.
5. Acquisition provenance: every fetch records when and from which exact
   URI.

## Measurements (task 4 acceptance)

- Ingestion failures per publication (fetch, parse, identity mismatch).
- Ambiguous or conflicting temporal versions encountered.
- These numbers feed the task 7 pilot decision; they are measurements, not
  quality claims.

## Real inputs this design cannot supply itself

- The pilot case area: WHICH acts and articles, in which language(s).
- The temporal version each cited act must be read at, confirmed by the
  lawyer.
- Confirmation that all pilot material is public / royalty-free, or an
  approved-environment decision.

## Explicitly out of scope here

Article-level applicability judgments, entry-into-force reasoning, any LLM
use in the ingestion verdict path, OCR of the publication image (the image is
the reference; OCR would be a reading fallback, never the product).
