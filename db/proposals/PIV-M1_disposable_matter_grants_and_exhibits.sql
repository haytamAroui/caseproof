-- PIV-M1 proposed secure-case/exhibit SQL: disposable verification ONLY.
-- Requires independent human security review before any real Supabase migration.
-- No SECURITY DEFINER, no API execute privilege and NO production schema deployment.
-- p_actor is synthetic in disposable tests and MUST NOT come from HTTP inputs.
begin;

create table caseproof._m1_matter_grants (
  org_id uuid not null,
  case_id uuid not null,
  user_id uuid not null,
  role text not null check(role in ('viewer','reviewer')),
  permissions text[] not null default '{}'::text[]
    check (permissions <@ array['case:read','coverage:read','evidence:read',
      'review:request','finding:write','evidence:upload','evidence:index',
      'exhibit:confirm','draft:check']::text[]),
  active boolean not null default true,
  revision bigint not null default 1 check(revision >= 1),
  primary key (org_id,case_id,user_id),
  foreign key (org_id,case_id) references caseproof.cases(org_id,id),
  foreign key (org_id,user_id) references caseproof.organization_members(org_id,user_id)
);

create table caseproof._m1_exhibit_heads (
  org_id uuid not null,
  case_id uuid not null,
  revision bigint not null default 0 check (revision >= 0),
  payload jsonb,
  payload_sha256 text,
  updated_at timestamptz not null default now(),
  primary key (org_id,case_id),
  foreign key (org_id,case_id) references caseproof.cases(org_id,id),
  check ((revision=0 and payload is null and payload_sha256 is null)
     or (revision>0 and jsonb_typeof(payload)='object'
         and payload_sha256 ~ '^[0-9a-f]{64}$'))
);

create table caseproof._m1_exhibit_events (
  org_id uuid not null,
  case_id uuid not null,
  revision bigint not null check (revision >= 1),
  request_id uuid not null,
  actor_user_id uuid not null,
  expected_revision bigint not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  payload jsonb not null,
  audit_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (org_id,case_id,revision),
  unique (org_id,case_id,request_id),
  unique (audit_id),
  foreign key (org_id,case_id) references caseproof.cases(org_id,id),
  foreign key (org_id,actor_user_id) references caseproof.organization_members(org_id,user_id),
  foreign key (org_id,case_id,audit_id) references caseproof.audit_events(org_id,case_id,id)
);

create function caseproof._m1_exhibit_event_guard()
returns trigger language plpgsql security invoker
set search_path=pg_catalog,pg_temp as $$
begin
  raise exception 'exhibit history immutable' using errcode='55000';
end
$$;

create trigger m1_exhibit_events_append_only
before update or delete on caseproof._m1_exhibit_events
for each row execute function caseproof._m1_exhibit_event_guard();

-- Controlled transition under one row lock. Identifies the actor only for
-- isolated disposable fixtures. In a production security-approved replacement,
-- derive actor identity from the authenticated DB session, not p_actor.
create function caseproof._m1_disposable_confirm_exhibits(
  p_actor uuid, p_case uuid, p_request uuid,
  p_expected bigint, p_payload jsonb, p_sha text
) returns table(committed_revision bigint, resulting_audit uuid, replay boolean)
language plpgsql security invoker
set search_path=pg_catalog,pg_temp as $$
declare
  v_org uuid;
  v_rev bigint;
  v_previous caseproof._m1_exhibit_events%rowtype;
  v_audit uuid;
begin
  if p_actor is null or p_case is null or p_request is null
     or p_expected is null or p_expected<0
     or p_payload is null or jsonb_typeof(p_payload)!='object'
     or p_payload->>'schema' != 'caseproof-exhibit-register-v1'
     or jsonb_typeof(p_payload->'entries') != 'array'
     or jsonb_array_length(p_payload->'entries') > 512
     or p_sha !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid register command' using errcode='22023';
  end if;
  select c.org_id into v_org
  from caseproof.cases c
  join caseproof.organization_members m
    on m.org_id=c.org_id and m.user_id=p_actor and m.active
  join caseproof._m1_matter_grants g
    on g.org_id=c.org_id and g.case_id=c.id
       and g.user_id=p_actor and g.active and g.role='reviewer'
       and 'exhibit:confirm'=any(g.permissions)
  where c.id=p_case and 'case:read'=any(m.actions)
      and 'review:request'=any(m.actions)
  limit 2;
  if v_org is null then
    raise exception 'matter unavailable' using errcode='42501';
  end if;
  insert into caseproof._m1_exhibit_heads(org_id,case_id) values (v_org,p_case)
  on conflict do nothing;
  select h.revision into v_rev
  from caseproof._m1_exhibit_heads h
  where h.org_id=v_org and h.case_id=p_case for update;
  select * into v_previous from caseproof._m1_exhibit_events e
  where e.org_id=v_org and e.case_id=p_case and e.request_id=p_request;
  if found then
    if v_previous.payload_sha256 != p_sha
       or v_previous.payload != p_payload
       or v_previous.actor_user_id != p_actor
       or v_previous.expected_revision != p_expected then
      raise exception 'conflicting request replay' using errcode='23505';
    end if;
    return query select v_previous.revision, v_previous.audit_id, true;
    return;
  end if;
  if v_rev != p_expected then
    raise exception 'stale register version' using errcode='40001';
  end if;
  -- Claim labels and page maps are confirmed only by the server application
  -- contract, not from this JSON or from an AI proposal.
  v_audit:=gen_random_uuid();
  insert into caseproof.audit_events(
    id, org_id, case_id, actor_type, actor_user_id, action,
    event_schema_version, correlation_id, input_sha256_hex
  ) values (
    v_audit,v_org,p_case,'human',p_actor,'m1_exhibit_register_confirm',
    'm1-v1',p_request,p_sha
  );
  update caseproof._m1_exhibit_heads h
  set revision=p_expected+1,payload=p_payload,payload_sha256=p_sha,updated_at=now()
  where h.org_id=v_org and h.case_id=p_case and h.revision=p_expected;
  if not found then raise exception 'stale register version' using errcode='40001'; end if;
  insert into caseproof._m1_exhibit_events (
    org_id,case_id,revision,request_id,actor_user_id,
    expected_revision,payload_sha256,payload,audit_id
  ) values (v_org,p_case,p_expected+1,p_request,p_actor,p_expected,p_sha,p_payload,v_audit);
  return query select p_expected+1,v_audit,false;
end
$$;

alter table caseproof._m1_matter_grants enable row level security;
alter table caseproof._m1_exhibit_heads enable row level security;
alter table caseproof._m1_exhibit_events enable row level security;
-- Proposal does NOT expose these tables or disposable command to user/API roles.
revoke all on caseproof._m1_matter_grants,
  caseproof._m1_exhibit_heads,caseproof._m1_exhibit_events
from public,anon,authenticated;
revoke execute on function caseproof._m1_disposable_confirm_exhibits(
  uuid,uuid,uuid,bigint,jsonb,text
) from public,anon,authenticated;
revoke execute on function caseproof._m1_exhibit_event_guard()
from public,anon,authenticated;
commit;
