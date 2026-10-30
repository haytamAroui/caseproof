-- M0.5: private CI lifecycle ledger. No public Data API access.
create table if not exists caseproof.test_run_registry (
  run_id uuid not null,
  resource_type text not null check (resource_type in ('run', 'auth_user', 'matter', 'storage_file')),
  resource_id text not null,
  created_at timestamptz not null default now(),
  state text not null default 'RESERVED' check (state in ('RESERVED','CREATED','CLEANING','CLEANED')),
  primary key (run_id, resource_type, resource_id)
);
create index if not exists test_run_registry_stale_idx on caseproof.test_run_registry (created_at,run_id);
revoke all on caseproof.test_run_registry from public, anon, authenticated;
alter table caseproof.test_run_registry enable row level security;
comment on table caseproof.test_run_registry is 'CaseProof development-only protected CI resource ownership ledger; no anonymous/authenticated access.';
