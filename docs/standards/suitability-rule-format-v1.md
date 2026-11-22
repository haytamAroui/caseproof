# Suitability rule format v1 (roadmap task 5)

Status: format and evaluator implemented (`application/litigation/suitability_rules.py`,
tests in `tests/test_suitability_rules.py`). No lawyer-written rule exists yet;
every example below is a synthetic placeholder, never legal content.

## Purpose

A lawyer writes a few suitability rules over confirmed case facts. The format
is typed and versioned so each result can name exactly which rule, in which
version, produced it. The pilot measures writing and review time per rule;
that measurement is a process record (stopwatch + review log), not code.
Per the roadmap, no general rule editor is built before that measurement.

## Document shape (TOML, one rule per file)

```toml
[rule]
format = "caseproof-suitability-rule-format-v1"
id = "synthetic.example.deposit"     # bounded identifier
version = "0.1.0"                    # the lawyer's own version for THIS rule
scope = "What the rule checks, in one bounded sentence."
reference = "Synthetic Act, art. 1"  # the assessed reference, named

[article]
act = "synthetic-act-2026"           # corpus act identity
article = "1"
language = "fr"                      # "nl" or "fr"
version = "2026-01-01"               # declared temporal version of the text

[condition]                          # deterministic predicate tree
all = [
  { fact = "deposit_paid", op = "eq", value = true },
  { fact = "deposit_months", op = "le", value = 2 },
]
```

Predicate operators: `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `in` (list),
`between` (two ordered numbers), `present` (no value). Combinators: `all`,
`any`, `not`. Nesting depth, leaf count, list sizes and every string are
bounded; the loader rejects anything outside the bounds (fail closed).
Unknown top-level tables and unknown keys in `[rule]`, `[article]` or
`[outcomes]` are rejected, so a typo can never be silently ignored.
Non-finite numbers (`nan`, `inf`) are rejected everywhere. `[outcomes]` may
only restate the default `on_true = "PASS"` / `on_false = "FAIL"`; remapping
is rejected, because anything that is not a decidable PASS/FAIL is
UNDETERMINED by construction.

Comparisons are typed by family (string, number, boolean — a boolean is NOT
a number here, so `true` never equals `1`). A predicate whose fact value
belongs to another family than its comparison value cannot be decided and
abstains (UNDETERMINED, sub-result `not_comparable`), never FAIL.

Corpus membership uses the canonical key `article_key(act, article, language,
version)` (lowercased, trimmed, joined with `#`). The version is a DECLARED
token (for example the as-of date the corpus declared), matched verbatim:
identity matching only, never applicability or entry-into-force reasoning,
and never inferred from dates or hashes. Corpus builders MUST produce keys
through the same helper so membership cannot diverge on formatting.

## Evaluation semantics

Evaluation (`evaluate_rule`) is pure and deterministic. No LLM, no inference,
no network.

1. **Corpus membership first.** The rule declares the article it assesses
   AND the temporal version it was written against. If the full key
   (`act#article#language#version`) is in the case's chosen corpus,
   evaluation proceeds. If the article is present only at other versions
   (or the corpus holds it without a declared version), the result is
   UNDETERMINED with reason `article_version_mismatch_or_ambiguous` and the
   versions the corpus holds are listed: the machine never decides across
   versions and never infers applicability. If the article is absent
   entirely, the result is UNVERIFIED with reason
   `article_absent_from_chosen_corpus`. This is the reserved contract status
   (rule result contract v1), activated here for the first time because
   suitability rules are the first family tied to a corpus article. It never
   means the article does not exist.
2. **Confirmed facts only.** The rule reads only facts supplied as
   `ConfirmedFact` with `confirmed = true`. A fact that is missing,
   unconfirmed or of an incomparable type family makes the whole result
   UNDETERMINED with reason `facts_unavailable_unconfirmed_or_incomparable`;
   the precondition names the affected facts. Absent or undecidable evidence
   never becomes FAIL.
3. **Decidable outcomes.** Otherwise the predicate tree decides: holds →
   PASS (`condition_holds_over_confirmed_facts`), violated → FAIL
   (`condition_violated_over_confirmed_facts`). PASS/FAIL describe only the
   evaluated condition over the confirmed facts, never a legal conclusion.
4. **Conservative combinators.** Under `any`/`all`, if any branch cannot be
   evaluated for lack of confirmed evidence, the whole node abstains
   (UNDETERMINED) rather than deciding on partial evidence.
5. **Integrity evidence.** Every result records the sha256 of the rule
   document (`rule_source`) and of the facts actually read
   (`confirmed_facts`), plus each leaf predicate's outcome as a preserved
   sub-result.

## What the lawyer writes vs what the machine does

The lawyer writes the TOML document: which facts, which thresholds, which
article. The machine validates the document, evaluates it over confirmed
facts, and reports. The machine never drafts the rule, never picks the
thresholds, and never upgrades an uncertain input into a verdict.

## Non-goals (explicit)

- No general rule editor, rule marketplace or versioning workflow beyond the
  per-rule `version` string (roadmap: measure first).
- No legal content shipped by engineering; pilot rules come from the lawyer.
- No applicability, entry-into-force or derogation reasoning (the derogation
  decision is roadmap task 2 and stays the user's).
- No OCR dependence: rules consume confirmed facts, however those facts were
  confirmed.
