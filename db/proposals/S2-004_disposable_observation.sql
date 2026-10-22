-- S2-004 reference implementation: DISPOSABLE PostgreSQL security fixture ONLY.
--
-- Not a migration. DO NOT apply to caseproof-dev/production or expose this
-- helper in an API: p_actor_user_id is caller-supplied synthetic fixture input
-- and is NOT an authenticated human identity. No live trust boundary exists.
-- This SQL is executed only in the dedicated ephemeral caseproof_s2_ci DB.
--
-- It proves state REVISION + immutable audit event + idempotency receipt
-- are one PostgreSQL transaction, including concurrent and faulted attempts.
-- It NEVER promotes evidence, modifies case.state, approves a finding or
-- creates a reviewer disposition. It does not replace the planned trusted
-- authorization, actor credential, evidence graph and policy verification.

begin;

create function caseproof._s2_004_disposable_observation(
    p_actor_user_id uuid,
    p_case_id uuid,
    p_expected_case_revision bigint,
    p_expected_scope_version bigint,
    p_expected_manifest_revision bigint,
    p_expected_policy_version text,
    p_idempotency_key text,
    p_semantic_sha256 text,
    p_correlation_id uuid,
    p_fault text default null
)
returns table(event_id uuid, committed_revision bigint, idempotent_replay boolean)
language plpgsql
security invoker
set search_path = pg_catalog, pg_temp
as $body$
declare
    v_org_id uuid;
    v_actions text[];
    v_case caseproof.cases%rowtype;
    v_existing caseproof.idempotency_records%rowtype;
    v_receipt jsonb;
    v_event uuid;
    v_next bigint;
begin
    if p_actor_user_id is null or p_case_id is null
       or p_correlation_id is null
       or p_expected_case_revision is null or p_expected_case_revision < 1
       or p_expected_scope_version is null or p_expected_scope_version < 1
       or p_expected_manifest_revision is null or p_expected_manifest_revision < 1
       or p_expected_policy_version is null
       or length(btrim(p_expected_policy_version)) = 0
       or p_idempotency_key is null
       or length(p_idempotency_key) not between 1 and 128
       or length(btrim(p_idempotency_key)) != length(p_idempotency_key)
       or p_semantic_sha256 is null
       or p_semantic_sha256 !~ '^[0-9a-f]{64}$'
       or p_fault not in ('audit', 'receipt') then
       -- NULL fault is intentional; p_fault NOT IN is NULL in SQL.
       raise exception 'invalid internal observation request' using errcode = '22023';
    end if;

    -- Stable lock order: live membership FIRST, then exact tenant-owned case.
    -- The first lookup never discloses whether a foreign case exists.
    select m.org_id, m.actions into v_org_id, v_actions
    from caseproof.organization_members as m
    where m.user_id = p_actor_user_id
      and m.org_id = (
         select c.org_id from caseproof.cases as c where c.id = p_case_id
      )
      and m.active = true
    for update of m;

    if v_org_id is null then
        raise exception 'case not found' using errcode = 'P0002';
    end if;
    if not ('case:read' = any(v_actions)
        and 'finding:write' = any(v_actions)) then
        raise exception 'operation not permitted' using errcode = '42501';
    end if;

    select * into v_case
    from caseproof.cases as c
    where c.id = p_case_id and c.org_id = v_org_id
    for update;
    if not found then
        raise exception 'case not found' using errcode = 'P0002';
    end if;

    -- Enforce single writer per case; check receipts BEFORE revision mismatch
    -- so identical safe retries replay the original event.
    select * into v_existing
    from caseproof.idempotency_records as i
    where i.org_id = v_org_id and i.case_id = p_case_id
      and i.operation = 's2_004_internal_observation'
      and i.idempotency_key = p_idempotency_key;

    if found then
        if v_existing.input_sha256_hex is distinct from p_semantic_sha256 then
            raise exception 'idempotency input mismatch' using errcode = '23505';
        end if;
        begin
            v_receipt := v_existing.response_reference::jsonb;
            v_event := (v_receipt->>'event_id')::uuid;
            v_next := (v_receipt->>'revision')::bigint;
        exception when others then
            raise exception 'saved idempotency receipt corrupt' using errcode = '55000';
        end;
        if v_receipt->>'schema' is distinct from 's2-004-observation-v1'
           or v_next is null
           or not exists (
               select 1 from caseproof.audit_events as a
               where a.id = v_event and a.org_id = v_org_id
                 and a.case_id = p_case_id
                 and a.actor_user_id = p_actor_user_id
                 and a.action = 's2_004_internal_observation'
                 and a.input_sha256_hex = p_semantic_sha256
           ) then
            raise exception 'saved idempotency receipt has no valid audit' using errcode = '55000';
        end if;
        return query select v_event, v_next, true;
        return;
    end if;

    if v_case.case_revision != p_expected_case_revision
       or v_case.scope_version != p_expected_scope_version
       or v_case.manifest_revision != p_expected_manifest_revision
       or v_case.effective_policy_version != p_expected_policy_version
       or v_case.state != 'candidate' then
        raise exception 'stale or unsupported case snapshot' using errcode = '40001';
    end if;

    update caseproof.cases as c
       set case_revision = c.case_revision + 1, updated_at = now()
    where c.id = p_case_id and c.org_id = v_org_id
      and c.case_revision = p_expected_case_revision
      and c.state = 'candidate'
    returning c.case_revision into v_next;

    if v_next is null then
        raise exception 'concurrent revision mismatch' using errcode = '40001';
    end if;

    -- Force an audit constraint failure after revision mutation. A caller
    -- transaction must roll back the ENTIRE statement, not rescue the update.
    insert into caseproof.audit_events (
        org_id, case_id, actor_type, actor_user_id, action,
        event_schema_version, correlation_id, previous_state, new_state,
        input_sha256_hex
    ) values (
        v_org_id, p_case_id, 'human', p_actor_user_id,
        's2_004_internal_observation', 's2-004-observation-v1',
        p_correlation_id, 'candidate', 'candidate',
        case when p_fault = 'audit' then 'invalid' else p_semantic_sha256 end
    ) returning id into v_event;

    v_receipt := jsonb_build_object(
      'schema', 's2-004-observation-v1',
      'event_id', v_event,
      'revision', v_next
    );

    insert into caseproof.idempotency_records (
       org_id, case_id, operation, idempotency_key,
       input_sha256_hex, response_reference
    ) values (
       v_org_id, p_case_id, 's2_004_internal_observation',
       p_idempotency_key,
       case when p_fault = 'receipt' then 'invalid' else p_semantic_sha256 end,
       v_receipt::text
    );

    return query select v_event, v_next, false;
end;
$body$;

-- No grants to runtime roles; Postgres functions normally default to
-- EXECUTE for PUBLIC, so explicit revocation is mandatory.
revoke all on function caseproof._s2_004_disposable_observation(
    uuid,uuid,bigint,bigint,bigint,text,text,text,uuid,text
) from public, anon, authenticated;

-- Explicit permission assertion; a mistake here invalidates this fixture.
do $grants$
begin
    if has_function_privilege('anon', 'caseproof._s2_004_disposable_observation(uuid,uuid,bigint,bigint,bigint,text,text,text,uuid,text)', 'EXECUTE')
       or has_function_privilege('authenticated', 'caseproof._s2_004_disposable_observation(uuid,uuid,bigint,bigint,bigint,text,text,text,uuid,text)', 'EXECUTE') then
        raise exception 'internal-only S2-004 fixture unexpectedly executable by clients';
    end if;
end $grants$;

commit;
