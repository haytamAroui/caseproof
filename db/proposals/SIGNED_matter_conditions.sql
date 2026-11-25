-- APPLIED to caseproof-dev as 20261124030604 (recorded in supabase/migrations/20261124030604_caseproof_signed_matter_conditions.sql); NOT applied to production.
-- Lawyer-defined conditions for ONE matter (MD "extension cible"): retrieval and routing, never a verdict.
-- Append-only revisions of a canonical spec text. The server (Python) builds the canonical JSON text and its
-- SHA-256; this function re-hashes the exact text with the built-in sha256 and refuses a mismatch, so a
-- caller cannot store a spec whose hash it did not compute over those bytes. Compare-and-swap on the revision.
-- Authorization: active org member with finding:write AND an active matter grant holding finding:write.
create table caseproof.matter_condition_specs (
  org_id uuid not null,
  case_id uuid not null,
  revision integer not null check (revision >= 1 and revision <= 100000),
  spec_text text not null check (length(spec_text) between 2 and 200000),
  spec_sha256 text not null check (spec_sha256 ~ '^[0-9a-f]{64}$'),
  actor_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (org_id, case_id, revision),
  foreign key (org_id, case_id) references caseproof.cases (org_id, id),
  foreign key (org_id, actor_id) references caseproof.organization_members (org_id, user_id),
  check (encode(sha256(convert_to(spec_text, 'UTF8')), 'hex') = spec_sha256)
);
alter table caseproof.matter_condition_specs enable row level security;
alter table caseproof.matter_condition_specs force row level security;
revoke all on caseproof.matter_condition_specs from public, anon, authenticated, service_role;
grant select on caseproof.matter_condition_specs to authenticated;

create policy matter_condition_specs_read on caseproof.matter_condition_specs
  for select to authenticated using (
    (select auth.uid()) is not null and exists (
      select 1 from caseproof.organization_members m
      join caseproof._m1_matter_grants g
        on g.org_id = m.org_id and g.user_id = m.user_id and g.case_id = matter_condition_specs.case_id and g.active
      where m.org_id = matter_condition_specs.org_id and m.user_id = (select auth.uid()) and m.active
        and 'case:read' = any (m.actions) and 'case:read' = any (g.permissions)));

create function caseproof._matter_condition_specs_immutable() returns trigger
language plpgsql security invoker set search_path = pg_catalog, pg_temp as $$
begin
  -- Same bounded bypass as the other immutable histories: only the service-only, locked, eligibility-checked
  -- retention finalize RPC (owner postgres, setting set transaction-locally) may delete. UPDATE is never allowed.
  if tg_op = 'DELETE' and current_user = 'postgres'
     and current_setting('caseproof.dev_review_cleanup', true) = 'single_fixture' then
    return old;
  end if;
  raise exception 'condition spec revisions are append-only' using errcode = '55000';
end $$;
create trigger matter_condition_specs_no_change before update or delete on caseproof.matter_condition_specs
  for each row execute function caseproof._matter_condition_specs_immutable();
create trigger matter_condition_specs_no_truncate before truncate on caseproof.matter_condition_specs
  for each statement execute function caseproof._matter_condition_specs_immutable();

create function public.caseproof_append_conditions(
  p_case uuid, p_expected integer, p_spec_text text, p_sha text
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_actor uuid := auth.uid(); v_org uuid; v_head integer; v_spec jsonb;
begin
  if v_actor is null or p_case is null or p_expected is null or p_expected < 0 or p_expected > 100000
     or p_spec_text is null or p_sha is null or p_sha !~ '^[0-9a-f]{64}$'
     or length(p_spec_text) not between 2 and 200000 then
    raise exception 'invalid conditions proposal' using errcode = '42501';
  end if;
  select c.org_id into v_org from caseproof.cases c
   where c.id = p_case and c.deleted_at is null
     and exists (select 1 from caseproof.organization_members m
                 join caseproof._m1_matter_grants g
                   on g.org_id = m.org_id and g.user_id = m.user_id and g.case_id = c.id and g.active
                 where m.org_id = c.org_id and m.user_id = v_actor and m.active
                   and 'finding:write' = any (m.actions) and 'finding:write' = any (g.permissions));
  if v_org is null then
    raise exception 'not authorized for this matter' using errcode = '42501';
  end if;
  if encode(sha256(convert_to(p_spec_text, 'UTF8')), 'hex') <> p_sha then
    raise exception 'spec hash mismatch' using errcode = '42501';
  end if;
  begin
    v_spec := p_spec_text::jsonb;
  exception when others then
    raise exception 'spec is not json' using errcode = '42501';
  end;
  if jsonb_typeof(v_spec) <> 'object' or v_spec ->> 'format' is distinct from 'caseproof-conditions-v1'
     or jsonb_typeof(v_spec -> 'conditions') <> 'array'
     or jsonb_array_length(v_spec -> 'conditions') not between 0 and 50 then
    raise exception 'unsupported conditions format' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_case::text, 0));
  select coalesce(max(revision), 0) into v_head from caseproof.matter_condition_specs
   where org_id = v_org and case_id = p_case;
  if v_head <> p_expected then
    -- Returned as data: PostgREST hides exception text from callers, and a conflict is an expected outcome.
    return jsonb_build_object('conflict', true, 'revision', v_head);
  end if;
  insert into caseproof.matter_condition_specs (org_id, case_id, revision, spec_text, spec_sha256, actor_id)
    values (v_org, p_case, v_head + 1, p_spec_text, p_sha, v_actor);
  return jsonb_build_object('revision', v_head + 1, 'spec_sha256', p_sha);
end $$;
revoke all on function public.caseproof_append_conditions(uuid, integer, text, text) from public, anon, authenticated, service_role;
grant execute on function public.caseproof_append_conditions(uuid, integer, text, text) to authenticated;

-- Latest revision for one matter. SECURITY DEFINER with the same explicit member + matter-grant check as the
-- select policy (case:read on both). A caller without access gets an ERROR (42501), never "revision 0", so
-- "denied" and "no conditions yet" are distinguishable. Direct table reads stay governed by the RLS policy.
create function public.caseproof_read_conditions(p_case uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare v_actor uuid := auth.uid(); v_row caseproof.matter_condition_specs%rowtype;
begin
  if v_actor is null or p_case is null or not exists (
      select 1 from caseproof.cases c
      join caseproof.organization_members m on m.org_id = c.org_id
      join caseproof._m1_matter_grants g on g.org_id = m.org_id and g.user_id = m.user_id and g.case_id = c.id and g.active
      where c.id = p_case and c.deleted_at is null and m.user_id = v_actor and m.active
        and 'case:read' = any (m.actions) and 'case:read' = any (g.permissions)) then
    raise exception 'not authorized for this matter' using errcode = '42501';
  end if;
  select * into v_row from caseproof.matter_condition_specs where case_id = p_case order by revision desc limit 1;
  if not found then return jsonb_build_object('revision', 0); end if;
  -- Recorded events (who and when each revision was stored), oldest first. Values come from the append-only
  -- table: actor_id is the verified subject at append time, recorded_at the database clock (UTC).
  return jsonb_build_object('revision', v_row.revision, 'spec_text', v_row.spec_text, 'spec_sha256', v_row.spec_sha256,
    'history', (select jsonb_agg(jsonb_build_object('revision', h.revision, 'spec_sha256', h.spec_sha256,
        'actor_id', h.actor_id, 'recorded_at', to_char(h.created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))
        order by h.revision)
      from caseproof.matter_condition_specs h where h.case_id = p_case));
end $$;
revoke all on function public.caseproof_read_conditions(uuid) from public, anon, authenticated, service_role;
grant execute on function public.caseproof_read_conditions(uuid) to authenticated;

-- Retention: refuse new revisions for a soft-deleted or missing matter (same guard as the other matter tables).
create trigger retention_write_guard before insert or update on caseproof.matter_condition_specs
  for each row execute function caseproof.retention_write_guard();
