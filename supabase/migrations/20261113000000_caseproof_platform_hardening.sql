-- CaseProof platform hardening for the caseproof-dev environment.
--
-- Scope, rationale and reversibility for each block:
--
-- 1. FORCE ROW LEVEL SECURITY on every caseproof relation.
--    RLS was already enabled on all relations, but a table OWNER bypasses
--    RLS unless FORCE is set. Every caseproof relation is currently owned
--    by `postgres`, which holds BYPASSRLS, so this changes no live
--    behaviour today. It makes the invariant explicit and keeps it true if
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
-- 3. Revoke SELECT on the pg_stat_statements views from anon and
--    authenticated. Supabase grants these by default. The views expose the
--    normalized query text of every statement the database executes, to a
--    role whose credential (the publishable key) is served publicly by the
--    development app. RPC arguments are parameterised and are not inlined
--    today, so this is a defence-in-depth removal of a public read of
--    internal query text and of any future inlined literal.
--
-- 4. Raise log_min_error_statement from 'error' to 'fatal' for the
--    database. Normal traffic is already not logged (log_statement='ddl',
--    log_min_duration_statement=-1), but any statement that ERRORS is
--    written to the database log in full, and a PostgREST direct table read
--    inlines filter values into the statement text. log_parameter_max_
--    length_on_error is already 0, so parameter values are omitted, but
--    statement text is not. Raising the threshold to 'fatal' removes
--    routine statement text from the database log while keeping the error
--    message itself and catastrophic diagnostics.
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

-- NOSUPERUSER / NOBYPASSRLS are the defaults for a newly created role and are
-- asserted below. They are not restated here because altering the SUPERUSER
-- attribute requires the SUPERUSER privilege, which the migration role does
-- not hold, and because restating them would grant nothing.
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

-- 3. Remove the public read of internal query text.
--    The SELECT grant on these views is held by PUBLIC (`=r/postgres` in
--    pg_class.relacl), so revoking only from anon and authenticated is a
--    no-op: PUBLIC still confers the privilege on every role. The revoke
--    from PUBLIC is therefore the effective one. The explicit revokes from
--    anon and authenticated are kept so the intent survives a future
--    platform re-grant of a direct grant.
--    Note: Supabase re-applies its platform defaults on some project
--    configuration changes, so this must be re-verified after any such
--    change. See the deployment receipt.
do $$
begin
    if exists (
        select 1 from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'extensions' and c.relname = 'pg_stat_statements'
    ) then
        execute 'revoke select on extensions.pg_stat_statements from public';
        execute 'revoke select on extensions.pg_stat_statements from anon, authenticated';
    end if;
    if exists (
        select 1 from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'extensions' and c.relname = 'pg_stat_statements_info'
    ) then
        execute 'revoke select on extensions.pg_stat_statements_info from public';
        execute 'revoke select on extensions.pg_stat_statements_info from anon, authenticated';
    end if;
end
$$;

-- 4. Stop routine failing statements from writing statement text to the log.
--    `ALTER DATABASE ... SET` requires the SUPERUSER privilege, which the
--    migration role does not hold on a managed project, so the parameter is
--    set per role instead. `postgres` covers direct and management
--    connections; `authenticator` covers PostgREST sessions, which
--    authenticate as `authenticator` and then assume a client role.
do $$
begin
    execute 'alter role postgres set log_min_error_statement = ''fatal''';
    execute 'alter role authenticator set log_min_error_statement = ''fatal''';
end
$$;

-- Fail closed if the hardened state is not exactly what was intended.
do $$
declare
    unprotected integer;
    leaked integer;
    reader_write_privileges integer;
    reader_owner_count integer;
    reader_privileged_membership integer;
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

    select count(*) into leaked
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'extensions'
      and c.relname in ('pg_stat_statements', 'pg_stat_statements_info')
      and (has_table_privilege('anon', c.oid, 'SELECT')
           or has_table_privilege('authenticated', c.oid, 'SELECT'));
    if leaked <> 0 then
        raise exception 'pg_stat_statements still readable by anon or authenticated'
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
end
$$;
