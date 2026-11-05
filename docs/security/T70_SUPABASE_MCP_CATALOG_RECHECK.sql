-- CaseProof T70: NON-MUTATING, METADATA-ONLY reproducible Supabase audit.
-- Use with Supabase MCP execute_sql, against the specifically approved project.
-- DO NOT execute application RPCs, read document rows, list Storage objects,
-- inspect authentication user records, or change grants, roles or policies.
-- These SELECTs are not signed-client adversarial security tests.

-- 1. Exposed CaseProof SECURITY DEFINER functions and delegated-call candidates.
SELECT p.proname AS rpc,
       has_function_privilege('anon',p.oid,'EXECUTE') AS anonymous_execute,
       has_function_privilege('authenticated',p.oid,'EXECUTE') AS user_execute,
       p.proconfig AS function_settings,
       (pg_get_functiondef(p.oid) ~* 'auth[.]uid[[:space:]]*\(') AS directly_mentions_actor,
       md5(pg_get_functiondef(p.oid)) AS definition_fingerprint
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname LIKE 'caseproof_%'
  AND p.prosecdef
ORDER BY p.proname;

-- 2. Seven authenticated-readable private tables and their policy types.
SELECT c.relname AS table_name,c.relrowsecurity AS rls_enabled,
       has_table_privilege('anon',c.oid,'SELECT') AS anon_select,
       has_table_privilege('authenticated',c.oid,'SELECT') AS user_select,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) AS policy_count
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='caseproof' AND c.relkind='r'
  AND (has_table_privilege('anon',c.oid,'SELECT')
       OR has_table_privilege('authenticated',c.oid,'SELECT'))
ORDER BY c.relname;

-- 3. Verify RLS policy semantics, including restrictive soft-deletion guards.
SELECT schemaname,tablename,policyname,permissive,cmd,roles
FROM pg_policies
WHERE schemaname='caseproof' AND tablename IN ('cases','documents')
ORDER BY tablename,policyname;

-- 4. Storage configuration and read/put-once policy metadata ONLY.
SELECT id,public,file_size_limit,allowed_mime_types
FROM storage.buckets ORDER BY id;
SELECT policyname,permissive,cmd,roles,
       (coalesce(qual,'') ~* 'm[.]active') AS active_member_read,
       (coalesce(qual,'') ~* 'g[.]active') AS active_grant_read,
       (coalesce(with_check,'') ~* 'm[.]active') AS active_member_write,
       (coalesce(with_check,'') ~* 'g[.]active') AS active_grant_write
FROM pg_policies
WHERE schemaname='storage' AND tablename='objects'
ORDER BY policyname;

-- 5. Number of private tables without an explicit policy.
SELECT count(*) AS private_rls_no_policy
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='caseproof' AND c.relkind='r' AND c.relrowsecurity
  AND NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid);

-- Scope warning: Storage objects are NOT backed up with PostgreSQL database
-- backups. This query contains NO proof of operational restore or residency.
