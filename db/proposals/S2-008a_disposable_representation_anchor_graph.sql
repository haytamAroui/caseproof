-- S2-008a: immutable source/representation/anchor *proposal*.
-- NEVER apply this file to caseproof-dev, any Supabase project, or production.
-- Run exclusively in ephemeral PostgreSQL 17 caseproof_s2_ci after S2-002.
-- Not a canonical migration, API writer, signed-Auth proof, verified byte vault
-- or a positive eligibility/promotion implementation. No client write grants.
--
-- Data identity: internal UUID keys are NOT the opaque kernel logical IDs.
-- SHA-256 is integrity metadata, NEVER an identity or authenticity claim.
-- Each proposed immutable row requires a same-transaction trusted audit event
-- FK, but caller authority/audit identity must be independently enforced by
-- a future reviewed least-privilege application writer.

begin;

-- Additional unique composite parents enable same-org, other-case rejection.
alter table caseproof.documents
    add constraint s2_008a_documents_case_identity
    unique (org_id, case_id, id);
alter table caseproof.document_versions
    add constraint s2_008a_versions_source_identity
    unique (org_id, document_id, id, original_sha256_hex);

create table caseproof.s2_008a_source_logical_ids (
    org_id uuid not null,
    case_id uuid not null,
    document_pk uuid not null,
    kernel_document_id text not null
        check (length(kernel_document_id) between 1 and 256
               and length(btrim(kernel_document_id)) > 0),
    audit_event_id uuid not null,
    primary key (org_id, case_id, document_pk),
    unique (org_id, case_id, kernel_document_id),
    foreign key (org_id, case_id, document_pk)
        references caseproof.documents(org_id, case_id, id),
    foreign key (org_id, case_id, audit_event_id)
        references caseproof.audit_events(org_id, case_id, id)
);

create table caseproof.s2_008a_version_logical_ids (
    org_id uuid not null,
    case_id uuid not null,
    document_pk uuid not null,
    version_pk uuid not null,
    kernel_version_id text not null
        check (length(kernel_version_id) between 1 and 256
               and length(btrim(kernel_version_id)) > 0),
    source_sha256_hex text not null
        check (source_sha256_hex ~ '^[0-9a-f]{64}$'),
    audit_event_id uuid not null,
    primary key (org_id, case_id, document_pk, version_pk),
    unique (org_id, case_id, document_pk, kernel_version_id),
    unique (org_id, case_id, document_pk, version_pk, kernel_version_id, source_sha256_hex),
    foreign key (org_id, case_id, document_pk)
        references caseproof.s2_008a_source_logical_ids(org_id, case_id, document_pk),
    foreign key (org_id, document_pk, version_pk, source_sha256_hex)
        references caseproof.document_versions(org_id, document_id, id, original_sha256_hex),
    foreign key (org_id, case_id, audit_event_id)
        references caseproof.audit_events(org_id, case_id, id)
);

create table caseproof.s2_008a_representations (
    representation_pk uuid primary key,
    org_id uuid not null,
    case_id uuid not null,
    document_pk uuid not null,
    version_pk uuid not null,
    kernel_version_id text not null,
    kernel_representation_id text not null
        check (length(kernel_representation_id) between 1 and 256
               and length(btrim(kernel_representation_id)) > 0),
    source_sha256_hex text not null check (source_sha256_hex ~ '^[0-9a-f]{64}$'),
    representation_sha256_hex text not null
        check (representation_sha256_hex ~ '^[0-9a-f]{64}$'),
    media_type text not null check (length(btrim(media_type)) between 1 and 128),
    transform_name text not null check (length(btrim(transform_name)) between 1 and 128),
    transform_version text not null check (length(btrim(transform_version)) between 1 and 128),
    transform_config_sha256 text not null check (transform_config_sha256 ~ '^[0-9a-f]{64}$'),
    coordinate_convention text not null check (length(btrim(coordinate_convention)) between 1 and 128),
    created_at timestamptz not null default now(),
    audit_event_id uuid not null,
    unique (org_id, case_id, document_pk, version_pk, kernel_representation_id),
    unique (org_id, case_id, document_pk, version_pk, representation_pk,
            source_sha256_hex, representation_sha256_hex),
    foreign key (org_id, case_id, document_pk, version_pk, kernel_version_id, source_sha256_hex)
        references caseproof.s2_008a_version_logical_ids(
            org_id, case_id, document_pk, version_pk, kernel_version_id, source_sha256_hex
        ),
    foreign key (org_id, case_id, audit_event_id)
        references caseproof.audit_events(org_id, case_id, id)
);

create table caseproof.s2_008a_layouts (
    org_id uuid not null,
    case_id uuid not null,
    representation_pk uuid not null,
    layout_kind text not null check (layout_kind in ('text','pdf','spreadsheet','structured')),
    layout_schema_version text not null check (layout_schema_version = 'krn102-layout-v1'),
    layout_manifest jsonb not null check (jsonb_typeof(layout_manifest) = 'object'
                                         and octet_length(layout_manifest::text) <= 65536),
    layout_sha256_hex text not null check (layout_sha256_hex ~ '^[0-9a-f]{64}$'),
    audit_event_id uuid not null,
    primary key (org_id, case_id, representation_pk),
    foreign key (org_id, case_id, audit_event_id)
        references caseproof.audit_events(org_id, case_id, id)
);

-- A layout cannot attach to another case's representation.
alter table caseproof.s2_008a_representations
    add constraint s2_008a_repr_case_pk
    unique (org_id, case_id, representation_pk);
alter table caseproof.s2_008a_layouts
    add constraint s2_008a_layout_repr_fk
    foreign key (org_id, case_id, representation_pk)
    references caseproof.s2_008a_representations(org_id, case_id, representation_pk);

create table caseproof.s2_008a_anchors (
    anchor_pk uuid primary key,
    org_id uuid not null,
    case_id uuid not null,
    kernel_anchor_id text not null
        check (length(kernel_anchor_id) between 1 and 256 and length(btrim(kernel_anchor_id)) > 0),
    document_pk uuid not null,
    version_pk uuid not null,
    representation_pk uuid not null,
    source_sha256_hex text not null check (source_sha256_hex ~ '^[0-9a-f]{64}$'),
    representation_sha256_hex text not null check (representation_sha256_hex ~ '^[0-9a-f]{64}$'),
    locator_kind text not null
        check (locator_kind in ('text_span','pdf_region','sheet_range','structured_field')),
    locator_schema_version text not null check (locator_schema_version='krn102-locator-v1'),
    locator jsonb not null check (jsonb_typeof(locator)='object'
                                and octet_length(locator::text) <= 8192),
    audit_event_id uuid not null,
    unique (org_id, case_id, kernel_anchor_id),
    foreign key (org_id, case_id, document_pk, version_pk, representation_pk,
                 source_sha256_hex, representation_sha256_hex)
        references caseproof.s2_008a_representations(
            org_id, case_id, document_pk, version_pk, representation_pk,
            source_sha256_hex, representation_sha256_hex
        ),
    foreign key (org_id, case_id, representation_pk)
        references caseproof.s2_008a_layouts(org_id, case_id, representation_pk),
    foreign key (org_id, case_id, audit_event_id)
        references caseproof.audit_events(org_id, case_id, id)
);

-- Type-specific geometry/coordinate validation is still required from the
-- pure KRN-102 typed constructors and trusted parser layout on every read
-- AND write. A JSON object/known locator kind is NOT sufficient to declare
-- the anchor resolvable. No promotion or export is authorized here.

-- Prevent in-place modification under the test superuser too; privileged
-- DBA can still change/drop this guard, hence NOT tamper-proof.
create function caseproof._s2_008a_disposable_no_mutation()
returns trigger language plpgsql security invoker
set search_path=pg_catalog,pg_temp
as $guard$
begin
    raise exception 'S2-008a immutable evidence record cannot be rewritten';
end
$guard$;

create trigger s2_008a_source_immutable before update or delete
    on caseproof.s2_008a_source_logical_ids
    for each row execute function caseproof._s2_008a_disposable_no_mutation();
create trigger s2_008a_version_immutable before update or delete
    on caseproof.s2_008a_version_logical_ids
    for each row execute function caseproof._s2_008a_disposable_no_mutation();
create trigger s2_008a_repr_immutable before update or delete
    on caseproof.s2_008a_representations
    for each row execute function caseproof._s2_008a_disposable_no_mutation();
create trigger s2_008a_layout_immutable before update or delete
    on caseproof.s2_008a_layouts
    for each row execute function caseproof._s2_008a_disposable_no_mutation();
create trigger s2_008a_anchor_immutable before update or delete
    on caseproof.s2_008a_anchors
    for each row execute function caseproof._s2_008a_disposable_no_mutation();

revoke execute on function caseproof._s2_008a_disposable_no_mutation()
    from public, anon, authenticated;
alter table caseproof.s2_008a_source_logical_ids enable row level security;
alter table caseproof.s2_008a_version_logical_ids enable row level security;
alter table caseproof.s2_008a_representations enable row level security;
alter table caseproof.s2_008a_layouts enable row level security;
alter table caseproof.s2_008a_anchors enable row level security;
revoke all on caseproof.s2_008a_source_logical_ids,
    caseproof.s2_008a_version_logical_ids,
    caseproof.s2_008a_representations,
    caseproof.s2_008a_layouts,
    caseproof.s2_008a_anchors
from public, anon, authenticated;
-- No client-side SELECT or DML grants: deny-all until S2-007 runtime role
-- and S2-009 private stored bytes have independently verified proof.

commit;
