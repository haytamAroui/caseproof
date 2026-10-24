-- Disposable PostgreSQL integration only. No installed migration or public runtime grant.
begin;
create table caseproof._worker_jobs (
    org_id uuid not null,
    case_id uuid not null,
    request_id uuid not null,
    actor_id uuid not null,
    input_sha text not null check (input_sha ~ '^[0-9a-f]{64}$'),
    spec_json text not null check (octet_length(spec_json) <= 131072),
    state text not null default 'queued' check (state in ('queued','running','retry_wait','succeeded','blocked','failed','cancelled','outcome_unknown')),
    attempt integer not null default 0 check (attempt between 0 and 5),
    revision integer not null default 1 check (revision > 0),
    worker_id uuid,
    lease_token uuid,
    lease_until timestamptz,
    available_at timestamptz not null default clock_timestamp(),
    deadline_at timestamptz not null,
    result_json text check (octet_length(result_json) <= 2097152),
    result_sha text check (result_sha ~ '^[0-9a-f]{64}$'),
    reason text not null default 'submitted',
    created_at timestamptz not null default clock_timestamp(),
    primary key (org_id,case_id,request_id),
    foreign key (org_id,case_id) references caseproof.cases(org_id,id),
    foreign key (org_id,actor_id) references caseproof.organization_members(org_id,user_id),
    check ((state='running') = (lease_token is not null and worker_id is not null and lease_until is not null)),
    check ((result_json is null) = (result_sha is null)),
    check (state <> 'succeeded' or result_json is not null)
);
create index _worker_ready_idx on caseproof._worker_jobs(org_id,case_id,available_at,created_at,request_id)
    where state in ('queued','retry_wait');
create index _worker_expired_idx on caseproof._worker_jobs(org_id,case_id,lease_until)
    where state='running';
create index _worker_actor_idx on caseproof._worker_jobs(org_id,actor_id);
create table caseproof._worker_events (
    org_id uuid not null,
    case_id uuid not null,
    request_id uuid not null,
    revision integer not null check (revision > 0),
    state text not null,
    attempt integer not null,
    reason text not null,
    worker_id uuid,
    created_at timestamptz not null default clock_timestamp(),
    primary key (org_id,case_id,request_id,revision),
    foreign key (org_id,case_id,request_id) references caseproof._worker_jobs(org_id,case_id,request_id)
);
alter table caseproof._worker_jobs enable row level security;
alter table caseproof._worker_events enable row level security;
revoke all on caseproof._worker_jobs,caseproof._worker_events from public,anon,authenticated;
commit;
