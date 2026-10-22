-- S2-009b / disposable PostgreSQL 17 reference ONLY.
-- NEVER apply to Supabase, deploy, create a live bucket, or grant API access.
-- Synthetic p_actor is NOT authenticated identity. The proof digests below
-- are caller-asserted test values, NOT independently checked object bytes.
-- Does NOT yet implement actual Storage object verification, availability
-- head publication, review approval, source scanning, or production grants.
begin;

create table caseproof._s2_009b_vault_intents (
  org_id uuid not null,
  case_id uuid not null,
  intent_id uuid not null,
  actor_user_id uuid not null,
  document_id uuid not null,
  document_version_id uuid not null,
  object_key text not null,
  sha256_hex text not null check (sha256_hex ~ '^[0-9a-f]{64}$'),
  byte_length bigint not null check (byte_length between 1 and 5242880),
  media_type text not null check (media_type in
     ('application/pdf','application/xml','text/xml','text/plain')),
  state text not null default 'pending'
    check (state in ('pending','verified','unavailable')),
  intent_revision bigint not null default 1 check (intent_revision > 0),
  created_audit_id uuid not null,
  last_audit_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (org_id, case_id, intent_id),
  unique (object_key),
  foreign key (org_id, case_id) references caseproof.cases(org_id,id),
  foreign key (org_id, actor_user_id)
      references caseproof.organization_members(org_id,user_id),
  foreign key (org_id, case_id, document_id)
      references caseproof.documents(org_id,case_id,id),
  foreign key (org_id, document_id, document_version_id, sha256_hex)
      references caseproof.document_versions(
          org_id,document_id,id,original_sha256_hex),
  foreign key (org_id,case_id,created_audit_id)
      references caseproof.audit_events(org_id,case_id,id),
  foreign key (org_id,case_id,last_audit_id)
      references caseproof.audit_events(org_id,case_id,id)
);

create table caseproof._s2_009b_availability_events (
  org_id uuid not null,
  case_id uuid not null,
  intent_id uuid not null,
  intent_revision bigint not null check (intent_revision > 1),
  status text not null check (status in ('verified','unavailable')),
  reason text not null check (reason in ('readback_verified','missing','digest_mismatch')),
  case_revision bigint not null check (case_revision > 0),
  audit_event_id uuid not null,
  observed_at timestamptz not null default now(),
  primary key (org_id,case_id,intent_id,intent_revision),
  unique (audit_event_id),
  foreign key (org_id,case_id,intent_id)
      references caseproof._s2_009b_vault_intents(org_id,case_id,intent_id),
  foreign key (org_id,case_id,audit_event_id)
      references caseproof.audit_events(org_id,case_id,id),
  check ((status='verified' and reason='readback_verified')
     or (status='unavailable' and reason in ('missing','digest_mismatch')))
);

-- Immutable history. DB administrator can still disable these test triggers;
-- do not present them as storage tamper resistance or production security.
create function caseproof._s2_009b_immutable_availability()
returns trigger language plpgsql security invoker
set search_path=pg_catalog,pg_temp
as $guard$
begin
  raise exception 'availability history is append-only' using errcode='55000';
end
$guard$;

create trigger s2_009b_availability_no_rewrite
before update or delete on caseproof._s2_009b_availability_events
for each row execute function caseproof._s2_009b_immutable_availability();

create function caseproof._s2_009b_disposable_command(
  p_actor uuid,
  p_case uuid,
  p_intent uuid,
  p_operation text,
  p_request_key text,
  p_correlation uuid,
  p_document_version uuid default null,
  p_object_key text default null,
  p_sha text default null,
  p_byte_length bigint default null,
  p_media text default null,
  p_expected_intent_revision bigint default null,
  p_reason text default null,
  p_fault text default null
)
returns table(
  resulting_state text,
  resulting_intent_revision bigint,
  resulting_case_revision bigint,
  recorded_audit uuid,
  idempotent_replay boolean
)
language plpgsql security invoker
set search_path=pg_catalog,pg_temp
as $body$
declare
  v_org uuid;
  v_actions text[];
  v_case caseproof.cases%rowtype;
  v_intent caseproof._s2_009b_vault_intents%rowtype;
  v_receipt caseproof.idempotency_records%rowtype;
  v_event uuid;
  v_next_case bigint;
  v_next_intent bigint;
  v_state text;
  v_operation text;
  v_fingerprint text;
  v_document uuid;
  v_existing_event uuid;
  v_existing_intent_revision bigint;
  v_existing_case_revision bigint;
  v_expected_object_prefix text;
begin
  if p_actor is null or p_case is null or p_intent is null
     or p_correlation is null
     or p_intent::text !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
     or p_operation not in ('stage','verify','unavailable')
     or p_request_key is null or length(p_request_key) not between 1 and 128
     or btrim(p_request_key) != p_request_key
     or p_fault not in ('audit','availability','receipt') then
    raise exception 'invalid disposable vault operation' using errcode='22023';
  end if;
  if p_operation='stage' and (
       p_document_version is null
       or p_object_key is null or p_sha !~ '^[0-9a-f]{64}$'
       or p_byte_length is null or p_byte_length not between 1 and 5242880
       or p_media not in ('application/pdf','application/xml','text/xml','text/plain')
       or p_request_key != p_intent::text
       or p_expected_intent_revision is not null or p_reason is not null) then
    raise exception 'invalid stage contract' using errcode='22023';
  end if;
  if p_operation='verify' and (
       p_sha !~ '^[0-9a-f]{64}$' or p_byte_length is null
       or p_expected_intent_revision is null or p_expected_intent_revision < 1
       or p_document_version is not null or p_object_key is not null
       or p_media is not null or p_reason is not null) then
    raise exception 'invalid synthetic readback contract' using errcode='22023';
  end if;
  if p_operation='unavailable' and (
       p_reason not in ('missing','digest_mismatch')
       or p_expected_intent_revision is null or p_expected_intent_revision < 1
       or p_document_version is not null or p_object_key is not null
       or p_sha is not null or p_byte_length is not null or p_media is not null) then
    raise exception 'invalid unavailability contract' using errcode='22023';
  end if;

  -- Lock active membership before case; no client execute grant exists.
  select m.org_id, m.actions into v_org,v_actions
  from caseproof.organization_members as m
  where m.user_id=p_actor
    and m.org_id=(select c.org_id from caseproof.cases c where c.id=p_case)
    and m.active and 'case:read'=any(m.actions)
  for update of m;
  if v_org is null then
    raise exception 'source not found' using errcode='P0002';
  end if;
  if not ('finding:write'=any(v_actions)) then
    raise exception 'operation not permitted' using errcode='42501';
  end if;

  select * into v_case from caseproof.cases c
  where c.id=p_case and c.org_id=v_org for update;
  if not found then
    raise exception 'source not found' using errcode='P0002';
  end if;
  select * into v_intent
  from caseproof._s2_009b_vault_intents i
  where i.org_id=v_org and i.case_id=p_case and i.intent_id=p_intent
  for update;

  -- Canonical semantic digest: object key is intentionally NOT part of a
  -- stage retry fingerprint. Stable request intent ID binds original object key.
  v_fingerprint:=encode(sha256(convert_to(jsonb_build_object(
    'op',p_operation,'actor',p_actor,'case',p_case,'intent',p_intent,
    'source_version',p_document_version,'sha',p_sha,'bytes',p_byte_length,
    'media',p_media,'expected',p_expected_intent_revision,'reason',p_reason
  )::text,'UTF8')),'hex');
  v_operation:='s2_009b_vault_'||p_operation;

  select * into v_receipt from caseproof.idempotency_records r
  where r.org_id=v_org and r.case_id=p_case and r.operation=v_operation
    and r.idempotency_key=p_request_key;

  if found then
    if v_receipt.input_sha256_hex is distinct from v_fingerprint
       or v_intent.intent_id is null or v_intent.actor_user_id!=p_actor then
      raise exception 'request intent conflict' using errcode='23505';
    end if;
    begin
      v_existing_event := (v_receipt.response_reference::jsonb->>'audit')::uuid;
      v_existing_intent_revision :=
        (v_receipt.response_reference::jsonb->>'intent_revision')::bigint;
      v_existing_case_revision :=
        (v_receipt.response_reference::jsonb->>'case_revision')::bigint;
    exception when others then
      raise exception 'invalid stored receipt' using errcode='55000';
    end;
    if v_existing_event is null or v_existing_intent_revision is null
       or v_existing_case_revision is null
       or v_existing_intent_revision>v_intent.intent_revision
       or v_existing_case_revision>v_case.case_revision
       or not exists (
         select 1 from caseproof.audit_events a
         where a.org_id=v_org and a.case_id=p_case
           and a.id=v_existing_event and a.actor_user_id=p_actor
           and a.action=v_operation and a.input_sha256_hex=v_fingerprint
       ) or (p_operation!='stage' and not exists (
         select 1 from caseproof._s2_009b_availability_events e
         where e.org_id=v_org and e.case_id=p_case and e.intent_id=p_intent
           and e.intent_revision=v_existing_intent_revision
           and e.case_revision=v_existing_case_revision
           and e.audit_event_id=v_existing_event
       )) then
      raise exception 'stored receipt inconsistent with durable event' using errcode='55000';
    end if;
    return query select v_intent.state, v_intent.intent_revision,
        v_case.case_revision,v_existing_event,true;
    return;
  end if;

  if p_operation='stage' then
    if v_intent.intent_id is not null then
      raise exception 'same intent ID with different semantic request'
      using errcode='23505';
    end if;
    v_expected_object_prefix:=
      'org/'||replace(v_org::text,'-','')||'/case/'||
      replace(p_case::text,'-','')||'/sources/';
    if left(p_object_key,length(v_expected_object_prefix))
          !=v_expected_object_prefix
       or substring(p_object_key from length(v_expected_object_prefix)+1)
          !~ '^[0-9a-f]{32}$' then
      raise exception 'invalid randomized object key format' using errcode='22023';
    end if;
    select d.id into v_document
    from caseproof.document_versions v
    join caseproof.documents d on d.id=v.document_id
      and d.org_id=v.org_id
    where v.id=p_document_version and v.org_id=v_org
      and d.case_id=p_case and v.original_sha256_hex=p_sha
      and v.byte_length=p_byte_length and v.media_type=p_media;
    if v_document is null then
      raise exception 'wrong case or source version digest' using errcode='P0002';
    end if;
    v_next_intent:=1;
    v_state:='pending';
  else
    if v_intent.intent_id is null or v_intent.actor_user_id!=p_actor then
      raise exception 'source not found' using errcode='P0002';
    end if;
    if v_intent.intent_revision!=p_expected_intent_revision then
      raise exception 'stale intent version' using errcode='40001';
    end if;
    if p_operation='verify' then
      if v_intent.state!='pending'
         or p_sha is distinct from v_intent.sha256_hex
         or p_byte_length is distinct from v_intent.byte_length then
        raise exception 'unverified source version' using errcode='40001';
      end if;
      v_state:='verified';
    else
      if v_intent.state!='verified' then
        raise exception 'only verified sources may become unavailable'
        using errcode='40001';
      end if;
      v_state:='unavailable';
    end if;
    v_next_intent:=v_intent.intent_revision+1;
  end if;

  update caseproof.cases c
  set case_revision=c.case_revision+1,updated_at=now()
  where c.id=p_case and c.org_id=v_org
  returning c.case_revision into v_next_case;
  if v_next_case is null then
    raise exception 'missing locked case' using errcode='40001';
  end if;

  insert into caseproof.audit_events (
     org_id,case_id,actor_type,actor_user_id,action,
     event_schema_version,correlation_id,input_sha256_hex
  ) values (
     v_org,p_case,'human',p_actor,v_operation,'s2-009b-vault-v1',
     p_correlation,
     case when p_fault='audit' then 'invalid' else v_fingerprint end
  ) returning id into v_event;

  if p_operation='stage' then
    insert into caseproof._s2_009b_vault_intents(
      org_id,case_id,intent_id,actor_user_id,document_id,
      document_version_id,object_key,sha256_hex,byte_length,media_type,
      state,intent_revision,created_audit_id,last_audit_id
    ) values (
      v_org,p_case,p_intent,p_actor,v_document,p_document_version,p_object_key,
      p_sha,p_byte_length,p_media,'pending',1,v_event,v_event
    );
  else
    update caseproof._s2_009b_vault_intents i
    set state=v_state,intent_revision=v_next_intent,last_audit_id=v_event
    where i.org_id=v_org and i.case_id=p_case and i.intent_id=p_intent
      and i.intent_revision=p_expected_intent_revision;
    if not found then
      raise exception 'failed intent CAS' using errcode='40001';
    end if;
    insert into caseproof._s2_009b_availability_events (
      org_id,case_id,intent_id,intent_revision,status,reason,
      case_revision,audit_event_id
    ) values (
      v_org,p_case,p_intent,v_next_intent,v_state,
      case when p_operation='verify' then 'readback_verified' else p_reason end,
      v_next_case,
      case when p_fault='availability' then gen_random_uuid() else v_event end
    );
  end if;

  insert into caseproof.idempotency_records(
    org_id,case_id,operation,idempotency_key,input_sha256_hex,response_reference
  ) values (
    v_org,p_case,v_operation,p_request_key,
    case when p_fault='receipt' then 'invalid' else v_fingerprint end,
    jsonb_build_object('schema','s2-009b-vault-v1','audit',v_event,
      'intent_revision',v_next_intent,'case_revision',v_next_case)::text
  );
  return query select v_state,v_next_intent,v_next_case,v_event,false;
end;
$body$;

alter table caseproof._s2_009b_vault_intents enable row level security;
alter table caseproof._s2_009b_availability_events enable row level security;
revoke all on caseproof._s2_009b_vault_intents,
  caseproof._s2_009b_availability_events from public,anon,authenticated;
revoke execute on function caseproof._s2_009b_disposable_command(
  uuid,uuid,uuid,text,text,uuid,uuid,text,text,bigint,text,bigint,text,text
) from public,anon,authenticated;
revoke execute on function caseproof._s2_009b_immutable_availability()
from public,anon,authenticated;

do $deny$
begin
  if has_function_privilege(
    'authenticated',
    'caseproof._s2_009b_disposable_command(uuid,uuid,uuid,text,text,uuid,uuid,text,text,bigint,text,bigint,text,text)',
    'EXECUTE'
  ) then
    raise exception 'S2-009b fixture function exposed to authenticated clients';
  end if;
end $deny$;

commit;
