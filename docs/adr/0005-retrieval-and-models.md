# ADR 0005-retrieval-and-models

**Status:** accepted as initial design baseline, subject to empirical and legal validation.

## Decision
Start with typed structured extraction and source-preserving corpus/section processing. No vector store, LangChain dependency or autonomous agents required for v1. Benchmark whole-context vs segmented extraction and optionally add hybrid lexical/vector retrieval for very large collections. No vendor-model pinning without current cost/availability/privacy review.

## Revisit criteria
A demonstrated business, correctness, reliability, privacy or cost requirement that the chosen architecture cannot satisfy.
