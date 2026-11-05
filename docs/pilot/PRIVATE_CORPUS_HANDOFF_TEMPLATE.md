# PRIVATE COPY ONLY — CaseProof rights and corpus handoff

**This public template contains NO permission and NO real dossier.**
Fill this in an approved private law-firm system; do not attach originals,
OCR, quotations, user names, matter numbers, consent files, exact private
hashes or reviewer identity to public GitHub/CI.

For EACH dossier (target 3–5), an authorized owner records privately:

- Coded dossier ID; selected NL/FR/EN convention; intended trial role
- Written rights-holder test authorization, date, owner, allowed purposes
- Applicable controller/processor terms, professional-secrecy obligations
- Data categories and any special-category/sensitive legal material
- Approved processing environment, subprocessors, regions and export access
- Original DOCX/inventory/PDF/scan SHA-256, collected only within secure custody
- Printed/PDF/bundle page map and corroborating source inspection
- Two independent adjudicators and frozen gold labels by reference/error
- Correction eligibility, unsupported spans, OCR/visual unassessed regions
- Retention/erasure/legal-hold decision, incident owner and stop conditions
- Version-pinned CaseProof build, capacity envelope and consent for human study

For each two-reviewer session record a coded reviewer ID, mode (manual or
CaseProof), elapsed positive seconds, gold-error denominator, caught errors,
false verifications, abstentions and wrong-source/physical-page events.
Counterbalance: both reviewers use both modes across dossiers, but do not
review the same dossier in both modes. Never treat empty gold-error
denominators as 100% recall.

The **metadata-only** private JSON can follow
[PRIVATE_STUDY_TEMPLATE.json](PRIVATE_STUDY_TEMPLATE.json) and be scored
locally with
\`uv run --locked python -m scripts.check_pilot_readiness --private-study /approved/private/path/metadata.json\`.
This tool **never** grants authorization and does not verify human identity
or permission. Inspect and approve rights *before* running even a local test.

External manual sign-off remains required for T61/T70/T73/T74/T75/T76/T78/T79.
