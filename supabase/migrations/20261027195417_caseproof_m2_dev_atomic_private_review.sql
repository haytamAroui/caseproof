-- Candidate-only deployment boundary. Do not apply to caseproof-dev without
-- approved independent security review, a canonical migration and M1 signoff.
-- Source tables are merged byte-for-byte apart from their outer transaction
-- wrappers. Fail whole transaction before adding any M2 relation.
do $gate$
declare
    actual_policy_count integer;
begin
    if to_regclass('caseproof._m1_matter_grants') is null
        or to_regclass('caseproof.cases') is null
        or to_regclass('caseproof.audit_events') is null
        or to_regclass('caseproof.documents') is null
        or to_regclass('caseproof.document_versions') is null
        or to_regclass('auth.users') is null then
        raise exception 'M1 default-private foundation absent' using errcode='55000';
    end if;
    if exists (
        select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
        where n.nspname='caseproof' and left(c.relname,4)='_m2_'
    ) then
        raise exception 'M2 schema already present; refuse blind retry'
            using errcode='55000';
    end if;
    if exists (select 1 from auth.users)
        or exists (select 1 from caseproof.organizations)
        or exists (select 1 from caseproof.cases)
        or exists (select 1 from caseproof._m1_matter_grants)
        or exists (select 1 from caseproof.audit_events) then
        raise exception 'nonempty development schema; migration not approved for data backfill'
            using errcode='55000';
    end if;
    select count(*) into actual_policy_count from pg_policies
    where schemaname='caseproof' and (
        (tablename='cases' and policyname='m1_private_case_read')
        or (tablename='documents' and policyname='m1_private_document_read')
        or (tablename='document_versions' and policyname='m1_private_document_version_read')
        or (tablename='_m1_matter_grants' and policyname='m1_own_private_grant_read')
    ) and cmd='SELECT' and roles=array['authenticated']::name[];
    if actual_policy_count<>4 or exists (
        select 1 from pg_policies where schemaname='caseproof'
          and tablename in ('cases','documents','document_versions','_m1_matter_grants')
          and cmd in ('SELECT','ALL')
          and not (
               (tablename='cases' and policyname='m1_private_case_read')
            or (tablename='documents' and policyname='m1_private_document_read')
            or (tablename='document_versions'
                and policyname='m1_private_document_version_read')
            or (tablename='_m1_matter_grants'
                and policyname='m1_own_private_grant_read')
          )
    ) then
        raise exception 'unexpected M1 RLS policy; M2 not installed'
            using errcode='42501';
    end if;
    if exists (
        select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
        where n.nspname='caseproof'
        and c.relname in ('cases','documents','document_versions','_m1_matter_grants')
        and not c.relrowsecurity
    ) then
        raise exception 'M1 private relations lack RLS' using errcode='42501';
    end if;
    if not has_schema_privilege('authenticated','caseproof','USAGE') then
        raise exception 'M1 authenticated role/schema boundary changed'
            using errcode='42501';
    end if;
end
$gate$;

-- BEGIN PINNED SOURCE: db/proposals/PIV-M2_disposable_review_runs.sql
-- PIV-M2 disposable PostgreSQL proposal: NO live Supabase migration.
-- Synthetic server-owned actor only; owner connection does not prove signed Auth.
-- Schema is intentionally private; only isolated localhost CI loads this file.

create table caseproof._m2_check_runs (
  org_id uuid not null,
  case_id uuid not null,
  snapshot_sha text not null check(snapshot_sha ~ '^[0-9a-f]{64}$'),
  payload_sha text not null check(payload_sha ~ '^[0-9a-f]{64}$'),
  payload text not null check(octet_length(payload) between 2 and 262144),
  brief_version_id text not null check(length(brief_version_id) between 1 and 128),
  case_revision bigint not null check(case_revision > 0),
  exhibit_revision bigint not null check(exhibit_revision > 0),
  actor_id uuid not null,
  created_at timestamptz not null default now(),
  primary key(org_id,case_id,snapshot_sha),
  foreign key(org_id,case_id) references caseproof.cases(org_id,id),
  foreign key(org_id,actor_id) references caseproof.organization_members(org_id,user_id)
);

create table caseproof._m2_review_heads (
  org_id uuid not null, case_id uuid not null, snapshot_sha text not null,
  revision bigint not null default 0 check(revision >= 0),
  event_sha text not null check(event_sha ~ '^[0-9a-f]{64}$'),
  primary key(org_id,case_id,snapshot_sha),
  foreign key(org_id,case_id,snapshot_sha)
    references caseproof._m2_check_runs(org_id,case_id,snapshot_sha)
);

create table caseproof._m2_review_events (
  org_id uuid not null, case_id uuid not null, snapshot_sha text not null,
  revision bigint not null check(revision > 0),
  request_id uuid not null,
  actor_id uuid not null,
  previous_sha text not null check(previous_sha ~ '^[0-9a-f]{64}$'),
  event_sha text not null check(event_sha ~ '^[0-9a-f]{64}$'),
  decision text not null check(octet_length(decision) between 2 and 8192),
  audit_id uuid not null,
  created_at timestamptz not null default now(),
  primary key(org_id,case_id,snapshot_sha,revision),
  unique(org_id,case_id,snapshot_sha,request_id),
  unique(audit_id),
  foreign key(org_id,case_id,snapshot_sha)
    references caseproof._m2_check_runs(org_id,case_id,snapshot_sha),
  foreign key(org_id,actor_id) references caseproof.organization_members(org_id,user_id),
  foreign key(org_id,case_id,audit_id) references caseproof.audit_events(org_id,case_id,id)
);

create table caseproof._m2_review_receipts (
  org_id uuid not null, case_id uuid not null, snapshot_sha text not null,
  request_id uuid not null,
  input_sha text not null check(input_sha ~ '^[0-9a-f]{64}$'),
  revision bigint not null check(revision > 0),
  event_sha text not null check(event_sha ~ '^[0-9a-f]{64}$'),
  primary key(org_id,case_id,snapshot_sha,request_id),
  foreign key(org_id,case_id,snapshot_sha,revision)
    references caseproof._m2_review_events(org_id,case_id,snapshot_sha,revision)
);

create function caseproof._m2_deny_event_mutation()
returns trigger language plpgsql security invoker
set search_path=pg_catalog,pg_temp as $$
begin
  raise exception 'M2 event history immutable' using errcode='55000';
end $$;

create trigger m2_review_events_append_only
before update or delete on caseproof._m2_review_events
for each row execute function caseproof._m2_deny_event_mutation();

create trigger m2_review_receipts_append_only
before update or delete on caseproof._m2_review_receipts
for each row execute function caseproof._m2_deny_event_mutation();

create trigger m2_check_runs_immutable
before update or delete on caseproof._m2_check_runs
for each row execute function caseproof._m2_deny_event_mutation();

alter table caseproof._m2_check_runs enable row level security;
alter table caseproof._m2_review_heads enable row level security;
alter table caseproof._m2_review_events enable row level security;
alter table caseproof._m2_review_receipts enable row level security;

revoke all on caseproof._m2_check_runs,caseproof._m2_review_heads,
  caseproof._m2_review_events,caseproof._m2_review_receipts
from public,anon,authenticated;
revoke execute on function caseproof._m2_deny_event_mutation()
from public,anon,authenticated;
-- END PINNED SOURCE: db/proposals/PIV-M2_disposable_review_runs.sql


-- BEGIN PINNED SOURCE: db/proposals/PIV-M2_disposable_brief_graph.sql
-- PIV-M2 versioned brief graph: disposable, security-review-only proposal.
-- No live Supabase migration, user/API write route, SECURITY DEFINER or JWT
-- parameter. Synthetic server-owned actor is validated by the fixture adapter.

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
-- END PINNED SOURCE: db/proposals/PIV-M2_disposable_brief_graph.sql


-- BEGIN PINNED SOURCE: db/proposals/PIV-M2_disposable_correction_recheck.sql
-- M2 correction recovery journal, DISPOSABLE security-review proposal.
-- No live Supabase migration or customer/HTTP write route.

create table caseproof._m2_correction_plans (
    org_id uuid not null, case_id uuid not null, brief_id uuid not null,
    request_id uuid not null, actor_id uuid not null,
    old_run_sha text not null check(old_run_sha ~ '^[0-9a-f]{64}$'),
    old_version_id uuid not null,
    new_version_id uuid not null,
    new_document_version_id uuid not null,
    new_vault_intent_id uuid not null,
    expected_brief_revision bigint not null check(expected_brief_revision > 0),
    expected_review_revision bigint not null check(expected_review_revision > 0),
    input_sha text not null check(input_sha ~ '^[0-9a-f]{64}$'),
    corrected_text_sha text not null check(corrected_text_sha ~ '^[0-9a-f]{64}$'),
    graph_sha text not null check(graph_sha ~ '^[0-9a-f]{64}$'),
    audit_id uuid not null,
    created_at timestamptz not null default now(),
    primary key(org_id,case_id,brief_id,request_id),
    unique(org_id,case_id,brief_id,new_version_id),
    unique(audit_id),
    foreign key(org_id,case_id) references caseproof.cases(org_id,id),
    foreign key(org_id,case_id,brief_id,old_version_id)
        references caseproof._m2_brief_versions(org_id,case_id,brief_id,version_id),
    foreign key(org_id,case_id,old_run_sha)
        references caseproof._m2_check_runs(org_id,case_id,snapshot_sha),
    foreign key(org_id,new_document_version_id)
        references caseproof.document_versions(org_id,id),
    foreign key(org_id,case_id,audit_id)
        references caseproof.audit_events(org_id,case_id,id)
);
create table caseproof._m2_correction_events (
    org_id uuid not null, case_id uuid not null, brief_id uuid not null,
    request_id uuid not null,
    phase text not null check(phase in ('graph_applied','rechecked')),
    actor_id uuid not null,
    graph_sha text not null check(graph_sha ~ '^[0-9a-f]{64}$'),
    check_run_sha text,
    audit_id uuid not null,
    created_at timestamptz not null default now(),
    primary key(org_id,case_id,brief_id,request_id,phase),
    unique(audit_id),
    foreign key(org_id,case_id,brief_id,request_id)
        references caseproof._m2_correction_plans(org_id,case_id,brief_id,request_id),
    foreign key(org_id,case_id,audit_id)
        references caseproof.audit_events(org_id,case_id,id),
    check ((phase='graph_applied' and check_run_sha is null) or
           (phase='rechecked' and check_run_sha ~ '^[0-9a-f]{64}$'))
);
-- Append-only plans, events and audit: prior source versions never mutated.
create trigger m2_correction_plans_immutable
before update or delete on caseproof._m2_correction_plans
for each row execute function caseproof._m2_brief_immutable();
create trigger m2_correction_events_immutable
before update or delete on caseproof._m2_correction_events
for each row execute function caseproof._m2_brief_immutable();
alter table caseproof._m2_correction_plans enable row level security;
alter table caseproof._m2_correction_events enable row level security;
revoke all on caseproof._m2_correction_plans,caseproof._m2_correction_events
from public,anon,authenticated;
-- END PINNED SOURCE: db/proposals/PIV-M2_disposable_correction_recheck.sql

-- Audit the resulting security posture BEFORE commit. Default deny to all
-- client roles remains mandatory, including function execute.
do $verify$
declare
    relation_count integer;
begin
    select count(*) into relation_count
    from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='caseproof'
      and c.relkind in ('r','p') and left(c.relname,4)='_m2_';
    if relation_count<>11 then
        raise exception 'unexpected number of M2 private relations'
            using errcode='55000';
    end if;
    if exists (
      select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='caseproof' and c.relkind in ('r','p')
        and left(c.relname,4)='_m2_'
        and (
          not c.relrowsecurity
          or has_table_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,DELETE')
          or has_table_privilege('authenticated',c.oid,'SELECT,INSERT,UPDATE,DELETE')
        )
    ) then
        raise exception 'M2 client privileges or RLS unsafe' using errcode='42501';
    end if;
    if has_function_privilege('anon','caseproof._m2_deny_event_mutation()','EXECUTE')
      or has_function_privilege('authenticated','caseproof._m2_deny_event_mutation()','EXECUTE')
      or has_function_privilege('anon','caseproof._m2_brief_immutable()','EXECUTE')
      or has_function_privilege('authenticated','caseproof._m2_brief_immutable()','EXECUTE')
    then
       raise exception 'M2 trigger function visible to clients' using errcode='42501';
    end if;
end
$verify$;
