-- Proposal (not applied): signed check-bundle read for the workbench check
-- flow. Returns every SQL-ownable row the check port needs in ONE masked
-- call: member+grant access with case revision, the exhibit register head,
-- the pinned brief version with its references and assertions, and the
-- declared confirmed source universe (version metadata, verified-intent
-- presence, trusted-registry representation). The adapter derives all
-- digests from the returned content and composes verified-byte previews
-- itself; this RPC trusts no stored digest column. Read-only. Masking:
-- every authorization, existence or bound failure raises the same
-- 'matter unavailable' 42501, so the endpoint is no existence oracle.
create or replace function public.caseproof_signed_check_bundle(
 p_case uuid, p_brief_version uuid
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_case_rev bigint;
 v_register jsonb; v_register_rev bigint;
 v_version caseproof._m2_brief_versions%rowtype;
 v_refs jsonb; v_asserts jsonb; v_sources jsonb;
begin
 if p_case is null or p_brief_version is null
 or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;

 select c.org_id,c.case_revision into v_org,v_case_rev from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','draft:check']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 select v.* into v_version from caseproof._m2_brief_versions v
 where v.org_id=v_org and v.case_id=p_case and v.version_id=p_brief_version;
 if v_version.version_id is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 select e.payload,e.revision into v_register,v_register_rev
 from caseproof._m1_exhibit_heads e where e.org_id=v_org and e.case_id=p_case;

 select coalesce(jsonb_agg(jsonb_build_object(
   'reference_id',r.reference_id,'reference_order',r.reference_order,
   'exhibit_label',r.exhibit_label,'exact_quote',r.exact_quote,'pdf_page',r.pdf_page)
   order by r.reference_order),'[]'::jsonb) into v_refs
 from caseproof._m2_brief_references r
 where r.org_id=v_org and r.case_id=p_case and r.brief_id=v_version.brief_id
   and r.version_id=p_brief_version;
 select coalesce(jsonb_agg(jsonb_build_object(
   'claim_id',a.claim_id,'claim_order',a.claim_order,'reference_id',a.reference_id,
   'text_start',a.text_start,'text_end',a.text_end,'assertion_text',a.assertion_text,
   'kind',a.kind,'fact_role',a.fact_role,'language',a.language,
   'source_language',a.source_language) order by a.claim_order),'[]'::jsonb) into v_asserts
 from caseproof._m2_brief_assertions a
 where a.org_id=v_org and a.case_id=p_case and a.brief_id=v_version.brief_id
   and a.version_id=p_brief_version;

 -- declared confirmed source universe, bounded to 32 like the check port
 with declared as (
   select distinct (p->>'source_id')::uuid as source_id,(p->>'version_id')::uuid as version_id
   from jsonb_array_elements(coalesce(v_register->'entries','[]'::jsonb)) e,
        jsonb_array_elements(coalesce(e->'pages','[]'::jsonb)) p
   where jsonb_typeof(e->'confirmed')='boolean' and (e->>'confirmed')::boolean
 )
 select jsonb_agg(jsonb_build_object(
   'document_id',d.id,'version_id',dv.id,
   'original_sha256_hex',dv.original_sha256_hex,'byte_length',dv.byte_length,
   'media_type',dv.media_type,
   'intent_verified',exists(
     select 1 from caseproof._s2_009b_vault_intents i
     where i.org_id=v_org and i.case_id=p_case and i.document_id=d.id
       and i.document_version_id=dv.id and i.sha256_hex=dv.original_sha256_hex
       and i.state='verified'),
   'representation',s.representation,'representation_sha',s.representation_sha)
   order by d.id,dv.id) into v_sources
 from declared t
 join caseproof.documents d on d.org_id=v_org and d.id=t.source_id and d.case_id=p_case
 join caseproof.document_versions dv on dv.org_id=v_org and dv.document_id=d.id and dv.id=t.version_id
 left join caseproof._dev_journey_sources s on s.org_id=v_org and s.case_id=p_case
   and s.version_id=dv.id;
 if (select count(*) from (
   select distinct (p->>'source_id')::uuid,(p->>'version_id')::uuid
   from jsonb_array_elements(coalesce(v_register->'entries','[]'::jsonb)) e,
        jsonb_array_elements(coalesce(e->'pages','[]'::jsonb)) p
   where jsonb_typeof(e->'confirmed')='boolean' and (e->>'confirmed')::boolean) u) > 32
 then raise exception 'matter unavailable' using errcode='42501'; end if;

 return jsonb_build_object(
   'ok',true,
   'case_revision',v_case_rev,
   'register_revision',v_register_rev,
   'register',v_register,
   'brief',jsonb_build_object(
     'brief_id',v_version.brief_id,'version_id',v_version.version_id,
     'revision',v_version.revision,'parent_version_id',v_version.parent_version_id,
     'document_id',v_version.document_id,'document_version_id',v_version.document_version_id,
     'vault_intent_id',v_version.vault_intent_id,'original_sha256',v_version.original_sha256,
     'representation_sha256',v_version.representation_sha256,'parser_id',v_version.parser_id,
     'representation',v_version.representation,'document_role',v_version.document_role,
     'graph_sha256',v_version.graph_sha256,'case_revision',v_version.case_revision,
     'exhibit_revision',v_version.exhibit_revision,'actor_id',v_version.actor_id,
     'created_at',v_version.created_at),
   'references',v_refs,
   'assertions',v_asserts,
   'sources',coalesce(v_sources,'[]'::jsonb));
end $$;
revoke all on function public.caseproof_signed_check_bundle(uuid,uuid) from public,anon;
grant execute on function public.caseproof_signed_check_bundle(uuid,uuid) to authenticated;
