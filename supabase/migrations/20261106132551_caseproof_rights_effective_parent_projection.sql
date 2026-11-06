-- PR2: signed rights projection must reflect CURRENT parent restrictions.
-- Prevent a copied child ALLOW from authorizing an immediate export after
-- the latest parent policy becomes DENY. Never expose firm auth text.
begin;
alter function public.caseproof_rights_current(uuid,uuid,uuid)
  rename to _rights_current_raw;
revoke all on function public._rights_current_raw(uuid,uuid,uuid)
  from public,anon,authenticated,service_role;

create function public.caseproof_rights_current(
  p_case uuid,p_document uuid,p_version uuid
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  v_policy jsonb;
  v_parent_policy jsonb;
  v_parent uuid;
  v_current uuid:=p_version;
  v_depth integer:=0;
  v_versions jsonb:='[]'::jsonb;
begin
  -- The original projection performs fresh signed membership, grant,
  -- tenant and source-ancestry validation. This wrapper may only RESTRICT.
  v_policy := public._rights_current_raw(p_case,p_document,p_version);
  if v_policy->>'policy_status' is distinct from 'present' then
    return v_policy;
  end if;
  loop
    select r.parent_version_id into v_parent
    from caseproof.dossier_draft_revisions r
    join caseproof.documents d on d.org_id=r.org_id
      and d.id=r.document_id and d.case_id=r.case_id
    where r.case_id=p_case and r.document_id=p_document
      and r.version_id=v_current;
    if not found then
      return v_policy || jsonb_build_object(
        'effective_parent_policy_versions',v_versions);
    end if;
    if v_parent is null or v_parent=v_current or v_depth>=32 then
      raise exception 'invalid derivative rights ancestry' using errcode='42501';
    end if;
    v_parent_policy:=public._rights_current_raw(p_case,p_document,v_parent);
    if v_parent_policy->>'policy_status' is distinct from 'present'
      or v_parent_policy->>'origin' is distinct from v_policy->>'origin'
      or v_parent_policy->>'classification' is distinct from v_policy->>'classification' then
      -- Parent UNKNOWN or invalid ancestry cannot be escalated by a copied
      -- child policy, even when the child's flags were explicitly true.
      return jsonb_build_object('policy_status','missing');
    end if;
    v_policy := v_policy || jsonb_build_object(
      'process',
      (v_policy->>'process')::boolean and (v_parent_policy->>'process')::boolean,
      'indexForSearch',
      (v_policy->>'indexForSearch')::boolean
        and (v_parent_policy->>'indexForSearch')::boolean,
      'useAcrossMatters',
      (v_policy->>'useAcrossMatters')::boolean
        and (v_parent_policy->>'useAcrossMatters')::boolean,
      'export',
      (v_policy->>'export')::boolean and (v_parent_policy->>'export')::boolean,
      'authorization_reference_present',
      (v_policy->>'authorization_reference_present')::boolean
        and (v_parent_policy->>'authorization_reference_present')::boolean
    );
    v_versions:=v_versions || jsonb_build_array(jsonb_build_object(
      'version_id',v_parent,'policy_version',v_parent_policy->'policy_version'
    ));
    v_current:=v_parent;
    v_depth:=v_depth+1;
  end loop;
end $$;
revoke all on function public.caseproof_rights_current(uuid,uuid,uuid)
from public,anon,authenticated,service_role;
grant execute on function public.caseproof_rights_current(uuid,uuid,uuid)
to authenticated;
commit;
