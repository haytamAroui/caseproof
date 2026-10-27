-- M2 correction recovery journal, DISPOSABLE security-review proposal.
-- No live Supabase migration or customer/HTTP write route.
begin;
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
commit;
