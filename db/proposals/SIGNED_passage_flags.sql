-- PROPOSAL ONLY. Append-only human-reported missed passages, not automatic findings.
begin;
create table if not exists caseproof._m3_passage_flags (
 id bigint generated always as identity primary key,
 org_id uuid not null, case_id uuid not null, request_id uuid not null,
 actor_id uuid not null, brief_version_id text not null,
 source_document_id uuid not null, source_version_id uuid not null,
 source_sha256 text not null check(source_sha256 ~ '^[0-9a-f]{64}$'),
 draft_passage text not null check(length(draft_passage) between 1 and 1200),
 source_passage text not null check(length(source_passage) between 1 and 1200),
 source_start integer not null check(source_start>=0),
 rationale text not null check(length(btrim(rationale)) between 1 and 2000),
 recorded_at timestamptz not null default now(),
 unique(org_id,case_id,request_id),
 foreign key(org_id,actor_id) references caseproof.organization_members(org_id,user_id)
);
create or replace function caseproof._m3_deny_flag_mutation() returns trigger
language plpgsql as $$ begin raise exception 'passage flags are append-only'; end $$;
drop trigger if exists _m3_flags_append_only on caseproof._m3_passage_flags;
create trigger _m3_flags_append_only before update or delete on caseproof._m3_passage_flags
 for each row execute function caseproof._m3_deny_flag_mutation();
alter table caseproof._m3_passage_flags enable row level security;
revoke all on caseproof._m3_passage_flags from public,anon,authenticated;
revoke execute on function caseproof._m3_deny_flag_mutation() from public,anon,authenticated;

create or replace function public.caseproof_signed_passage_flag(p_case uuid,p_request uuid,p_flag text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid(); v_org uuid; f jsonb; v_sha text; prior record;
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor and m.active
  and m.actions @> array['case:read','evidence:read','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=v_actor
  and g.active and g.role='reviewer'
  and g.permissions @> array['case:read','evidence:read','draft:check','review:request']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 if p_request is null or p_flag is null or octet_length(p_flag)>16000
 then return jsonb_build_object('ok',false,'error','invalid'); end if;
 begin
  f:=p_flag::jsonb;
  if jsonb_typeof(f)<>'object' or (select count(*)<>7 from jsonb_object_keys(f))
   or not f ?& array['brief_version_id','source_document_id','source_version_id','draft_passage','source_passage','source_start','rationale']
   or exists(select 1 from jsonb_each(f) e where e.key<>'source_start' and jsonb_typeof(e.value)<>'string')
   or jsonb_typeof(f->'source_start')<>'number'
   or length(f->>'brief_version_id') not between 1 and 128
   or length(f->>'draft_passage') not between 1 and 1200
   or length(f->>'source_passage') not between 1 and 1200
   or length(btrim(f->>'rationale')) not between 1 and 2000
   or (f->>'source_start')::integer<0
  then return jsonb_build_object('ok',false,'error','invalid'); end if;
  select dv.original_sha256_hex into v_sha from caseproof.documents d
  join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
  join lateral (select caseproof._signed_storage_source_binding(d.org_id,d.case_id,d.id,dv.id) as binding) custody on custody.binding is not null
  where d.org_id=v_org and d.case_id=p_case and d.id=(f->>'source_document_id')::uuid
   and dv.id=(f->>'source_version_id')::uuid;
  if v_sha is null then return jsonb_build_object('ok',false,'error','conflict'); end if;
  select * into prior from caseproof._m3_passage_flags where org_id=v_org and case_id=p_case and request_id=p_request;
  if found then
   if prior.actor_id=v_actor and prior.brief_version_id=f->>'brief_version_id'
    and prior.source_document_id=(f->>'source_document_id')::uuid and prior.source_version_id=(f->>'source_version_id')::uuid
    and prior.draft_passage=f->>'draft_passage' and prior.source_passage=f->>'source_passage'
    and prior.source_start=(f->>'source_start')::integer and prior.rationale=btrim(f->>'rationale')
   then return jsonb_build_object('ok',true,'replay',true); end if;
   return jsonb_build_object('ok',false,'error','conflict');
  end if;
  insert into caseproof._m3_passage_flags(org_id,case_id,request_id,actor_id,brief_version_id,
   source_document_id,source_version_id,source_sha256,draft_passage,source_passage,source_start,rationale)
  values(v_org,p_case,p_request,v_actor,f->>'brief_version_id',(f->>'source_document_id')::uuid,
   (f->>'source_version_id')::uuid,v_sha,f->>'draft_passage',f->>'source_passage',(f->>'source_start')::integer,btrim(f->>'rationale'));
 exception when invalid_text_representation or check_violation or not_null_violation then
  return jsonb_build_object('ok',false,'error','invalid');
 end;
 return jsonb_build_object('ok',true,'replay',false);
end $$;
revoke all on function public.caseproof_signed_passage_flag(uuid,uuid,text) from public,anon;
grant execute on function public.caseproof_signed_passage_flag(uuid,uuid,text) to authenticated;

create or replace function public.caseproof_signed_passage_flags(p_case uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid();v_org uuid;
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor and m.active
  and m.actions @> array['case:read','evidence:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=v_actor and g.active
  and g.permissions @> array['case:read','evidence:read']::text[] where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501';end if;
 return coalesce((select jsonb_agg(to_jsonb(f)-'org_id'-'case_id'-'request_id' order by f.id)
 from caseproof._m3_passage_flags f where f.org_id=v_org and f.case_id=p_case),'[]'::jsonb);
end $$;
revoke all on function public.caseproof_signed_passage_flags(uuid) from public,anon;
grant execute on function public.caseproof_signed_passage_flags(uuid) to authenticated;
commit;
