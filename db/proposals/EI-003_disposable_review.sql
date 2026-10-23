-- Disposable CI only. No live migration, approval permission or public grants.
begin;
create table caseproof._review_snapshots (
 org_id uuid not null, case_id uuid not null,
 snapshot_sha text not null check (snapshot_sha ~ '^[a-f0-9]{64}$'),
 payload text not null check (octet_length(payload) <= 4194304),
 created_by uuid not null, created_at timestamptz not null default now(),
 primary key(org_id,case_id,snapshot_sha),
 foreign key(org_id,case_id) references caseproof.cases(org_id,id),
 foreign key(org_id,created_by) references caseproof.organization_members(org_id,user_id)
);
create index _review_snapshots_actor on caseproof._review_snapshots(org_id,created_by);
create table caseproof._review_heads (
 org_id uuid not null, case_id uuid not null, snapshot_sha text not null,
 revision bigint not null default 0 check(revision>=0),
 audit_sha text not null check(audit_sha ~ '^[a-f0-9]{64}$'),
 primary key(org_id,case_id),
 foreign key(org_id,case_id,snapshot_sha) references caseproof._review_snapshots(org_id,case_id,snapshot_sha)
);
create index _review_heads_snapshot on caseproof._review_heads(org_id,case_id,snapshot_sha);
create table caseproof._review_events (
 org_id uuid not null, case_id uuid not null, revision bigint not null check(revision>0),
 snapshot_sha text not null, actor_id uuid not null, request_id uuid not null,
 event_json text not null check(octet_length(event_json)<=32768),
 audit_sha text not null check(audit_sha ~ '^[a-f0-9]{64}$'),
 primary key(org_id,case_id,revision),
 unique(org_id,case_id,request_id),
 foreign key(org_id,case_id,snapshot_sha) references caseproof._review_snapshots(org_id,case_id,snapshot_sha),
 foreign key(org_id,actor_id) references caseproof.organization_members(org_id,user_id)
);
create index _review_events_snapshot on caseproof._review_events(org_id,case_id,snapshot_sha);
create index _review_events_actor on caseproof._review_events(org_id,actor_id);
create table caseproof._review_receipts (
 org_id uuid not null, case_id uuid not null, request_id uuid not null,
 input_sha text not null check(input_sha ~ '^[a-f0-9]{64}$'),
 revision bigint not null, receipt_json text not null,
 primary key(org_id,case_id,request_id),
 foreign key(org_id,case_id,revision) references caseproof._review_events(org_id,case_id,revision)
);
create index _review_receipts_event on caseproof._review_receipts(org_id,case_id,revision);
alter table caseproof._review_snapshots enable row level security;
alter table caseproof._review_heads enable row level security;
alter table caseproof._review_events enable row level security;
alter table caseproof._review_receipts enable row level security;
revoke all on caseproof._review_snapshots,caseproof._review_heads,caseproof._review_events,caseproof._review_receipts
 from public,anon,authenticated;
commit;
