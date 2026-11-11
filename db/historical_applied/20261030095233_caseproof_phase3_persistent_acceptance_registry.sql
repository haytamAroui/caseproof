-- Persistent Phase 3 acceptance registry; intentionally no cleanup automation.
-- Auth identities must be provisioned through GoTrue Admin, not SQL inserts.
create table if not exists caseproof._phase3_acceptance_registry (
 fixture_key text primary key,
 org_id uuid,
 matter_id uuid,
 owner_user_id uuid,
 ungranted_user_id uuid,
 foreign_user_id uuid,
 bundle_manifest jsonb not null default '{}'::jsonb,
 acceptance_evidence jsonb not null default '{}'::jsonb,
 lifecycle text not null default 'awaiting_auth_provisioning',
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 constraint phase3_fixture_lifecycle check (lifecycle in ('awaiting_auth_provisioning','ready','testing','accepted','merged'))
);
alter table caseproof._phase3_acceptance_registry enable row level security;
revoke all on caseproof._phase3_acceptance_registry from public,anon,authenticated;
insert into caseproof._phase3_acceptance_registry(fixture_key,bundle_manifest)
values ('phase3-ocr-live-20261030',jsonb_build_object(
 'draft.docx','d3a510daeb493df28a2e4beb180dfcabb1bb8105f8650002c4940374a72d40a8',
 'inventory.txt','27de7aa69a66d20c4323039a47cbb6e6c91307d1cf1d5d2cdadc272de0bb7d0c',
 'stuk-1-invoice.pdf','188ee628997a4b193aae82b16ffb9a024db513d93541fdf4eb91495c01f5a778',
 'piece-2-scanned-receipt.pdf','313aefd33648c0f93e84dd9473d0a4136e49cac804f6dd42fe8d5891f6c5ff5b'))
on conflict(fixture_key) do nothing;