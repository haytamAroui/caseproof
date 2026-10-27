-- PIV-M2 disposable PostgreSQL proposal: NO live Supabase migration.
-- Synthetic server-owned actor only; owner connection does not prove signed Auth.
-- Schema is intentionally private; only isolated localhost CI loads this file.
begin;

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
commit;
