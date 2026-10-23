-- DISPOSABLE CI ONLY. Not a Supabase migration or authenticated runtime.
begin;
create table caseproof._ei_steps (
    org_id uuid not null,
    case_id uuid not null,
    run_id text not null check (length(run_id) between 1 and 128),
    step_id text not null check (length(step_id) between 1 and 256),
    actor_id uuid not null,
    input_sha text not null check (input_sha ~ '^[0-9a-f]{64}$'),
    state text not null check (state in ('prepared','dispatched','received','completed','outcome_unknown','failed')),
    payload text check (octet_length(payload) <= 4194304),
    revision integer not null default 1 check (revision > 0),
    created_at timestamptz not null default now(),
    primary key (org_id,case_id,run_id,step_id),
    foreign key (org_id,case_id) references caseproof.cases(org_id,id),
    foreign key (org_id,actor_id) references caseproof.organization_members(org_id,user_id)
);
create index _ei_steps_actor_idx on caseproof._ei_steps(org_id,actor_id);
create table caseproof._ei_events (
    org_id uuid not null,
    case_id uuid not null,
    run_id text not null,
    step_id text not null,
    revision integer not null check (revision > 0),
    state text not null,
    payload_sha text check (payload_sha ~ '^[0-9a-f]{64}$'),
    actor_id uuid not null,
    created_at timestamptz not null default now(),
    primary key (org_id,case_id,run_id,step_id,revision),
    foreign key (org_id,case_id,run_id,step_id)
        references caseproof._ei_steps(org_id,case_id,run_id,step_id),
    foreign key (org_id,actor_id) references caseproof.organization_members(org_id,user_id)
);
create index _ei_events_actor_idx on caseproof._ei_events(org_id,actor_id);
alter table caseproof._ei_steps enable row level security;
alter table caseproof._ei_events enable row level security;
revoke all on caseproof._ei_steps,caseproof._ei_events from public,anon,authenticated;
commit;
