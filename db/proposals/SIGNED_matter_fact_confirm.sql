-- Proposal (not applied): lawyer fact confirmation bound to actor, source and version.
-- Append-only per matter. The actor is the verified caller (auth.uid()), never
-- a client field. The source is a document version of THIS matter whose
-- original is custody-verified; its sha256 is read server-side, not trusted
-- from the client. Confirmation records that the signed session user entered
-- the value against that source version. It is NOT proof that the fact is true,
-- NOT a legal conclusion, and the lawyer's own judgement stays theirs.
begin;
create table if not exists caseproof._m3_matter_facts (
  id bigint generated always as identity primary key,
  org_id uuid not null, case_id uuid not null,
  fact_name text not null check(fact_name ~ '^[a-z][a-z0-9_]{0,63}$'),
  fact_value jsonb not null
    check(jsonb_typeof(fact_value) in ('boolean','number','string')
          and octet_length(fact_value::text)<=512),
  confirmed boolean not null,
  source_document_id uuid not null, source_version_id uuid not null,
  source_sha256 text not null check(source_sha256 ~ '^[0-9a-f]{64}$'),
  locator text not null check(length(btrim(locator)) between 1 and 200),
  actor_id uuid not null, request_id uuid not null,
  recorded_at timestamptz not null default now(),
  unique(org_id,case_id,request_id),
  foreign key(org_id,actor_id) references caseproof.organization_members(org_id,user_id)
);
create or replace function caseproof._m3_deny_fact_mutation() returns trigger
language plpgsql as $$ begin raise exception 'matter facts are append-only'; end $$;
drop trigger if exists _m3_matter_facts_append_only on caseproof._m3_matter_facts;
create trigger _m3_matter_facts_append_only before update or delete
  on caseproof._m3_matter_facts for each row execute function caseproof._m3_deny_fact_mutation();
alter table caseproof._m3_matter_facts enable row level security;
revoke all on caseproof._m3_matter_facts from public,anon,authenticated;
revoke execute on function caseproof._m3_deny_fact_mutation() from public,anon,authenticated;

create or replace function public.caseproof_signed_fact_confirm(
 p_case uuid, p_request uuid, p_fact text
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_f jsonb; v_sha text; v_prev record;
 v_doc uuid; v_ver uuid;
begin
 if p_case is null or p_request is null or p_fact is null or v_actor is null
 or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
   and m.active and m.actions @> array['case:read','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=v_actor and g.active and g.role='reviewer'
   and g.permissions @> array['case:read','review:request']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 if octet_length(p_fact) not between 2 and 2048 or p_fact ~ '[\x00-\x1f]'
 then return jsonb_build_object('ok',false,'error','invalid'); end if;
 begin
   v_f:=p_fact::jsonb;
   if jsonb_typeof(v_f)<>'object'
   or (select count(*)<>6 or bool_and(k not in
        ('name','value','confirmed','source_document_id','source_version_id','locator'))
       from jsonb_object_keys(v_f) k)
   or jsonb_typeof(v_f->'name')<>'string' or (v_f->>'name') !~ '^[a-z][a-z0-9_]{0,63}$'
   or jsonb_typeof(v_f->'value') not in ('boolean','number','string')
   or jsonb_typeof(v_f->'confirmed')<>'boolean'
   or jsonb_typeof(v_f->'locator')<>'string'
   or length(btrim(v_f->>'locator')) not between 1 and 200
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
   v_doc:=(v_f->>'source_document_id')::uuid; v_ver:=(v_f->>'source_version_id')::uuid;
 exception when others then
   return jsonb_build_object('ok',false,'error','invalid');
 end;
 select dv.original_sha256_hex into v_sha from caseproof.documents d
 join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
 join lateral (select caseproof._signed_storage_source_binding(d.org_id,d.case_id,d.id,dv.id) as binding) custody on custody.binding is not null
 where d.org_id=v_org and d.case_id=p_case and d.id=v_doc and dv.id=v_ver;
 if v_sha is null then return jsonb_build_object('ok',false,'error','conflict'); end if;
 select * into v_prev from caseproof._m3_matter_facts
  where org_id=v_org and case_id=p_case and request_id=p_request;
 if found then
   if v_prev.actor_id=v_actor and v_prev.fact_name=v_f->>'name'
      and v_prev.fact_value=v_f->'value' and v_prev.confirmed=(v_f->>'confirmed')::boolean
      and v_prev.source_version_id=v_ver and v_prev.locator=btrim(v_f->>'locator')
   then return jsonb_build_object('ok',true,'replay',true,'id',v_prev.id); end if;
   return jsonb_build_object('ok',false,'error','conflict');
 end if;
 insert into caseproof._m3_matter_facts(org_id,case_id,fact_name,fact_value,confirmed,
   source_document_id,source_version_id,source_sha256,locator,actor_id,request_id)
 values(v_org,p_case,v_f->>'name',v_f->'value',(v_f->>'confirmed')::boolean,
   v_doc,v_ver,v_sha,btrim(v_f->>'locator'),v_actor,p_request);
 return jsonb_build_object('ok',true,'replay',false);
end $$;
revoke all on function public.caseproof_signed_fact_confirm(uuid,uuid,text) from public,anon;
grant execute on function public.caseproof_signed_fact_confirm(uuid,uuid,text) to authenticated;

-- Latest record per fact name (the history stays in the table; later entries supersede).
create or replace function public.caseproof_signed_fact_list(p_case uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid(); v_org uuid;
begin
 if p_case is null or v_actor is null
 or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
   and m.active and m.actions @> array['case:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=v_actor and g.active and g.permissions @> array['case:read']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 return coalesce((select jsonb_agg(jsonb_build_object(
   'name',f.fact_name,'value',f.fact_value,'confirmed',f.confirmed,
   'source_document_id',f.source_document_id,'source_version_id',f.source_version_id,
   'source_sha256',f.source_sha256,'locator',f.locator,'actor_id',f.actor_id,
   'recorded_at',f.recorded_at) order by f.fact_name)
  from (select distinct on (fact_name) * from caseproof._m3_matter_facts
        where org_id=v_org and case_id=p_case order by fact_name,id desc) f),'[]'::jsonb);
end $$;
revoke all on function public.caseproof_signed_fact_list(uuid) from public,anon;
grant execute on function public.caseproof_signed_fact_list(uuid) to authenticated;
commit;
