# M5 Synthetic 5-Dossier FR/NL Benchmark Baseline — 25 November 2026

**Status:** **SYNTHETIC ENGINE BASELINE ONLY — NOT PRACTITIONER M5 SIGNOFF.**  
**Commit tested:** `44824863e984feecf23b16bd869e76c112a3ed70` (`main`)  
**Command:** `python -m scripts.run_m5_fr_nl_benchmark --json-out <path>`  
**Authority:** [ROADMAP M5 & P5-03](../ROADMAP.md) · [Partner Discovery & Scorecard](PARTNER_DEMO_AND_INTERVIEW_SCORECARD.md) · [ADR 0038](../adr/0038-pre-filing-truth-layer-and-competitive-strategy.md)

> [!IMPORTANT]
> This report records deterministic engine behavior on **5 synthetic, rights-cleared Belgian FR/NL dossiers** (including a clean zero-error control). It does **not** prove recall on arbitrary lawyer-authored documents, does **not** measure real partner review minutes (`M5-02` / `P5-03`), and does **not** authorize real client uploads (`SEC-01`–`SEC-16`).

## Summary Metrics (`caseproof-m5-synthetic-benchmark-v1`)

| Metric | Measured Value | Notes |
| --- | --- | --- |
| Dossiers evaluated | `5` | 2 FR trap dossiers, 1 NL trap dossier, 1 FR/NL bilingual dossier, 1 FR clean zero-error control |
| Seeded traps total | `6` | Deterministic seeded reference/value/lexical/inventory traps |
| Caught traps total | `6` | `6/6` seeded traps surfaced (`100%` on synthetic fixture set only) |
| False alarms total | `0` | `0` false alarms on the clean zero-error control and non-trap passages |
| Explicit abstentions | `1` | Bilingual FR/NL dossier abstained cleanly where required |
| Total deterministic runtime | `1.173 ms` | Pure in-memory deterministic engine checks (excludes PDF rasterization/OCR/network I/O) |
| `synthetic_benchmark` | `true` | Synthetic fixtures only; zero client data |
| `not_practitioner_m5_signoff` | `true` | Real practitioner benchmark (`M5-02`) remains **OPEN** |

## Per-Dossier Breakdown

| Dossier ID | Language | Clean Control | Seeded Traps | Caught Traps | False Alarms | Abstentions | Elapsed (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fr-bail-commercial` | `fr` | No | 2 | 2 | 0 | 0 | `0.439` |
| `nl-aanneming` | `nl` | No | 2 | 2 | 0 | 0 | `0.433` |
| `fr-nl-bilingual-refere` | `fr/nl` | No | 1 | 1 | 0 | 1 | `0.120` |
| `fr-missing-inventory-piece` | `fr` | No | 1 | 1 | 0 | 0 | `0.032` |
| `fr-clean-zero-error-control` | `fr` | **Yes** | 0 | 0 | 0 | 0 | `0.130` |

## What Remains Open for M5-01 & M5-02 (P5-01 / P5-03)
1. **5 disconfirming Belgian partner interviews + 2 observed workflows** using [PARTNER_DEMO_AND_INTERVIEW_SCORECARD.md](PARTNER_DEMO_AND_INTERVIEW_SCORECARD.md) on synthetic dossiers (`M5-01`).
2. **3–5 representative FR/NL practitioner dossiers** (rights-cleared or executed only after `SEC-01`–`SEC-16` approval for the target environment) measuring:
   - Total end-to-end review time vs. manual baseline (including OCR/PDF page rendering and human disposition time),
   - Critical errors caught vs. missed (with independent adjudication), and
   - False-alarm friction rate during real partner review (`M5-02`).
3. **Explicit Go / Refine / Reconsider owner decision** (`P5-01`) before any spend on `BE-09` (optional Level-2 LLM Scout) or broad commercialization.
