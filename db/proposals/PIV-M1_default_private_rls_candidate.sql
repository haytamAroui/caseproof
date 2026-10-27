-- M1-B default-private matter RLS rollout CANDIDATE.
-- APPLY ONLY AFTER ADR-0017 SECURITY APPROVAL. Do NOT run on live caseproof-dev.
-- Requires tenant foundation and reviewed M1 grant proposal; CI runs locally.
-- Old installed org-wide read policies are intentionally removed: doing only
-- additive policies would OR the permissive organization-wide predicates!
-- No HTTP-input actor ID, SECURITY DEFINER, privileged RPC or public write.
begin;

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
