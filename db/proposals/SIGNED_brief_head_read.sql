-- Proposal (not applied): signed brief-head read for the workbench publish
-- flow. Returns the current working-brief head (revision + version id) for
-- one case and role, so the publish adapter can compute its expected
-- revision. Read-only, same masking discipline as
-- caseproof_signed_exhibit_register: the caller must be a signed
-- authenticated member with the draft:check matter grant; any authorization
-- or existence gap raises the same masked 'matter unavailable' error, never
-- a distinguishable denial. The working brief id is recomputed in SQL from
-- the case identity and role (mirrors caseproof_signed_publish_uploaded), so
-- the caller cannot enumerate other briefs' heads. A missing head returns
-- revision 0 with a null version id: the first publication expects 0.
create or replace function public.caseproof_signed_brief_head(
 p_case uuid, p_role text
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid;
 v_head caseproof._m2_brief_heads%rowtype;
 v_h text; v_raw bytea; v_working uuid;
begin
 if p_case is null or p_role not in ('own_draft','opponent_brief')
 or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;

 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','draft:check']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 v_h:=encode(sha256(convert_to('caseproof-working-brief:'||p_role||':'||p_case::text,'UTF8')),'hex');
 v_raw:=decode(substring(v_h from 1 for 32),'hex');
 v_raw:=set_byte(v_raw,6,(get_byte(v_raw,6)&15)|64);
 v_raw:=set_byte(v_raw,8,(get_byte(v_raw,8)&63)|128);
 v_working:=encode(v_raw,'hex')::uuid;

 select h.* into v_head from caseproof._m2_brief_heads h
 where h.org_id=v_org and h.case_id=p_case and h.brief_id=v_working;
 return jsonb_build_object(
   'ok',true,
   'brief_id',v_working,
   'revision',coalesce(v_head.revision,0),
   'version_id',v_head.version_id);
end $$;
revoke all on function public.caseproof_signed_brief_head(uuid,text) from public,anon;
grant execute on function public.caseproof_signed_brief_head(uuid,text) to authenticated;
