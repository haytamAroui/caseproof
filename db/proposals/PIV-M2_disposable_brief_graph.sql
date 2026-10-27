-- PIV-M2 versioned brief graph: disposable, security-review-only proposal.
-- No live Supabase migration, user/API write route, SECURITY DEFINER or JWT
-- parameter. Synthetic server-owned actor is validated by the fixture adapter.
begin;

create table caseproof._m2_brief_versions (
    org_id uuid not null,
    case_id uuid not null,
    brief_id uuid not null,
    version_id uuid not null,
    revision bigint not null check(revision >= 1),
    parent_version_id uuid,
    document_id uuid not null,
    document_version_id uuid not null,
    vault_intent_id uuid not null,
    original_sha256 text not null check(original_sha256 ~ '^[0-9a-f]{64}$'),
    representation_sha256 text not null check(representation_sha256 ~ '^[0-9a-f]{64}$'),
    parser_id text not null check(length(parser_id) between 1 and 256),
    representation text not null check(octet_length(representation) <= 480000),
    document_role text not null check(document_role in ('own_draft','opponent_brief')),
    graph_sha256 text not null check(graph_sha256 ~ '^[0-9a-f]{64}$'),
    case_revision bigint not null check(case_revision >= 1),
    exhibit_revision bigint not null check(exhibit_revision >= 1),
    actor_id uuid not null,
    created_at timestamptz not null default now(),
    primary key(org_id,case_id,brief_id,version_id),
    unique(org_id,case_id,brief_id,revision),
    foreign key(org_id,case_id) references caseproof.cases(org_id,id),
    foreign key(org_id,document_id) references caseproof.documents(org_id,id),
    foreign key(org_id,document_version_id)
        references caseproof.document_versions(org_id,id),
    foreign key(org_id,actor_id)
        references caseproof.organization_members(org_id,user_id)
);

create table caseproof._m2_brief_references (
    org_id uuid not null, case_id uuid not null, brief_id uuid not null,
    version_id uuid not null, reference_order integer not null check(reference_order >= 0),
    reference_id text not null
        check(length(reference_id) between 1 and 128),
    exhibit_label text not null check(length(exhibit_label) between 1 and 160),
    exact_quote text,
    pdf_page integer check(pdf_page between 1 and 100000),
    primary key(org_id,case_id,brief_id,version_id,reference_id),
    unique(org_id,case_id,brief_id,version_id,reference_order),
    foreign key(org_id,case_id,brief_id,version_id)
        references caseproof._m2_brief_versions(org_id,case_id,brief_id,version_id)
);
create table caseproof._m2_brief_assertions (
    org_id uuid not null, case_id uuid not null, brief_id uuid not null,
    version_id uuid not null,
    claim_order integer not null check(claim_order >= 0),
    claim_id text not null check(length(claim_id) between 1 and 160),
    reference_id text not null,
    text_start integer not null check(text_start >= 0),
    text_end integer not null check(text_end > text_start),
    assertion_text text not null,
    kind text not null check(kind in ('money','date')),
    fact_role text not null check(fact_role in ('payment','due','delivery','invoice')),
    language text not null check(language in ('nl','fr','en')),
    source_language text not null check(source_language in ('nl','fr','en')),
    primary key(org_id,case_id,brief_id,version_id,claim_id),
    unique(org_id,case_id,brief_id,version_id,claim_order),
    foreign key(org_id,case_id,brief_id,version_id,reference_id)
        references caseproof._m2_brief_references(
            org_id,case_id,brief_id,version_id,reference_id)
);
create table caseproof._m2_brief_heads (
    org_id uuid not null, case_id uuid not null, brief_id uuid not null,
    revision bigint not null default 0 check(revision >= 0),
    version_id uuid,
    primary key(org_id,case_id,brief_id),
    foreign key(org_id,case_id) references caseproof.cases(org_id,id),
    foreign key(org_id,case_id,brief_id,version_id)
        references caseproof._m2_brief_versions(org_id,case_id,brief_id,version_id),
    check ((revision=0 and version_id is null) or
           (revision>0 and version_id is not null))
);
create table caseproof._m2_brief_events (
    org_id uuid not null, case_id uuid not null, brief_id uuid not null,
    revision bigint not null check(revision >= 1),
    request_id uuid not null, actor_id uuid not null,
    version_id uuid not null, graph_sha256 text not null,
    expected_revision bigint not null check(expected_revision >= 0),
    audit_id uuid not null,
    created_at timestamptz not null default now(),
    primary key(org_id,case_id,brief_id,revision),
    unique(org_id,case_id,brief_id,request_id),
    unique(audit_id),
    foreign key(org_id,case_id,brief_id,version_id)
        references caseproof._m2_brief_versions(org_id,case_id,brief_id,version_id),
    foreign key(org_id,case_id,audit_id)
        references caseproof.audit_events(org_id,case_id,id)
);

-- The transaction may only change the explicit revision head. The original
-- document graph, reference rows, assertion rows and audit event are immutable.
create function caseproof._m2_brief_immutable()
returns trigger language plpgsql security invoker
set search_path=pg_catalog,pg_temp as $$
begin
    raise exception 'immutable M2 brief history' using errcode='55000';
end $$;

create trigger m2_brief_versions_immutable before update or delete
    on caseproof._m2_brief_versions for each row
    execute function caseproof._m2_brief_immutable();
create trigger m2_brief_references_immutable before update or delete
    on caseproof._m2_brief_references for each row
    execute function caseproof._m2_brief_immutable();
create trigger m2_brief_assertions_immutable before update or delete
    on caseproof._m2_brief_assertions for each row
    execute function caseproof._m2_brief_immutable();
create trigger m2_brief_events_immutable before update or delete
    on caseproof._m2_brief_events for each row
    execute function caseproof._m2_brief_immutable();

alter table caseproof._m2_brief_versions enable row level security;
alter table caseproof._m2_brief_references enable row level security;
alter table caseproof._m2_brief_assertions enable row level security;
alter table caseproof._m2_brief_heads enable row level security;
alter table caseproof._m2_brief_events enable row level security;
revoke all on caseproof._m2_brief_versions,
    caseproof._m2_brief_references,caseproof._m2_brief_assertions,
    caseproof._m2_brief_heads,caseproof._m2_brief_events
from public,anon,authenticated;
revoke execute on function caseproof._m2_brief_immutable()
from public,anon,authenticated;
commit;
