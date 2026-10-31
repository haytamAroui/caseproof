"""S2-008a fail-closed schema contract: not a live migration or vault."""

from pathlib import Path

from scripts.verify_s2_008a_database import SCHEMA

ROOT = Path(__file__).resolve().parents[1]


def test_schema_preserves_opaque_ids_and_case_constrained_ancestry() -> None:
    assert "create table caseproof.s2_008a_source_logical_ids" in SCHEMA
    assert "create table caseproof.s2_008a_version_logical_ids" in SCHEMA
    assert "create table caseproof.s2_008a_representations" in SCHEMA
    assert "create table caseproof.s2_008a_layouts" in SCHEMA
    assert "create table caseproof.s2_008a_anchors" in SCHEMA
    assert "kernel_document_id text not null" in SCHEMA
    assert "kernel_version_id text not null" in SCHEMA
    assert "kernel_representation_id text not null" in SCHEMA
    assert "unique (org_id, case_id, kernel_document_id)" in SCHEMA
    assert "foreign key (org_id, case_id, document_pk)" in SCHEMA
    assert "references caseproof.documents(org_id, case_id, id)" in SCHEMA
    assert "references caseproof.s2_008a_representations(" in SCHEMA
    assert "and source_sha256" not in SCHEMA  # SQL conditions are typed FKs, not string predicates


def test_every_evidence_row_has_audit_reference_and_no_client_grants() -> None:
    # All 5 new tables are private, RLS-enabled, and must be audit-linked.
    assert SCHEMA.count("audit_event_id uuid not null") == 5
    assert SCHEMA.count("references caseproof.audit_events(org_id, case_id, id)") == 5
    assert SCHEMA.count("enable row level security;") == 5
    assert "revoke all on caseproof.s2_008a_source_logical_ids" in SCHEMA
    assert "grant select" not in SCHEMA.lower()
    assert "security definer" not in SCHEMA.lower()
    assert SCHEMA.count("before update or delete") == 6
    assert "create trigger s2_008a_parent_source_metadata_immutable" in SCHEMA
    assert "caseproof.document_versions" in SCHEMA
    assert "create function caseproof._s2_008a_disposable_no_mutation()" in SCHEMA


def test_disposable_guard_and_cloud_verification_wiring() -> None:
    runner = (ROOT / "scripts/verify_s2_008a_database.py").read_text(encoding="utf-8")
    assert "env = _isolated_postgres_env()" in runner
    assert "caseproof_s2_ci" in runner[:500]
    assert "_assert_sql_rejected" in runner
    assert "s2_008a_src_case_fk" in runner
    assert "s2_008a_anchor_repr_case_digest_fk" in runner
    assert "OTHER_AUDIT" in runner
    assert "get stacked diagnostics actual_constraint = constraint_name" in runner
    assert "Equal-byte representations must preserve TWO distinct IDs" in runner
    assert "aborted append transaction" in runner
    assert "append-only update denied" in runner
    assert "referenced original source-version metadata update denied" in runner
    assert "referenced original source-version delete denied" in runner
    assert "authenticated role cannot read unapproved graph" in runner
    assert "S2-008a_DISPOSABLE_EVIDENCE_GRAPH_CONTRACT_PASSED" in runner
    workflow = (ROOT / ".github/workflows/kernel-boundary.yml").read_text(
        encoding="utf-8"
    )
    assert "uv run --locked python -m scripts.verify_s2_008a_database" in workflow
    assert "CASEPROOF_DEV_AUTH" not in workflow


def test_no_installed_migration_or_prod_route() -> None:
    assert {p.name for p in (ROOT / "supabase/migrations").glob("*.sql")} == {
        "20261031112127_signed_page_worker.sql",
        "20261030140000_caseproof_phase3_private_ocr_geometry.sql",
        "20261030141500_caseproof_phase3_geometry_text_payload.sql",
        "20261030143000_caseproof_phase3_atomic_ocr_ingest.sql",
        "20261030150000_caseproof_phase3_signed_geometry_read.sql",
        "20261030153000_caseproof_phase3_four_source_draft_bundle.sql",
        "20261022001009_caseproof_tenant_foundation.sql",
        "20261027160745_caseproof_m1_dev_atomic_private_grants.sql",
        "20261027195417_caseproof_m2_dev_atomic_private_review.sql",
        "20261027195451_caseproof_m1_signed_invoker_read_views.sql",
            "20261027202734_caseproof_m1_private_originals_storage.sql",
            "20261027204343_caseproof_m1_storage_upload_action_correction.sql",
            "20261027214851_caseproof_m1_dev_live_positive_fixture_rpc.sql",
            "20261028065430_caseproof_m1_private_exhibit_storage.sql",
            "20261028070156_caseproof_dev_signed_review_roundtrip.sql",
            "20261028070231_caseproof_dev_scoped_review_cleanup.sql",
            "20261028071554_caseproof_dev_signed_review_security_hardening.sql",
            "20261028081227_caseproof_dev_signed_matter_txt_ingestion.sql",
            "20261028081347_caseproof_dev_txt_review_binding.sql",
            "20261028081408_caseproof_dev_txt_revocation_cleanup.sql",
            "20261028081528_caseproof_dev_signed_create_org_discovery.sql",
            "20261028082143_caseproof_dev_txt_cleanup_uuid_fix.sql",
            "20261028083533_caseproof_dev_close_client_ingest_bypass.sql",
            "20261028083622_caseproof_dev_trusted_ingest_verified_promotion.sql",
            "20261028083747_caseproof_dev_cleanup_actor_isolation.sql",
            "20261028105942_caseproof_dev_separate_draft_write_grant.sql",
            "20261028110031_caseproof_dev_signed_reviewed_draft_correction.sql",
            "20261028110102_caseproof_dev_reversible_draft_cleanup.sql",
            "20261028110233_caseproof_dev_ordered_revised_brief_state.sql",
            "20261028110604_caseproof_dev_correction_review_head_fence.sql",
            "20261028111543_caseproof_dev_correct_owner_write_and_read_separation.sql",
            "20261028111744_caseproof_dev_require_org_write_for_brief.sql",
            "20261028111820_caseproof_dev_org_only_revoke_test_rpc.sql",
            "20261028114522_caseproof_dev_signed_pdf_docx_register_parse_manifest.sql",
            "20261028114616_caseproof_dev_service_verified_binary_parser_promotion.sql",
            "20261028114940_caseproof_dev_m2_preserve_partial_pdf_docx_unknown.sql",
            "20261028114956_caseproof_dev_cleanup_verified_binary_source.sql",
            "20261030095000_caseproof_dev_bundle_cleanup.sql",
            "20261030101500_caseproof_dev_bundle_manifest.sql",
            "20261030103000_caseproof_durable_bundle_roles.sql",
            "20261030110000_caseproof_dev_atomic_bundle_registration.sql",
        "20261030113000_m05_test_run_registry.sql",
        "20261030114000_m05_ocr_sidecar_cleanup_fk.sql",
        "20261030115000_m05_protected_registry_rpc.sql",
        "20261030120000_m05_verify_empty.sql",
        "20261030155817_matter_retention.sql",
        "20261030160341_retention_storage_fence.sql",
        "20261030161844_complete_dossier_journey.sql",
            "20261030235107_representation_snapshot_read.sql",
            "20261030235456_regional_review_attestation.sql",
    }
    assert "S2-008a_disposable_representation_anchor_graph.sql" not in (
        ROOT / "apps/api/main.py"
    ).read_text(encoding="utf-8")
    assert not (ROOT / "apps/api/evidence_write_service.py").exists()
