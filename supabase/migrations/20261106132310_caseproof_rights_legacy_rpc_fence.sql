-- PR2: transactional rights authorization for independently exposed legacy RPCs.
-- No direct PostgREST path may bypass rights when the private control is ON.
-- This migration retains historical read access and does not change the switch.
begin;

alter function public.caseproof_dev_live_review(
  uuid,uuid,text,text,uuid,integer,text,text,text
) set schema caseproof;
alter function caseproof.caseproof_dev_live_review(
  uuid,uuid,text,text,uuid,integer,text,text,text
) rename to _rights_legacy_live_review;
revoke all on function caseproof._rights_legacy_live_review(
  uuid,uuid,text,text,uuid,integer,text,text,text
) from public,anon,authenticated,service_role;

alter function public.caseproof_dev_correct_brief(
  uuid,uuid,text,integer,text,text,text,uuid
) set schema caseproof;
alter function caseproof.caseproof_dev_correct_brief(
  uuid,uuid,text,integer,text,text,text,uuid
) rename to _rights_legacy_correct_brief;
revoke all on function caseproof._rights_legacy_correct_brief(
  uuid,uuid,text,integer,text,text,text,uuid
) from public,anon,authenticated,service_role;

create function caseproof._rights_require_legacy_brief(
  p_case uuid,p_version uuid,p_action text
) returns void language plpgsql security definer set search_path='' as $$
declare
  v_enabled boolean;
  v_actor uuid:=auth.uid();
  v_org uuid; v_doc uuid; v_original uuid;
begin
  select enabled into v_enabled from caseproof._rights_enforcement_control
    where singleton=true;
  if v_enabled is null then
    raise exception 'rights control unavailable' using errcode='42501';
  end if;
  if v_enabled=false then return; end if;
  if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
    or p_case is null or p_version is null
    or p_action not in ('process','export') then
    raise exception 'rights unavailable' using errcode='42501';
  end if;
  -- The brief's version is NOT the stored original's version. Only the
  -- server-authored mapping may resolve the correct document-version scope.
  select b.org_id,b.document_id,b.document_version_id
  into v_org,v_doc,v_original
  from caseproof._m2_brief_versions b
  where b.case_id=p_case and b.version_id=p_version
    and b.document_role='own_draft';
  if v_org is null or v_doc is null or v_original is null then
    raise exception 'rights unavailable' using errcode='42501';
  end if;
  perform caseproof._rights_require_source(
    v_org,p_case,v_doc,v_original,p_action);
end $$;
revoke all on function caseproof._rights_require_legacy_brief(uuid,uuid,text)
from public,anon,authenticated,service_role;

create function public.caseproof_dev_live_review(
  p_case uuid,p_version uuid,p_action text,p_snapshot text default null,
  p_request uuid default null,p_expected integer default null,
  p_observation text default null,p_disposition text default null,
  p_rationale text default null
) returns jsonb language plpgsql security definer set search_path='' as $$
begin
  -- A 'state' request is a historical, signed read. Both 'check' and
  -- review-derived writes require permission to process the source.
  if p_action in ('check','review') then
    perform caseproof._rights_require_legacy_brief(p_case,p_version,'process');
  elsif p_action is distinct from 'state' then
    raise exception 'invalid signed review operation' using errcode='42501';
  end if;
  return caseproof._rights_legacy_live_review(
    p_case,p_version,p_action,p_snapshot,p_request,p_expected,
    p_observation,p_disposition,p_rationale);
end $$;
revoke all on function public.caseproof_dev_live_review(
  uuid,uuid,text,text,uuid,integer,text,text,text
) from public,anon,authenticated,service_role;
grant execute on function public.caseproof_dev_live_review(
  uuid,uuid,text,text,uuid,integer,text,text,text
) to authenticated;

create function public.caseproof_dev_correct_brief(
  p_case uuid,p_version uuid,p_snapshot text,p_expected_review integer,
  p_before text,p_after text,p_action text default 'preview',
  p_request uuid default null
) returns jsonb language plpgsql security definer set search_path='' as $$
begin
  if p_action not in ('preview','commit') then
    raise exception 'invalid signed correction operation' using errcode='42501';
  end if;
  perform caseproof._rights_require_legacy_brief(p_case,p_version,'process');
  return caseproof._rights_legacy_correct_brief(
    p_case,p_version,p_snapshot,p_expected_review,p_before,p_after,
    p_action,p_request);
end $$;
revoke all on function public.caseproof_dev_correct_brief(
  uuid,uuid,text,integer,text,text,text,uuid
) from public,anon,authenticated,service_role;
grant execute on function public.caseproof_dev_correct_brief(
  uuid,uuid,text,integer,text,text,text,uuid
) to authenticated;

commit;
