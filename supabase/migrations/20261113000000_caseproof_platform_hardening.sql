-- CaseProof platform hardening for the caseproof-dev environment.
--
-- SCOPE. This migration carries only work that is replayable on any
-- PostgreSQL instance: the forced-RLS invariant on the private schema, and
-- the fixed least-privilege application login role. Platform tuning that
-- depends on Supabase-managed objects or roles - a per-role log setting and
-- the ACL of the pg_stat_statements views - is NOT a schema migration and is
-- deliberately NOT applied here. It lives in
-- docs/security/DEV_ONLY_APPLIED_PLATFORM_HARDENING_20261112.sql, is applied
-- once to the managed project, and is evidenced in
-- docs/security/LIVE_PLATFORM_HARDENING_RECEIPT_2026-11-12.md. Keeping it
-- out of this chain is what makes the chain replayable on a plain
-- PostgreSQL 17 instance, where those objects and roles do not exist.
--
-- 1. FORCE ROW LEVEL SECURITY on every caseproof relation.
--    RLS was already enabled on all relations, but a table OWNER bypasses
--    RLS unless FORCE is set. Every caseproof relation is currently owned
--    by `postgres`, which holds BYPASSRLS, so this changes no live
--    behaviour today; it makes the invariant explicit and keeps it true if
--    a future migration creates a relation owned by a role that does not
--    hold BYPASSRLS.
--
-- 2. The fixed least-privilege application login role
--    `caseproof_m1_reader`.
--    The role is created here with NO password and is therefore unusable
--    for password authentication until the deployment owner provisions one
--    through a reviewed, secret-managed path. No credential is stored in
--    this repository. The grant set is exactly what the signed private
--    reader asserts at runtime in
--    apps/api/signed_private_matter_reader.py:
--      - USAGE on schema caseproof;
--      - SELECT on the five protected relations only
--        (cases, documents, document_versions, organization_members,
--         _m1_matter_grants);
--      - no INSERT/UPDATE/DELETE/TRUNCATE/TRIGGER/REFERENCES on any of
--        them, and no membership in a superuser or BYPASSRLS role;
--      - no ownership of any protected relation.
--    auth.uid() is executable through PUBLIC, so no extra auth grant is
--    required for the request-scoped subject binding.
--
-- Rollback statements are recorded with this migration in the deployment
-- receipt under docs/security/.

set search_path = '';

-- 1. Force RLS on every caseproof relation (owner can no longer bypass).
do $$
declare
    rel record;
begin
    for rel in
        select c.relname
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'caseproof'
          and c.relkind in ('r', 'p')
        order by c.relname
    loop
        execute format('alter table caseproof.%I force row level security', rel.relname);
    end loop;
end
$$;

-- 2. Fixed least-privilege application login role (no password here).
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'caseproof_m1_reader') then
        create role caseproof_m1_reader nologin;
    end if;
end
$$;

-- NOSUPERUSER / NOBYPASSRLS are the defaults for a newly created role and
-- are asserted below. They are not restated here because altering the
-- SUPERUSER attribute requires the SUPERUSER privilege, which the
-- migration role does not hold, and because restating them would grant
-- nothing.
alter role caseproof_m1_reader login;
alter role caseproof_m1_reader nocreatedb nocreaterole noreplication noinherit;

revoke all on all tables in schema caseproof from caseproof_m1_reader;
revoke all on schema caseproof from caseproof_m1_reader;
grant usage on schema caseproof to caseproof_m1_reader;

grant select on
    caseproof.cases,
    caseproof.documents,
    caseproof.document_versions,
    caseproof.organization_members,
    caseproof._m1_matter_grants
to caseproof_m1_reader;

-- Fail closed on every environment-independent invariant.
do $$
declare
    unprotected integer;
    reader_write_privileges integer;
    reader_owner_count integer;
    reader_privileged_membership integer;
    reader_function_execute integer;
begin
    select count(*) into unprotected
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'caseproof'
      and c.relkind in ('r', 'p')
      and (not c.relrowsecurity or not c.relforcerowsecurity);
    if unprotected <> 0 then
        raise exception 'caseproof relations without forced RLS: %', unprotected
            using errcode = '42501';
    end if;

    select count(*) into reader_write_privileges
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'caseproof'
      and c.relname in ('cases', 'documents', 'document_versions',
                         'organization_members', '_m1_matter_grants')
      and has_table_privilege('caseproof_m1_reader', c.oid,
          'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES');
    if reader_write_privileges <> 0 then
        raise exception 'reader role holds write privileges on protected relations'
            using errcode = '42501';
    end if;

    select count(*) into reader_owner_count
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'caseproof'
      and c.relname in ('cases', 'documents', 'document_versions',
                         'organization_members', '_m1_matter_grants')
      and pg_get_userbyid(c.relowner) = 'caseproof_m1_reader';
    if reader_owner_count <> 0 then
        raise exception 'reader role owns a protected relation'
            using errcode = '42501';
    end if;

    select count(*) into reader_privileged_membership
    from pg_roles r
    where (r.rolsuper or r.rolbypassrls)
      and r.rolname <> 'caseproof_m1_reader'
      and pg_has_role('caseproof_m1_reader', r.oid, 'MEMBER');
    if reader_privileged_membership <> 0 then
        raise exception 'reader role inherits a privileged role'
            using errcode = '42501';
    end if;

    if not exists (select 1 from pg_roles
                   where rolname = 'caseproof_m1_reader'
                     and rolsuper = false
                     and rolbypassrls = false
                     and rolcanlogin = true) then
        raise exception 'reader role attributes are not least-privilege'
            using errcode = '42501';
    end if;

    -- A new role inherits EXECUTE on functions through PUBLIC. The reader
    -- role must not be able to run the schema's SECURITY DEFINER helpers
    -- directly. The residual is reported rather than hidden: revoking
    -- EXECUTE from PUBLIC would change behaviour for every other caller of
    -- those functions and is a separate, reviewed decision.
    select count(*) into reader_function_execute
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'caseproof'
      and has_function_privilege('caseproof_m1_reader', p.oid, 'EXECUTE');
    if reader_function_execute > 0 then
        raise notice
            'reader role can execute % caseproof functions through PUBLIC; reviewed separately',
            reader_function_execute;
    end if;
end
$$;
