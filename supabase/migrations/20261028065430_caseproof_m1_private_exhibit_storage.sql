-- Development candidate: private M1 exhibit-register storage foundation.
-- PRE-MERGE REVIEW CANDIDATE; not applied. No client-facing writer or grants.
-- The existing matter-grant table is intentionally not recreated.
begin;

create table caseproof._m1_exhibit_heads (
  org_id uuid not null,
  case_id uuid not null,
  revision bigint not null default 0 check (revision >= 0),
  payload jsonb,
  payload_sha256 text,
  updated_at timestamptz not null default now(),
  primary key (org_id, case_id),
  foreign key (org_id, case_id) references caseproof.cases(org_id, id),
  check ((revision = 0 and payload is null and payload_sha256 is null)
    or (revision > 0 and jsonb_typeof(payload) = 'object'
        and payload_sha256 ~ '^[0-9a-f]{64}$'))
);

create table caseproof._m1_exhibit_events (
  org_id uuid not null,
  case_id uuid not null,
  revision bigint not null check (revision >= 1),
  request_id uuid not null,
  actor_user_id uuid not null,
  expected_revision bigint not null check (expected_revision >= 0),
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  audit_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (org_id, case_id, revision),
  unique (org_id, case_id, request_id),
  unique (audit_id),
  foreign key (org_id, case_id) references caseproof.cases(org_id, id),
  foreign key (org_id, actor_user_id)
    references caseproof.organization_members(org_id, user_id),
  foreign key (org_id, case_id, audit_id)
    references caseproof.audit_events(org_id, case_id, id)
);

create function caseproof._m1_exhibit_event_guard()
returns trigger language plpgsql security invoker
set search_path = pg_catalog, pg_temp as $guard$
begin
  raise exception 'exhibit history immutable' using errcode = '55000';
end
$guard$;

create trigger m1_exhibit_events_append_only
before update or delete on caseproof._m1_exhibit_events
for each row execute function caseproof._m1_exhibit_event_guard();

alter table caseproof._m1_exhibit_heads enable row level security;
alter table caseproof._m1_exhibit_events enable row level security;
revoke all on caseproof._m1_exhibit_heads, caseproof._m1_exhibit_events
  from public, anon, authenticated;
revoke all on function caseproof._m1_exhibit_event_guard()
  from public, anon, authenticated;

commit;
