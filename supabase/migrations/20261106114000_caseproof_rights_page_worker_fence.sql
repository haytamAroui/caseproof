-- PR2 forward hardening: durable OCR/raster worker paths are processing.
-- No activation, backfill, permissions expansion or client-visible new RPC.
begin;

create function caseproof._rights_page_worker_fence()
returns trigger language plpgsql security definer set search_path='' as $$
declare
  v_enabled boolean;
  v_manifest jsonb;
  v_pages jsonb;
  v_page jsonb;
  v_doc uuid;
  v_ver uuid;
  v_digest text;
  v_known text;
begin
  select enabled into v_enabled from caseproof._rights_enforcement_control
    where singleton=true;
  if v_enabled is null then
    raise exception 'rights enforcement configuration unavailable' using errcode='42501';
  end if;
  if v_enabled=false then return new; end if;

  if tg_table_name='page_jobs' then
    -- Cancellation/finish/cleanup are not new processing. Starting,
    -- retrying, leasing and storing new bytes DO require current rights.
    if tg_op='UPDATE' and new.state<>'running' then return new; end if;
    begin v_manifest:=new.manifest::jsonb;
    exception when others then
      raise exception 'rights page manifest unavailable' using errcode='42501';
    end;
    v_pages:=v_manifest->'pages';
    if jsonb_typeof(v_pages)<>'array'
       or jsonb_array_length(v_pages) not between 1 and 200 then
      raise exception 'rights page manifest unavailable' using errcode='42501';
    end if;
    for v_page in select value from jsonb_array_elements(v_pages) loop
      begin
        v_doc:=(v_page->>'document_id')::uuid;
        v_ver:=(v_page->>'version_id')::uuid;
      exception when others then
        raise exception 'rights page source malformed' using errcode='42501';
      end;
      v_digest:=v_page->>'original_sha256';
      select dv.original_sha256_hex into v_known
      from caseproof.documents d
      join caseproof.document_versions dv on dv.org_id=d.org_id
        and dv.document_id=d.id
      where d.org_id=new.org_id and d.case_id=new.case_id
        and d.id=v_doc and dv.id=v_ver;
      if v_known is null or v_digest is distinct from v_known then
        raise exception 'rights page source mismatch' using errcode='42501';
      end if;
      perform caseproof._rights_require_source(
        new.org_id,new.case_id,v_doc,v_ver,'process');
    end loop;
  elsif tg_table_name='page_results' then
    select j.manifest::jsonb into v_manifest
    from caseproof.page_jobs j
    where j.org_id=new.org_id and j.case_id=new.case_id
      and j.request_id=new.request_id;
    if v_manifest is null or jsonb_typeof(v_manifest->'pages')<>'array' then
      raise exception 'rights page job unavailable' using errcode='42501';
    end if;
    select p.value into v_page from jsonb_array_elements(v_manifest->'pages') p(value)
    where (p.value->>'version_id')||':'||(p.value->>'pdf_page')=new.page_key;
    if v_page is null then
      raise exception 'rights page key unavailable' using errcode='42501';
    end if;
    begin
      v_doc:=(v_page->>'document_id')::uuid;
      v_ver:=(v_page->>'version_id')::uuid;
    exception when others then
      raise exception 'rights page source malformed' using errcode='42501';
    end;
    v_digest:=v_page->>'original_sha256';
    select dv.original_sha256_hex into v_known from caseproof.documents d
    join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
    where d.org_id=new.org_id and d.case_id=new.case_id
      and d.id=v_doc and dv.id=v_ver;
    if v_known is null or v_digest is distinct from v_known then
      raise exception 'rights page source mismatch' using errcode='42501';
    end if;
    perform caseproof._rights_require_source(
      new.org_id,new.case_id,v_doc,v_ver,'process');
  else
    raise exception 'rights worker trigger misconfigured' using errcode='42501';
  end if;
  return new;
end $$;
revoke all on function caseproof._rights_page_worker_fence()
  from public,anon,authenticated,service_role;

create trigger rights_page_enqueue_lease
  before insert or update on caseproof.page_jobs
  for each row execute function caseproof._rights_page_worker_fence();
create trigger rights_page_result
  before insert on caseproof.page_results
  for each row execute function caseproof._rights_page_worker_fence();

revoke all on caseproof.page_jobs,caseproof.page_results,caseproof.page_job_events
  from service_role;
commit;
