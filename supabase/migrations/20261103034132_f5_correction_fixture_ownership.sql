-- Development fixture safety: register derivatives in the reservation transaction.
-- No effect on matters absent from the protected run registry.
create function caseproof.register_fixture_draft_derivative()
returns trigger language plpgsql security definer set search_path='' as $$
declare runs uuid[]; run uuid;
begin
 select array_agg(m.run_id) into runs from caseproof.test_run_registry m
 join caseproof.test_run_registry root on root.run_id=m.run_id
 and root.resource_type='run' and root.resource_id=m.run_id::text
 and root.state in ('RESERVED','CREATED')
 where m.resource_type='matter' and m.resource_id=new.case_id::text
 and m.state in ('RESERVED','CREATED');
 if coalesce(cardinality(runs),0)=0 then return new; end if;
 if cardinality(runs)<>1 then raise exception 'ambiguous fixture ownership'; end if;
 run:=runs[1];
 insert into caseproof.test_run_registry(run_id,resource_type,resource_id,state)
 values(run,'storage_file',new.org_id::text||'/'||new.case_id::text||'/'||new.document_id::text||'/'||new.version_id::text||'/'||new.original_sha256,'RESERVED');
 return new;
end $$;
revoke all on function caseproof.register_fixture_draft_derivative() from public,anon,authenticated;
create trigger register_fixture_draft_derivative after insert on caseproof.dossier_draft_revisions
for each row execute function caseproof.register_fixture_draft_derivative();
