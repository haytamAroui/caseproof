-- Signed, read-only rediscovery of the immutable four-source development bundle.
create or replace function public.caseproof_dev_bundle_manifest(p_case uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid(); v_org uuid; v_manifest jsonb; v_sources jsonb;
begin
 if v_actor is null or p_case is null or coalesce(auth.jwt()->>'role','') <> 'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'matter unavailable' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
   and m.active and m.actions @> array['case:read','evidence:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=v_actor and g.active
   and g.permissions @> array['case:read','evidence:read']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 select op.response into v_manifest from caseproof._dev_journey_operations op
 where op.org_id=v_org and op.actor_id=v_actor and op.operation='bundle_register'
 and op.response->>'case_id'=p_case::text;
 if v_manifest is null or jsonb_array_length(v_manifest->'sources')<>4
 then raise exception 'bundle unavailable' using errcode='42501'; end if;
 select jsonb_agg(jsonb_build_object(
   'role',s.item->>'role','filename',d.source_label,'document_id',d.id,
   'version_id',dv.id,'version_number',dv.version_number,
   'sha256',dv.original_sha256_hex,'byte_length',dv.byte_length,'media_type',dv.media_type
 ) order by s.ordinality) into v_sources
 from jsonb_array_elements(v_manifest->'sources') with ordinality as s(item,ordinality)
 join caseproof.documents d on d.id=(s.item->>'document_id')::uuid and d.org_id=v_org and d.case_id=p_case
 join caseproof.document_versions dv on dv.id=(s.item->>'version_id')::uuid
 and dv.document_id=d.id and dv.org_id=v_org
 where d.source_label=s.item->>'filename'
 and dv.original_sha256_hex=s.item->>'sha256'
 and dv.media_type=s.item->>'media_type'
 and dv.byte_length=(s.item->>'byte_length')::bigint;
 if jsonb_array_length(coalesce(v_sources,'[]'::jsonb))<>4
 then raise exception 'bundle integrity mismatch' using errcode='42501'; end if;
 return jsonb_build_object('case_id',p_case,'sources',v_sources);
end $$;
revoke all on function public.caseproof_dev_bundle_manifest(uuid) from public,anon;
grant execute on function public.caseproof_dev_bundle_manifest(uuid) to authenticated;
