-- Fence uploads already authorized before soft deletion: Storage metadata
-- writes take the same matter lock. Deny new objects for a missing/deleted case.
create function caseproof.retention_storage_guard() returns trigger
 language plpgsql security definer set search_path='' as $$
declare v_case uuid; v_org uuid; v_deleted timestamptz;
begin
 if new.bucket_id<>'caseproof-originals-dev' then return new; end if;
 begin
  v_org:=split_part(new.name,'/',1)::uuid;
  v_case:=split_part(new.name,'/',2)::uuid;
 exception when invalid_text_representation then
  raise exception 'invalid matter Storage path' using errcode='42501';
 end;
 select deleted_at into v_deleted from caseproof.cases
  where id=v_case and org_id=v_org for share;
 if not found or v_deleted is not null then
  raise exception 'matter unavailable' using errcode='42501'; end if;
 return new;
end $$;
revoke all on function caseproof.retention_storage_guard() from public,anon,authenticated;
create trigger caseproof_retention_storage_guard before insert or update on storage.objects
 for each row execute function caseproof.retention_storage_guard();
