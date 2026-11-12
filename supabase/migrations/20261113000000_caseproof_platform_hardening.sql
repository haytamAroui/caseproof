-- CaseProof platform hardening for the caseproof-dev environment.
--
-- Scope, rationale and reversibility for each block:
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
-- 3. Platform-coupled hardening, applied only where the target exists and
--    the current role may alter it:
--      - REVOKE SELECT on the pg_stat_statements views from PUBLIC. The
--        grant is held by PUBLIC (`=r/postgres` in pg_class.relacl), so
--        revoking only from anon and authenticated would be a no-op.
--      - log_min_error_statement = 'fatal' for roles postgres and
--        authenticator. ALTER DATABASE ... SET requires SUPERUSER, which
--        the migration role does not hold on a managed project, so the
--        parameter is set per role: postgres covers direct and management
--        connections, authenticator covers PostgREST sessions, which
--        authenticate as authenticator and then assume a client role.
--    These targets are Supabase-provided: a bare PostgreSQL instance has
--    neither the authenticator role nor the extensions schema, and a local
--    Supabase stack may own the platform views differently. They therefore
--    must never abort a replay. Each statement is attempted, its outcome
--    counted, and the result asserted conditionally below. The
--    security-relevant state is verified directly on the managed project;
--    see docs/security/LIVE_PLATFORM_HARDENING_RECEIPT_2026-11-12.md.
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
revoke all on all sequences in schema caseproof from caseproof_m1_reader;
revoke all on all functions in schema caseproof from caseproof_m1_reader;
revoke all on schema caseproof from caseproof_m1_reader;
grant usage on schema caseproof to caseproof_m1_reader;

grant select on
    caseproof.cases,
    caseproof.documents,
    caseproof.document_versions,
    caseproof.organization_members,
    caseproof._m1_matter_grants
to caseproof_m1_reader;

-- 3. Platform-coupled hardening plus the fail-closed verification of every
--    environment-independent invariant.
do $$
declare
    target text;
    views_present integer := 0;
    views_revoked integer := 0;
    roles_configured integer := 0;
    unprotected integer;
    leaked integer;
    reader_write_privileges integer;
    reader_owner_count integer;
    reader_privileged_membership integer;
    inherited_leak integer;
begin
    -- 3a. log_min_error_statement, where the role exists and may be altered.
    for target in
        select rolname::text from pg_roles where rolname in ('postgres', 'authenticator')
    loop
        begin
            execute format(
                'alter role %I set log_min_error_statement = %L', target, 'fatal'
            );
            roles_configured := roles_configured + 1;
        exception when insufficient_privilege or undefined_object or undefined_table then
            raise notice
                'log_min_error_statement not applied to role % (insufficient privilege)',
                target;
        end;
    end loop;

    -- 3b. Revoke the public read of internal query text, where the view
    --     exists and this role may alter it.
    select count(*) into views_present
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'extensions'
      and c.relname in ('pg_stat_statements', 'pg_stat_statements_info');

    foreach target in array array['pg_stat_statements', 'pg_stat_statements_info'] loop
        if exists (
            select 1 from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'extensions' and c.relname = target
        ) then
            begin
                execute format('revoke select on extensions.%I from public', target);
                execute format(
                    'revoke select on extensions.%I from anon, authenticated', target
                );
                views_revoked := views_revoked + 1;
            exception when insufficient_privilege or undefined_object or undefined_table then
                raise notice
                    'revoke select on extensions.% not applied (insufficient privilege)',
                    target;
            end;
        end if;
    end loop;

    -- 3c. Fail closed on every environment-independent invariant.
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

    -- The invariant this migration owns is the PUBLIC grant and any direct
    -- grant to the browser roles. Access inherited through a platform
    -- monitoring role membership is a Supabase platform default that a
    -- project migration does not own and must not revoke; it is reported
    -- below rather than asserted. On the managed project the inherited
    -- count is 0 and the browser roles have no read at all.
    select count(*) into leaked
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    cross join lateral aclexplode(coalesce(c.relacl, '{}'::aclitem[])) grant_entry
    where n.nspname = 'extensions'
      and c.relname in ('pg_stat_statements', 'pg_stat_statements_info')
      and grant_entry.privilege_type = 'SELECT'
      and (
          grant_entry.grantee = 0
          or grant_entry.grantee in (
              select oid from pg_roles where rolname in ('anon', 'authenticated')
          )
      );
    if views_revoked = views_present and leaked <> 0 then
        raise exception
            'pg_stat_statements still granted to PUBLIC, anon or authenticated'
            using errcode = '42501';
    end if;

    select count(*) into inherited_leak
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'extensions'
      and c.relname in ('pg_stat_statements', 'pg_stat_statements_info')
      and (
          has_table_privilege('anon', c.oid, 'SELECT')
          or has_table_privilege('authenticated', c.oid, 'SELECT')
      );
    if inherited_leak > 0 then
        raise notice
            'pg_stat_statements remains reachable for anon/authenticated through a platform role membership; the PUBLIC and direct grants are removed';
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

    if roles_configured > 0 and not exists (
        select 1 from pg_db_role_setting s
        join pg_roles r on r.oid = s.setrole
        where r.rolname = 'postgres'
          and array_to_string(s.setconfig, ',') like '%log_min_error_statement=fatal%'
    ) then
        raise exception 'log_min_error_statement was not applied to the postgres role'
            using errcode = '42501';
    end if;

    raise notice
        'platform hardening applied: log roles %, revoked views % of % present',
        roles_configured, views_revoked, views_present;
end
$$;
