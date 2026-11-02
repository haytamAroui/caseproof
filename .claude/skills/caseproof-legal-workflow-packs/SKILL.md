---
name: caseproof-legal-workflow-packs
description: Design bounded Belgian litigation fixture and workflow packs as versioned data without extending CaseProof into legal research, deadline calculation or substantive legal advice.
---
# Belgian workflow packs
Read `CONSTITUTION.md`, `docs/ROADMAP.md`, and `frontend/BLUEPRINT.md`. Use this skill only for explicitly approved domain fixtures and practitioner review, not to add a new product vertical by default.

## Pack contract
Versioned JSON fixture/configuration: pack_id, schema_version, language, jurisdiction, procedure_label, synthetic_rights, expected_document_roles, example_reference_patterns, expected_ambiguities, supported_verification_dimensions, human_review_prompts, excluded_capabilities, fixture_sha256. No auto-generated legal conclusions, deadlines, substantive elements of claims, or legal advice.

## First candidate
Belgian invoice/debt dispute with NL/FR language variants and synthetic DOCX brief, confirmed inventory, text PDF, image-only PDF, inconsistent printed/PDF/bundle page numbering, ambiguous labels, revised draft, and explicit unsupported or unassessed claims. Mark all generated legal content fictional. Never imply that a generic Belgian pack is approved by a bar authority.

## Gates
Pack validation requires JSON schema, immutable fixture hashes, rights declaration, cross-language terminology review, actual parser integration, negative cases, and independent practitioner review before claiming legal acceptance. Configuration may tune presentation and test data; it MUST NOT change canonical evidence verdict rules.

## External research
Judicex workflow packs and Anthropic legal plugin gates are conceptual references only. Verify repository version, provenance, license and security before adopting code or templates.
