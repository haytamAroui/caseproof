-- DEV-ONLY ephemeral fixture issuer for protected CaseProof GitHub Actions.
-- Not production infrastructure. All RPCs callable ONLY by service_role.
-- Service role already holds admin authority; user JWTs perform real Storage I/O.
-- Preflight refuses to run outside the pinned empty dedicated development project.
do $dev_preflight$
begin
  if (select count(*) from storage.buckets where id='caseproof-originals-dev' and not public) <> 1
     or (select count(*) from supabase_migrations.schema_migrations
         where version in ('20261027160745','20261027202734','20261027204343')) <> 3
     or (select count(*) from caseproof.cases) <> 0
     or to_regclass('caseproof._dev_ci_fixture') is not null
  then
    raise exception 'expected empty isolated CaseProof-dev with reviewed private RLS'
      using errcode='55000';
  end if;
end
$dev_preflight$;

create table caseproof._dev_ci_fixture (
  run_id uuid primary key,
  owner_id uuid not null references auth.users(id),
  guest_id uuid not null references auth.users(id),
  foreign_id uuid not null references auth.users(id),
  org_id uuid not null unique,
  foreign_org_id uuid not null unique,
  case_id uuid not null unique,
  document_id uuid not null unique,
  version_id uuid not null unique,
  original_sha256 text not null check (original_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  constraint distinct_signed_actors check (owner_id<>guest_id and owner_id<>foreign_id and guest_id<>foreign_id)
);
alter table caseproof._dev_ci_fixture enable row level security;
revoke all on caseproof._dev_ci_fixture from public, anon, authenticated;

create function public.caseproof_dev_fixture_begin(
  p_run_id uuid, p_owner uuid, p_guest uuid, p_foreign uuid,
  p_sha text, p_size bigint
) returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  v_org uuid := gen_random_uuid();
  v_foreign_org uuid := gen_random_uuid();
  v_case uuid := gen_random_uuid();
  v_doc uuid := gen_random_uuid();
  v_version uuid := gen_random_uuid();
begin
  if p_run_id is null or p_owner is null or p_guest is null
    or p_foreign is null or p_owner=p_guest or p_owner=p_foreign or p_guest=p_foreign
    or p_sha !~ '^[0-9a-f]{64}$' or p_size<1 or p_size>20971520 then
    raise exception 'unacceptable synthetic CI fixture' using errcode='42501';
  end if;
  if exists(select 1 from caseproof._dev_ci_fixture)
    or exists(select 1 from caseproof.cases)
    or exists(select 1 from storage.objects where bucket_id='caseproof-originals-dev')
  then
    raise exception 'dev fixture or customer data exists; refuse to seed' using errcode='42501';
  end if;
  if (select count(*) from auth.users
      where id in (p_owner,p_guest,p_foreign)
        and email like 'caseproof-ci-%@example.com'
        and email_confirmed_at is not null) <> 3
  then
    raise exception 'three actual confirmed reserved GoTrue users required'
      using errcode='42501';
  end if;
  insert into caseproof.organizations(id,display_name)
    values (v_org,'CaseProof CI synthetic - disposable'),
           (v_foreign_org,'CaseProof CI foreign synthetic - disposable');
  insert into caseproof.organization_members(org_id,user_id,actions)
    values(v_org,p_owner,array['case:read','evidence:read','review:request','finding:write']::text[]),
          (v_org,p_guest,array['case:read','evidence:read']::text[]),
          (v_foreign_org,p_foreign,array['case:read','evidence:read']::text[]);
  insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
    values(v_case,v_org,p_owner,'caseproof-ci-dev-fixture-v1');
  insert into caseproof.documents(id,org_id,case_id,source_label)
    values(v_doc,v_org,v_case,'CI synthetic original - never real client data');
  insert into caseproof.document_versions
    (id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type)
    values(v_version,v_org,v_doc,1,p_sha,p_size,'text/plain');
  insert into caseproof._m1_matter_grants
    (org_id,case_id,user_id,role,permissions)
    values(v_org,v_case,p_owner,'reviewer',
      array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]);
  insert into caseproof._dev_ci_fixture
    (run_id,owner_id,guest_id,foreign_id,org_id,foreign_org_id,case_id,
     document_id,version_id,original_sha256)
    values(p_run_id,p_owner,p_guest,p_foreign,v_org,v_foreign_org,v_case,
      v_doc,v_version,p_sha);
  return jsonb_build_object('org_id',v_org,'case_id',v_case,
    'document_id',v_doc,'version_id',v_version,'sha256_hex',p_sha);
end;
$$;

create function public.caseproof_dev_fixture_revoke(
  p_run_id uuid, p_owner uuid
) returns boolean
language plpgsql security definer set search_path = ''
as $$
declare v caseproof._dev_ci_fixture%rowtype;
begin
  select * into v from caseproof._dev_ci_fixture
    where run_id=p_run_id and owner_id=p_owner for update;
  if not found then
    raise exception 'unknown dev fixture' using errcode='42501';
  end if;
  update caseproof._m1_matter_grants
    set active=false,revision=revision+1
    where org_id=v.org_id and case_id=v.case_id and user_id=v.owner_id;
  if not found then
    raise exception 'expected owner grant missing' using errcode='42501';
  end if;
  return true;
end;
$$;

-- Run only after DELETE through Supabase Storage API, never remove objects via SQL.
-- Reverses only exact scoped M1 fixtures; does NOT touch M2 immutable journals.
create function public.caseproof_dev_fixture_cleanup(
  p_run_id uuid, p_owner uuid
) returns boolean
language plpgsql security definer set search_path = ''
as $$
declare v caseproof._dev_ci_fixture%rowtype;
begin
  select * into v from caseproof._dev_ci_fixture
    where run_id=p_run_id and owner_id=p_owner for update;
  if not found then
    return false;
  end if;
  if exists(select 1 from storage.objects
     where bucket_id='caseproof-originals-dev'
       and name=concat_ws('/',v.org_id,v.case_id,v.document_id,v.version_id,v.original_sha256))
  then
    raise exception 'remove original through Storage API before DB cleanup'
      using errcode='55000';
  end if;
  delete from caseproof._m1_matter_grants
    where org_id=v.org_id and case_id=v.case_id;
  delete from caseproof.document_versions
    where org_id=v.org_id and document_id=v.document_id;
  delete from caseproof.documents
    where org_id=v.org_id and id=v.document_id;
  delete from caseproof.cases
    where org_id=v.org_id and id=v.case_id;
  delete from caseproof.organization_members
    where org_id in (v.org_id,v.foreign_org_id)
    and user_id in (v.owner_id,v.guest_id,v.foreign_id);
  delete from caseproof._dev_ci_fixture
    where run_id=p_run_id and owner_id=p_owner;
  delete from caseproof.organizations where id in (v.org_id,v.foreign_org_id);
  return true;
end;
$$;

revoke all on function public.caseproof_dev_fixture_begin(uuid,uuid,uuid,uuid,text,bigint) from public,anon,authenticated;
revoke all on function public.caseproof_dev_fixture_revoke(uuid,uuid) from public,anon,authenticated;
revoke all on function public.caseproof_dev_fixture_cleanup(uuid,uuid) from public,anon,authenticated;
grant execute on function public.caseproof_dev_fixture_begin(uuid,uuid,uuid,uuid,text,bigint) to service_role;
grant execute on function public.caseproof_dev_fixture_revoke(uuid,uuid) to service_role;
grant execute on function public.caseproof_dev_fixture_cleanup(uuid,uuid) to service_role;
