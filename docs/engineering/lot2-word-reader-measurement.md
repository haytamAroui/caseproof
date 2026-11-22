# Lot 2, task 6: Word reader coverage measurement — plan (not run)

Status: plan only. No measurement has been run for the pilot. Task text:
roadmap task 6 ("Tester la lecture Word sur des fichiers représentatifs").
Goal: measure what the existing reader sees and what it omits, to size task 8
("Compléter le lecteur Word de vérification") and feed the task 7 decision.

## Existing harness (verified in code 22 Nov 2026)

- `infrastructure/parsers/docx_region_inventory.py` — fail-closed region
  inventory. It already labels, per DOCX part:
  - `MAIN_BODY`, `HEADER`, `FOOTER`, `FOOTNOTE`, `ENDNOTE` regions, each
    `UNPROCESSED_REGION` ("TEXT_NOT_YET_SCANNED") or
    `REVISION_STATE_UNRESOLVED` ("FROZEN_VIEW_REQUIRED") when tracked
    insertions/deletions/moves are present;
  - `COMMENT_EXCLUDED` ("EXCLUDED_FROM_FILED_BODY") for `word/comments.xml`;
  - `HIDDEN_TEXT_EXCLUDED` for enabled `vanish` runs;
  - `STRUCTURED_CONTENT` ("UNSUPPORTED_STRUCTURED_CONTENT") for text boxes,
    altChunk, drawings, fields and similar;
  - `UNKNOWN_WORD_PART` for unrecognised `word/*.xml` parts;
  - whole-package fail-closed reasons: `PACKAGE_TOO_LARGE`,
    `TOO_MANY_PARTS`, `UNCOMPRESSED_LIMIT`, `ENCRYPTED_ZIP_ENTRY`,
    `DUPLICATE_ZIP_ENTRY`, `NOT_DOCX`, `UNSAFE_PART_PATH`, `PART_TOO_LARGE`,
    `DTD_FORBIDDEN`, `UNREADABLE_PACKAGE`.
  A `DocxCoverage` carries `coverage_unknown` plus the reason.
- `infrastructure/parsers/docx_text_regions.py` — bounded text extraction
  over selected regions with explicit omissions
  (`DocxTextExtraction.coverage_complete`, `unscanned_parts`, `manifest`).

So the reader already DECLARES its omission classes. Task 6 measures how
often each class occurs on representative files and how much brief content
falls in each.

## Measurement set

- Real set (decision-feeding): representative actual Belgian briefs as DOCX,
  containing the features lawyers really use: comments, tracked changes,
  footnotes, headers/footers, text boxes, hidden text. To be provided from
  the user/lawyer side; nothing confidential until the environment is
  approved.
- Synthetic control set (engineering prep only): generated DOCX files
  covering each omission class above, used to verify the harness counts what
  it claims to count. Synthetic results are harness validation; they are
  never presented as real Belgian acceptance.

## Metrics per file

- Regions by kind and status (counts), with the fail-closed reason when
  `coverage_unknown` is true.
- Share of body text (characters) in scanned vs omitted regions, per
  omission class: comments, tracked revisions, hidden text, structured
  content, unknown parts.
- Presence/absence of tracked changes and comments (the two classes the
  roadmap names explicitly).
- Extraction anomalies: empty main body, unexpectedly large unscanned share.

## Report shape

One measurement report per measurement run: per-file table of the metrics
above, an aggregate per omission class, and the explicit list of what the
reader does not see per file. The report states which set (real or
synthetic) it was run on. This report is the evidence base for sizing
task 8 and for the task 7 pilot review.

## What this plan does not do

It does not change the reader, does not decide task 8's scope, and does not
treat any synthetic coverage number as pilot evidence.
