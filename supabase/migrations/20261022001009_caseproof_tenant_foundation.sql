-- S2-002 design candidate. DO NOT APPLY AS A MIGRATION BEFORE HUMAN APPROVAL.
-- Designed for a NEW, EMPTY caseproof-dev Supabase project (PostgreSQL 17).
-- Tests execute it inside BEGIN ... ROLLBACK, leaving no application schema.
-- This private schema is NOT exposed by default in the Supabase Data API.
-- No client writes, SECURITY DEFINER, privileged helper or bypass role granted.

create schema caseproof;
revoke all on schema caseproof from public, anon, authenticated;
grant usage on schema caseproof to authenticated;

create table caseproof.organizations (
    id uuid primary key default gen_random_uuid(),
    display_name text not null check (length(btrim(display_name)) between 1 and 200),
    created_at timestamptz not null default now()
);

create table caseproof.organization_members (
    org_id uuid not null references caseproof.organizations(id),
    user_id uuid not null references auth.users(id),
    active boolean not null default true,
    actions text[] not null default '{}'::text[]
        check (actions <@ array[
            'case:read', 'coverage:read', 'evidence:read', 'finding:write',
            'review:request', 'conclusion:request_approval', 'exception:request'
        ]::text[]),
    membership_revision bigint not null default 1 check (membership_revision > 0),
    updated_at timestamptz not null default now(),
    primary key (org_id, user_id)
);

create table caseproof.cases (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references caseproof.organizations(id),
    created_by_user uuid not null,
    case_revision bigint not null default 1 check (case_revision > 0),
    state text not null default 'candidate'
        check (state in ('candidate','evidence_grounded','review_ready','approved_conclusion')),
    scope_version bigint not null default 1 check (scope_version > 0),
    manifest_revision bigint not null default 1 check (manifest_revision > 0),
    effective_policy_version text not null check (length(btrim(effective_policy_version)) > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (org_id, id),
    foreign key (org_id, created_by_user)
        references caseproof.organization_members(org_id, user_id)
);

create table caseproof.documents (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    case_id uuid not null,
    source_label text not null check (length(btrim(source_label)) between 1 and 256),
    received_at timestamptz not null default now(),
    unique (org_id, id),
    foreign key (org_id, case_id) references caseproof.cases(org_id, id)
);

create table caseproof.document_versions (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    document_id uuid not null,
    version_number bigint not null check (version_number > 0),
    original_sha256_hex text not null
        check (original_sha256_hex ~ '^[0-9a-f]{64}$'),
    byte_length bigint not null check (byte_length >= 0),
    media_type text not null check (length(btrim(media_type)) > 0),
    parser_version text,
    ingested_at timestamptz not null default now(),
    unique (org_id, id),
    unique (org_id, document_id, version_number),
    foreign key (org_id, document_id) references caseproof.documents(org_id, id)
);

create table caseproof.audit_events (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    case_id uuid not null,
    actor_type text not null check (actor_type in ('human', 'service')),
    actor_user_id uuid references auth.users(id),
    action text not null check (length(btrim(action)) > 0),
    event_schema_version text not null check (length(btrim(event_schema_version)) > 0),
    correlation_id uuid not null,
    previous_state text,
    new_state text,
    input_sha256_hex text not null check (input_sha256_hex ~ '^[0-9a-f]{64}$'),
    occurred_at timestamptz not null default now(),
    unique (org_id, case_id, id),
    foreign key (org_id, case_id) references caseproof.cases(org_id, id),
    foreign key (org_id, actor_user_id)
        references caseproof.organization_members(org_id, user_id),
    check (
        (actor_type = 'human' and actor_user_id is not null)
        or (actor_type = 'service' and actor_user_id is null)
    )
);

create table caseproof.idempotency_records (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null,
    case_id uuid not null,
    operation text not null check (length(btrim(operation)) > 0),
    idempotency_key text not null check (length(btrim(idempotency_key)) > 0),
    input_sha256_hex text not null check (input_sha256_hex ~ '^[0-9a-f]{64}$'),
    response_reference text,
    committed_at timestamptz not null default now(),
    unique (org_id, case_id, operation, idempotency_key),
    foreign key (org_id, case_id) references caseproof.cases(org_id, id)
);

-- A membership lookup from an authenticated user must be indexed on user_id
-- because the PK begins with org_id. RLS queries also filter by org_id.
create index organization_members_user_org_idx
    on caseproof.organization_members(user_id, org_id)
    where active;
create index cases_org_revision_idx
    on caseproof.cases(org_id, case_revision, id);
create index documents_org_case_idx
    on caseproof.documents(org_id, case_id, id);
create index document_versions_org_doc_idx
    on caseproof.document_versions(org_id, document_id, version_number);
create index audit_events_org_case_cursor_idx
    on caseproof.audit_events(org_id, case_id, occurred_at, id);

-- RLS defense in depth. Authentication claims must come from the actual
-- Supabase PostgREST-authenticated request, not arbitrary SQL set_config.
alter table caseproof.organizations enable row level security;
alter table caseproof.organization_members enable row level security;
alter table caseproof.cases enable row level security;
alter table caseproof.documents enable row level security;
alter table caseproof.document_versions enable row level security;
alter table caseproof.audit_events enable row level security;
alter table caseproof.idempotency_records enable row level security;

-- Authenticated users can view only their OWN current membership records.
-- It has no recursive membership-table reference.
create policy own_active_membership_read
on caseproof.organization_members for select to authenticated
using (active and user_id = (select auth.uid()));

-- Other policies use the self-only membership SELECT above and do not
-- require a SECURITY DEFINER helper. A revoked membership takes effect
-- on the next statement/query (not an already-running transaction).
create policy tenant_organization_read
on caseproof.organizations for select to authenticated
using (exists (
    select 1 from caseproof.organization_members as m
    where m.org_id = organizations.id
      and m.user_id = (select auth.uid())
      and m.active
      and 'case:read' = any(m.actions)
));

create policy tenant_case_read
on caseproof.cases for select to authenticated
using (exists (
    select 1 from caseproof.organization_members as m
    where m.org_id = cases.org_id
      and m.user_id = (select auth.uid())
      and m.active
      and 'case:read' = any(m.actions)
));

create policy tenant_document_read
on caseproof.documents for select to authenticated
using (exists (
    select 1 from caseproof.organization_members as m
    where m.org_id = documents.org_id
      and m.user_id = (select auth.uid())
      and m.active
      and 'evidence:read' = any(m.actions)
));

create policy tenant_document_version_read
on caseproof.document_versions for select to authenticated
using (exists (
    select 1 from caseproof.organization_members as m
    where m.org_id = document_versions.org_id
      and m.user_id = (select auth.uid())
      and m.active
      and 'evidence:read' = any(m.actions)
));

-- Privileged server operation remains unimplemented. No client INSERT,
-- UPDATE, DELETE, audit read, audit write or idempotency access is granted.
revoke all on all tables in schema caseproof from public, anon, authenticated;
grant select on caseproof.organizations,
    caseproof.organization_members,
    caseproof.cases,
    caseproof.documents,
    caseproof.document_versions
to authenticated;

-- No SECURITY DEFINER or dynamic membership JWT roles.
-- Default privileges for future tables require a separate, reviewed change.
