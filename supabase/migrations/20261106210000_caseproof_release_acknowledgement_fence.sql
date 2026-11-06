-- PR204: explicit release intent is bound to the trusted server actor, never
-- to client-supplied names. Existing historical releases are not rewritten.
-- Deployment is pilot-gated: install only together with API release changes.
begin;

create function caseproof.release_acknowledgement_fence()
returns trigger language plpgsql security invoker
set search_path = ''
as $$
declare
  ack jsonb := new.manifest -> 'release_acknowledgement';
  entered_at timestamptz;
begin
  if jsonb_typeof(ack) is distinct from 'object'
    or (select count(*) from jsonb_object_keys(ack)) <> 10
    or ack->>'schema' is distinct from 'caseproof-release-ack-v1'
    or ack->>'intent' is distinct from 'AUTHORIZE_REVIEW_RECORD_RELEASE'
    or ack->>'actor_id' is distinct from new.actor_id::text
    or ack->>'release_id' is distinct from new.release_id::text
    or ack->>'snapshot_hash' is distinct from new.snapshot_hash
    or ack->>'release_type' is distinct from
       new.manifest #>> '{review_completeness,release_type}'
    or coalesce(ack->>'actor_label_type','') not in ('confirmed_email','account_id')
    or coalesce(length(ack->>'actor_label'),0) not between 1 and 254
    or ack->>'actor_label' ~ '[[:cntrl:]]'
    or coalesce(length(ack->>'notice'),0) < 30
  then
    raise exception 'release acknowledgment missing or actor/snapshot mismatch'
      using errcode='42501';
  end if;
  begin
    entered_at := (ack->>'acknowledged_at')::timestamptz;
  exception when others then
    raise exception 'invalid release acknowledgment timestamp' using errcode='42501';
  end;
  if entered_at is null
     or entered_at > clock_timestamp() + interval '5 minutes'
     or entered_at < clock_timestamp() - interval '10 minutes'
  then
    raise exception 'release acknowledgment timestamp outside admission window'
      using errcode='42501';
  end if;
  return new;
end $$;

revoke all on function caseproof.release_acknowledgement_fence()
from public, anon, authenticated;

create trigger release_acknowledgement_fence
before insert on caseproof.dossier_releases
for each row execute function caseproof.release_acknowledgement_fence();

commit;
