-- M1-B exact-live-foundation private schema DEV REVIEW PACKET.
-- DO NOT APPLY TO CASEPROOF-DEV UNTIL INDEPENDENT HUMAN SECURITY APPROVAL.
--
-- Source base: PIV-M1_default_private_rls_candidate.sql (PR #86).
-- This is the *atomic* candidate to install the trusted case-specific grant
-- inventory and switch legacy same-org SELECT policies in ONE transaction.
-- Do not add this file to supabase/migrations until approved; no production
-- browser endpoints, no matter assignment writers, no user creation.
--
-- Intentionally one-time, only for an EMPTY dev schema with the EXACT
-- canonical foundation policies. Unknown data/policy causes explicit abort.
begin;

do $m1_dev_foundation_gate$
declare
    bad boolean;
begin
    if not exists (
        select 1 from pg_namespace where nspname = 'caseproof'
    ) or to_regclass('caseproof.cases') is null
      or to_regclass('caseproof.organization_members') is null
      or to_regclass('caseproof.documents') is null
      or to_regclass('caseproof.document_versions') is null
      or to_regclass('caseproof.audit_events') is null
      or to_regclass('auth.users') is null then
        raise exception 'foundation migration missing or incomplete'
            using errcode='55000';
    end if;
    if to_regclass('caseproof._m1_matter_grants') is not null then
        raise exception 'matter grant table already exists; manual reconciliation required'
            using errcode='55000';
    end if;
    if exists (select 1 from auth.users)
      or exists (select 1 from caseproof.organizations)
      or exists (select 1 from caseproof.organization_members)
      or exists (select 1 from caseproof.cases)
      or exists (select 1 from caseproof.documents)
      or exists (select 1 from caseproof.document_versions) then
        raise exception 'nonempty dev project: refuse private migration without backfill'
            using errcode='55000';
    end if;
    if (
        select count(*) from pg_policies
        where schemaname='caseproof'
          and tablename in ('cases','documents','document_versions')
    ) <> 3 or exists (
        select 1 from pg_policies
        where schemaname='caseproof'
          and tablename in ('cases','documents','document_versions')
          and (
              (tablename='cases'
                and (policyname<>'tenant_case_read' or cmd<>'SELECT'))
              or (tablename='documents'
                and (policyname<>'tenant_document_read' or cmd<>'SELECT'))
              or (tablename='document_versions'
                and (policyname<>'tenant_document_version_read' or cmd<>'SELECT'))
          )
    ) then
        raise exception 'unexpected installed read policies; fail closed'
            using errcode='55000';
    end if;
    if (
        select count(*) from pg_policies
        where schemaname='caseproof'
          and tablename='organization_members'
          and policyname='own_active_membership_read'
          and cmd='SELECT'
    ) <> 1 then
        raise exception 'own-membership RLS baseline missing'
            using errcode='55000';
    end if;
end;
$m1_dev_foundation_gate$;

create table caseproof._m1_matter_grants (
    org_id uuid not null,
    case_id uuid not null,
    user_id uuid not null,
    role text not null check(role in ('viewer','reviewer')),
    permissions text[] not null default '{}'::text[]
      check (permissions <@ array[
        'case:read','coverage:read','evidence:read',
        'review:request','finding:write','evidence:upload',
        'evidence:index','exhibit:confirm','draft:check'
      ]::text[]),
    active boolean not null default true,
    revision bigint not null default 1 check(revision>=1),
    primary key(org_id,case_id,user_id),
    foreign key(org_id,case_id) references caseproof.cases(org_id,id),
    foreign key(org_id,user_id)
      references caseproof.organization_members(org_id,user_id)
);

-- All permissions must be granted through an independently approved,
-- actor-audited application transaction, not direct HTTP/user SQL. This
-- packet does NOT add provisioning/assignment/revocation writers.
alter table caseproof._m1_matter_grants enable row level security;
revoke all on caseproof._m1_matter_grants from public, anon, authenticated;

-- Frozen #86 policy switch, transacted with grant-table creation.

-- Own active case assignments are visible only to the authenticated principal.
-- A grant is NOT independently authority: it must belong to a current member.
alter table caseproof._m1_matter_grants enable row level security;
revoke all on caseproof._m1_matter_grants from public, anon, authenticated;
drop policy if exists m1_own_private_grant_read on caseproof._m1_matter_grants;
create policy m1_own_private_grant_read
on caseproof._m1_matter_grants for select to authenticated
using (
    active and user_id = (select auth.uid())
    and exists (
        select 1 from caseproof.organization_members as m
        where m.org_id = _m1_matter_grants.org_id
          and m.user_id = (select auth.uid()) and m.active
          and 'case:read' = any(m.actions)
    )
);
grant select on caseproof._m1_matter_grants to authenticated;

-- Replace, don't merely supplement, the old org-wide SELECT policies.
drop policy if exists tenant_case_read on caseproof.cases;
drop policy if exists tenant_document_read on caseproof.documents;
drop policy if exists tenant_document_version_read on caseproof.document_versions;
drop policy if exists m1_private_case_read on caseproof.cases;
drop policy if exists m1_private_document_read on caseproof.documents;
drop policy if exists m1_private_document_version_read on caseproof.document_versions;

create policy m1_private_case_read on caseproof.cases
for select to authenticated
using (
    (select auth.uid()) is not null
    and exists (
        select 1 from caseproof.organization_members as m
        join caseproof._m1_matter_grants as g
          on g.org_id = m.org_id and g.user_id = m.user_id
         and g.case_id = cases.id and g.active
        where m.org_id = cases.org_id
          and m.user_id = (select auth.uid()) and m.active
          and 'case:read' = any(m.actions)
          and 'case:read' = any(g.permissions)
    )
);

create policy m1_private_document_read on caseproof.documents
for select to authenticated
using (
    (select auth.uid()) is not null
    and exists (
        select 1 from caseproof.organization_members as m
        join caseproof._m1_matter_grants as g
          on g.org_id = m.org_id and g.user_id = m.user_id
         and g.case_id = documents.case_id and g.active
        where m.org_id = documents.org_id
          and m.user_id = (select auth.uid()) and m.active
          and 'case:read' = any(m.actions)
          and 'evidence:read' = any(m.actions)
          and 'case:read' = any(g.permissions)
          and 'evidence:read' = any(g.permissions)
    )
);

create policy m1_private_document_version_read on caseproof.document_versions
for select to authenticated
using (
    (select auth.uid()) is not null
    and exists (
        select 1 from caseproof.documents as d
        join caseproof.organization_members as m on m.org_id = d.org_id
        join caseproof._m1_matter_grants as g
          on g.org_id = d.org_id and g.case_id = d.case_id
         and g.user_id = m.user_id and g.active
        where d.org_id = document_versions.org_id
          and d.id = document_versions.document_id
          and m.user_id = (select auth.uid()) and m.active
          and 'case:read' = any(m.actions)
          and 'evidence:read' = any(m.actions)
          and 'case:read' = any(g.permissions)
          and 'evidence:read' = any(g.permissions)
    )
);

alter table caseproof.cases enable row level security;
alter table caseproof.documents enable row level security;
alter table caseproof.document_versions enable row level security;

-- PostgreSQL ORs permissive policies. A stray owner/legacy policy would
-- undermine this migration even if the new predicates are individually
-- correct. Abort atomically rather than leave a false private-security claim.
do $private_policy_gate$
begin
    if exists (
        select 1 from pg_policies
        where schemaname = 'caseproof'
          and (
              (tablename = 'cases' and policyname <> 'm1_private_case_read')
              or (tablename = 'documents'
                  and policyname <> 'm1_private_document_read')
              or (tablename = 'document_versions'
                  and policyname <> 'm1_private_document_version_read')
              or (tablename = '_m1_matter_grants'
                  and policyname <> 'm1_own_private_grant_read')
          )
          and cmd in ('SELECT', 'ALL')
    ) then
        raise exception 'unreviewed overlapping SELECT policy blocks private rollout'
          using errcode = '42501';
    end if;
end;
$private_policy_gate$;

-- Explicit read-only API role grants. No authoring, exhibits write, audit or
-- privileged evidence-kernel tables are exposed by this proposal.
revoke all on caseproof.cases,caseproof.documents,
  caseproof.document_versions from public,anon,authenticated;
grant select on caseproof.cases,caseproof.documents,
  caseproof.document_versions to authenticated;

-- Source version and assignment lookups need these indexes once approved.
create index if not exists m1_grants_active_actor_idx
  on caseproof._m1_matter_grants(user_id,org_id,case_id) where active;
create index if not exists m1_grants_active_case_idx
  on caseproof._m1_matter_grants(org_id,case_id,user_id) where active;

-- No authenticated grant on _m1_exhibit_heads, _m1_exhibit_events, M2 check
-- run/review tables, private Vault and audit events. All remain server-only.
commit;
