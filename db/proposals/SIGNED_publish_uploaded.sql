-- Proposal (not applied): signed publish_uploaded for the workbench, against
-- the live _m2_brief_* schema (20261027195417). Server-enforced, non-bypassable
-- write boundary for direct authenticated calls:
--  * the published representation must be byte-identical to the representation
--    registered for the same verified original by the trusted path only
--    (caseproof._dev_journey_sources is written solely by service_role
--    ingestion or by the storage-fidelity-checked SQL TXT ingest), so a direct
--    caller cannot publish a representation the verifier never derived;
--  * the vault intent is resolved server-side: exactly the verified intent
--    bound to this version and its original digest is used (deterministically
--    the oldest when several verified intents name the same version); the
--    caller never supplies it (mirrors disposable_litigation_brief_graph.py:135-145);
--  * representation_sha256 and graph_sha256 are verified at write with the
--    core sha256(bytea) primitive against the exact submitted text;
--  * every reference resolves against the current CONFIRMED exhibit register
--    (label/alias, case-insensitive); its quote must occur in the referenced
--    exhibit's registered source representation; pdf_page, when present, must
--    belong to that entry's confirmed pages;
--  * every assertion's text must equal the exact slice of the published
--    representation it spans and must cite a passed reference; kind/fact_role/
--    language/source_language must satisfy the live enum checks;
--  * the working brief id is recomputed in SQL from case identity and role
--    (mirrors working_brief_id in disposable_signed_brief_publisher.py);
--  * CAS on _m2_brief_heads with expected revision; request_id replay via
--    _m2_brief_events unique(org,case,brief,request_id), identity checked
--    against the event's recorded version row.
-- Parser identity, graph content and event identity are derived by readers
-- from stored content; no stored digest is trusted at read time.
create or replace function public.caseproof_signed_publish_uploaded(
 p_case uuid,p_brief uuid,p_version uuid,p_request uuid,p_expected bigint,
 p_document uuid,p_document_version uuid,p_role text,
 p_representation text,p_representation_sha text,p_parser_id text,
 p_references jsonb,p_assertions jsonb,p_graph_text text,p_graph_sha text
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_head caseproof._m2_brief_heads%rowtype;
 v_intent uuid;
 v_source caseproof._dev_journey_sources%rowtype;
 v_register jsonb; v_case_rev bigint; v_exhibit_rev bigint; v_original_sha text;
 v_raw bytea; v_working uuid; v_h text; v_ref jsonb; v_ast jsonb;
 v_ref_ids text[]:='{}';
 v_entry jsonb; v_entry_version uuid; v_entry_rep text;
 v_label text; v_quote text; v_pdf_page jsonb; v_ok boolean;
 v_new_rev bigint; v_now timestamptz:=now(); v_audit uuid:=gen_random_uuid();
 v_replay_version uuid;
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 or p_case is null or p_version is null or p_request is null or p_expected is null
 or p_document is null or p_document_version is null
 or p_role not in ('own_draft','opponent_brief')
 or p_representation is null or p_representation='' or octet_length(p_representation)>480000
 or p_parser_id is null or length(p_parser_id) not between 1 and 256
 or jsonb_typeof(coalesce(p_references,'null'::jsonb)) is distinct from 'array'
 or jsonb_array_length(p_references)>512
 or jsonb_typeof(coalesce(p_assertions,'null'::jsonb)) is distinct from 'array'
 or jsonb_array_length(p_assertions)>2048
 or p_graph_text is null or length(p_graph_text)>200000
 or p_representation_sha is null
 or p_representation_sha<>encode(sha256(convert_to(p_representation,'UTF8')),'hex')
 or p_graph_sha is null
 or p_graph_sha<>encode(sha256(convert_to(p_graph_text,'UTF8')),'hex')
 then return jsonb_build_object('ok',false,'error','invalid'); end if;

 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
 where c.id=p_case for share of c,m,g;
 if v_org is null then return jsonb_build_object('ok',false,'error','forbidden'); end if;

 -- working brief identity recomputed server-side; the caller cannot steer it
 v_h:=encode(sha256(convert_to('caseproof-working-brief:'||p_role||':'||p_case::text,'UTF8')),'hex');
 v_raw:=decode(substring(v_h from 1 for 32),'hex');
 v_raw:=set_byte(v_raw,6,(get_byte(v_raw,6)&15)|64);
 v_raw:=set_byte(v_raw,8,(get_byte(v_raw,8)&63)|128);
 v_working:=encode(v_raw,'hex')::uuid;
 if p_brief is null or p_brief<>v_working
 then return jsonb_build_object('ok',false,'error','invalid'); end if;

 -- verified vault intent + original digest chain (bytes fidelity was verified
 -- against Storage at upload/ingest time)
 select dv.original_sha256_hex, i.intent_id into v_original_sha, v_intent
 from caseproof.documents d
 join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
 join caseproof._s2_009b_vault_intents i on i.org_id=dv.org_id
    and i.case_id=d.case_id and i.document_id=d.id and i.document_version_id=dv.id
    and i.sha256_hex=dv.original_sha256_hex and i.state='verified'
 where d.org_id=v_org and d.case_id=p_case and d.id=p_document and dv.id=p_document_version
 order by i.created_at, i.intent_id
 limit 1;
 if v_original_sha is null then return jsonb_build_object('ok',false,'error','invalid'); end if;

 -- representation byte-identical to the trusted-registry source for this
 -- exact version
 select s.* into v_source from caseproof._dev_journey_sources s
 where s.org_id=v_org and s.case_id=p_case and s.document_id=p_document
   and s.version_id=p_document_version and s.original_sha=v_original_sha
   and s.representation_sha=p_representation_sha
   and s.representation=p_representation;
 if v_source.document_id is null then return jsonb_build_object('ok',false,'error','invalid'); end if;

 insert into caseproof._m2_brief_heads(org_id,case_id,brief_id)
 values(v_org,p_case,v_working) on conflict do nothing;
 select h.* into v_head from caseproof._m2_brief_heads h
 where h.org_id=v_org and h.case_id=p_case and h.brief_id=v_working for update;
 select c.case_revision into v_case_rev from caseproof.cases c where c.id=p_case;
 select e.payload->'entries',e.revision into v_register,v_exhibit_rev
 from caseproof._m1_exhibit_heads e where e.org_id=v_org and e.case_id=p_case;
 if v_case_rev is null or v_case_rev<1 or v_exhibit_rev is null or v_exhibit_rev<1
 then return jsonb_build_object('ok',false,'error','invalid'); end if;
 -- request replay first: an identical recorded request replays regardless of
 -- the head revision the caller computed against; any difference conflicts
 select e.version_id into v_replay_version from caseproof._m2_brief_events e
 where e.org_id=v_org and e.case_id=p_case and e.brief_id=v_working and e.request_id=p_request;
 if found then
   if exists(select 1 from caseproof._m2_brief_versions v
     where v.org_id=v_org and v.case_id=p_case and v.brief_id=v_working
       and v.version_id=v_replay_version and v.version_id=p_version
       and v.document_id=p_document and v.document_version_id=p_document_version
       and v.vault_intent_id=v_intent and v.document_role=p_role
       and v.representation_sha256=p_representation_sha and v.graph_sha256=p_graph_sha)
   then return jsonb_build_object('ok',true,'replay',true,'revision',v_head.revision); end if;
   return jsonb_build_object('ok',false,'error','conflict'); end if;
 if v_head.revision<>p_expected then return jsonb_build_object('ok',false,'error','conflict','revision',v_head.revision); end if;
 if v_head.revision>0 then
   perform 1 from caseproof._m2_brief_versions v
   where v.org_id=v_org and v.case_id=p_case and v.brief_id=v_working
     and v.version_id=v_head.version_id and v.version_id<>p_version
     and v.document_version_id<>p_document_version;
   if not found then return jsonb_build_object('ok',false,'error','invalid'); end if;
 end if;
 -- a version id names one version per case: it can never migrate to another
 -- brief head, otherwise version-id-keyed readers become ambiguous
 if exists(select 1 from caseproof._m2_brief_versions v
   where v.org_id=v_org and v.case_id=p_case and v.version_id=p_version
     and v.brief_id<>v_working)
 then return jsonb_build_object('ok',false,'error','invalid'); end if;

 for v_ref in select value from jsonb_array_elements(p_references) loop
   if jsonb_typeof(v_ref)<>'object' or not (v_ref ?& array['reference_id','exhibit_label','exact_quote'])
   or ((v_ref ? 'pdf_page') and jsonb_typeof(v_ref->'pdf_page') not in ('number','null'))
   or jsonb_typeof(v_ref->'reference_id')<>'string'
   or length(v_ref->>'reference_id') not between 1 and 128
   or jsonb_typeof(v_ref->'exhibit_label')<>'string'
   or length(v_ref->>'exhibit_label') not between 1 and 160
   or jsonb_typeof(v_ref->'exact_quote')<>'string' or v_ref->>'exact_quote'=''
   or length(v_ref->>'exact_quote')>4000
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
   v_label:=lower(v_ref->>'exhibit_label'); v_quote:=v_ref->>'exact_quote'; v_ok:=false;
   for v_entry in select value from jsonb_array_elements(coalesce(v_register,'[]'::jsonb)) loop
     if jsonb_typeof(v_entry)<>'object' or jsonb_typeof(v_entry->'confirmed')<>'boolean'
     or (v_entry->>'confirmed')::boolean is not true then continue; end if;
     if lower(coalesce(v_entry->>'display_label',''))<>v_label
     and not (jsonb_typeof(v_entry->'aliases')='array'
              and exists(select 1 from jsonb_array_elements_text(v_entry->'aliases') a where lower(a)=v_label))
     then continue; end if;
     select (p->>'version_id')::uuid into v_entry_version
     from jsonb_array_elements(coalesce(v_entry->'pages','[]'::jsonb)) p limit 1;
     if v_entry_version is null then continue; end if;
     select s.representation into v_entry_rep from caseproof._dev_journey_sources s
     where s.org_id=v_org and s.case_id=p_case and s.version_id=v_entry_version;
     if v_entry_rep is null or position(v_quote in v_entry_rep)=0 then continue; end if;
     v_pdf_page:=v_ref->'pdf_page';
     if v_pdf_page is not null and jsonb_typeof(v_pdf_page)='number' then
       if v_pdf_page::numeric<>trunc(v_pdf_page::numeric)
       or (v_pdf_page::numeric)<1 or (v_pdf_page::numeric)>100000
       or not exists(select 1 from jsonb_array_elements(v_entry->'pages') p
                     where (p->>'pdf_page')::numeric=v_pdf_page::numeric)
       then return jsonb_build_object('ok',false,'error','invalid'); end if;
     end if;
     v_ok:=true; exit;
   end loop;
   if not v_ok then return jsonb_build_object('ok',false,'error','invalid'); end if;
   if v_ref->>'reference_id'=any(v_ref_ids) then return jsonb_build_object('ok',false,'error','invalid'); end if;
   v_ref_ids:=array_append(v_ref_ids,v_ref->>'reference_id');
 end loop;

 for v_ast in select value from jsonb_array_elements(p_assertions) loop
   if jsonb_typeof(v_ast)<>'object'
   or not (v_ast ?& array['claim_id','reference_id','text_start','text_end','assertion_text','kind','fact_role','language','source_language'])
   or jsonb_typeof(v_ast->'claim_id')<>'string' or length(v_ast->>'claim_id') not between 1 and 160
   or jsonb_typeof(v_ast->'reference_id')<>'string' or not (v_ast->>'reference_id'=any(v_ref_ids))
   or jsonb_typeof(v_ast->'text_start')<>'number' or jsonb_typeof(v_ast->'text_end')<>'number'
   or (v_ast->>'text_start')::numeric<>trunc((v_ast->>'text_start')::numeric)
   or (v_ast->>'text_end')::numeric<>trunc((v_ast->>'text_end')::numeric)
   or (v_ast->>'text_start')::numeric<0
   or (v_ast->>'text_end')::numeric<=(v_ast->>'text_start')::numeric
   or (v_ast->>'text_end')::numeric>length(p_representation)
   or (v_ast->>'text_start')::numeric>2147483647 or (v_ast->>'text_end')::numeric>2147483647
   or jsonb_typeof(v_ast->'assertion_text')<>'string'
   or v_ast->>'assertion_text'<>substring(p_representation from (v_ast->>'text_start')::integer+1
                                          for ((v_ast->>'text_end')::integer-(v_ast->>'text_start')::integer))
   or v_ast->>'kind' not in ('money','date')
   or v_ast->>'fact_role' not in ('payment','due','delivery','invoice')
   or v_ast->>'language' not in ('nl','fr','en')
   or v_ast->>'source_language' not in ('nl','fr','en')
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
 end loop;

 v_new_rev:=v_head.revision+1;
 insert into caseproof._m2_brief_versions(org_id,case_id,brief_id,version_id,revision,parent_version_id,
   document_id,document_version_id,vault_intent_id,original_sha256,representation_sha256,parser_id,
   representation,document_role,graph_sha256,case_revision,exhibit_revision,actor_id,created_at)
 values(v_org,p_case,v_working,p_version,v_new_rev,v_head.version_id,p_document,p_document_version,
        v_intent,v_original_sha,p_representation_sha,p_parser_id,p_representation,p_role,p_graph_sha,
        v_case_rev,v_exhibit_rev,v_actor,v_now);
 insert into caseproof._m2_brief_references(org_id,case_id,brief_id,version_id,reference_order,
   reference_id,exhibit_label,exact_quote,pdf_page)
 select v_org,p_case,v_working,p_version,ord.rnk-1,ord.value->>'reference_id',ord.value->>'exhibit_label',
        ord.value->>'exact_quote',
        case when jsonb_typeof(ord.value->'pdf_page')='number' then (ord.value->>'pdf_page')::integer end
 from jsonb_array_elements(p_references) with ordinality as ord(value,rnk);
 insert into caseproof._m2_brief_assertions(org_id,case_id,brief_id,version_id,claim_order,claim_id,
   reference_id,text_start,text_end,assertion_text,kind,fact_role,language,source_language)
 select v_org,p_case,v_working,p_version,ord.rnk-1,ord.value->>'claim_id',ord.value->>'reference_id',
        (ord.value->>'text_start')::integer,(ord.value->>'text_end')::integer,ord.value->>'assertion_text',
        ord.value->>'kind',ord.value->>'fact_role',ord.value->>'language',ord.value->>'source_language'
 from jsonb_array_elements(p_assertions) with ordinality as ord(value,rnk);
 insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,action,
   event_schema_version,correlation_id,input_sha256_hex)
 values(v_audit,v_org,p_case,'human',v_actor,'m2_brief_graph_publish','v1',p_request,p_graph_sha);
 insert into caseproof._m2_brief_events(org_id,case_id,brief_id,revision,request_id,actor_id,
   version_id,graph_sha256,expected_revision,audit_id,created_at)
 values(v_org,p_case,v_working,v_new_rev,p_request,v_actor,p_version,p_graph_sha,p_expected,v_audit,v_now);
 update caseproof._m2_brief_heads set version_id=p_version,revision=v_new_rev
 where org_id=v_org and case_id=p_case and brief_id=v_working
   and version_id is not distinct from v_head.version_id;
 if not found then return jsonb_build_object('ok',false,'error','conflict'); end if;
 return jsonb_build_object('ok',true,'replay',false,'revision',v_new_rev);
end $$;
revoke all on function public.caseproof_signed_publish_uploaded(uuid,uuid,uuid,uuid,bigint,uuid,uuid,text,text,text,text,jsonb,jsonb,text,text) from public,anon;
grant execute on function public.caseproof_signed_publish_uploaded(uuid,uuid,uuid,uuid,bigint,uuid,uuid,text,text,text,text,jsonb,jsonb,text,text) to authenticated;
