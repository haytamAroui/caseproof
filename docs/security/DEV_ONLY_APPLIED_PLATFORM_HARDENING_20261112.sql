-- DEV-ONLY applied platform hardening for caseproof-dev.
--
-- NOT a schema migration. These statements tune Supabase-managed platform
-- objects and roles, so they are deliberately excluded from
-- supabase/migrations/ and from the replayable migration chain: a plain
-- PostgreSQL 17 instance has neither the `authenticator` role nor the
-- `extensions` schema, and a local Supabase stack may own the platform
-- views differently. Including them in the chain made the replay fail in
-- exactly those environments.
--
-- Applied once to the managed project; verified by read-back in
-- docs/security/LIVE_PLATFORM_HARDENING_RECEIPT_2026-11-12.md.
--
-- Idempotent: every statement is safe to re-apply.
--
-- Rollback:
--   grant select on extensions.pg_stat_statements, extensions.pg_stat_statements_info to public;
--   alter role postgres reset log_min_error_statement;
--   alter role authenticator reset log_min_error_statement;

set search_path = '';

do $$
declare
    target text;
    views_present integer := 0;
    views_revoked integer := 0;
    roles_configured integer := 0;
    public_grant_leak integer := 0;
    inherited_leak integer := 0;
begin
    -- log_min_error_statement. Normal traffic is already unlogged
    -- (log_statement='ddl', log_min_duration_statement=-1), but any
    -- statement that ERRORS is written to the database log in full, and a
    -- PostgREST direct table read inlines filter values into the statement
    -- text. ALTER DATABASE ... SET requires SUPERUSER, which the migration
    -- role does not hold on a managed project, so the parameter is set per
    -- role: postgres covers direct and management connections,
    -- authenticator covers PostgREST sessions, which authenticate as
    -- authenticator and then assume a client role.
    for target in
        select rolname::text from pg_roles where rolname in ('postgres', 'authenticator')
    loop
        begin
            execute format(
                'alter role %I set log_min_error_statement = %L', target, 'fatal'
            );
            roles_configured := roles_configured + 1;
        exception when insufficient_privilege then
            raise notice
                'log_min_error_statement not applied to role % (insufficient privilege)',
                target;
        end;
    end loop;

    -- Remove the PUBLIC read of internal query text. The grant is held by
    -- PUBLIC, so revoking only from anon and authenticated would be a
    -- no-op. Access inherited through a Supabase monitoring role
    -- membership is a platform default that a project statement must not
    -- revoke; it is reported instead.
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
            exception when insufficient_privilege then
                raise notice
                    'revoke select on extensions.% not applied (insufficient privilege)',
                    target;
            end;
        end if;
    end loop;

    -- The invariant this statement owns: no PUBLIC grant, and no direct
    -- grant to the browser roles.
    select count(*) into public_grant_leak
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
    if views_revoked = views_present and public_grant_leak <> 0 then
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

    raise notice
        'platform hardening applied: log roles %, revoked views % of % present, public grant leak %, inherited reachability %',
        roles_configured, views_revoked, views_present, public_grant_leak, inherited_leak;
end
$$;
