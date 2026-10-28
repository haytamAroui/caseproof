"use strict";
/* ClearBrief development-only lawyer workspace: no fake data or browser token storage. */
(() => {
  const $ = id => document.getElementById(id);
  const state = {session:null, external:false, caseId:"", briefId:"", inventory:null, check:null,
    review:null, selected:null, previewReady:false, pending:null, busy:false, loading:false, generation:0, previewSeq:0, publishable:null};
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  const sha = /^[0-9a-f]{64}$/;
  const el = (tag, content, className) => {
    const node = document.createElement(tag);
    node.textContent = String(content ?? "");
    if (className) node.className = className;
    return node;
  };
  const label = value => String(value || "").replaceAll("_"," ");
  function notice(message, tone="") {
    $("notice").textContent = message; $("notice").className = "notice " + tone;
  }
  const path = () => "/v2/matters/" + encodeURIComponent(state.caseId) +
    "/briefs/" + encodeURIComponent(state.briefId);
  async function bearer() {
    if (!state.session) throw Error("no_session");
    const token = await state.session.getBearer();
    if (typeof token !== "string" || !token || token.length > 8192 || /[\r\n]/.test(token))
      throw Error("invalid_session");
    return token;
  }
  async function api(url, options={}) {
    const token = await bearer();
    const method = options.method || "GET";
    const headers = {Authorization:"Bearer " + token, ...(options.json ? {"Content-Type":"application/json"} : {})};
    const response = await fetch(url, {
      method, headers, credentials:"omit", redirect:"error", cache:"no-store",
      body: options.json ? JSON.stringify(options.json) : options.body,
    });
    if (!response.ok) {
      const err = Error(response.status === 401 ? "session_expired" :
        response.status === 403 || response.status === 404 ? "not_authorized" :
        response.status === 409 ? "stale_revision" : "service_unavailable");
      err.code=response.status; throw err;
    }
    return options.raw ? response : response.json();
  }
  function clearView() {
    state.inventory=null; state.check=null; state.review=null; state.selected=null; state.previewReady=false; state.pending=null;
    state.previewSeq+=1;state.loading=false;
    $("check-scope").textContent="Check source scope not assessed.";
    $("workspace").hidden=true; $("sources").replaceChildren(); $("observations").replaceChildren();
    $("search-results").replaceChildren(); $("source-preview").textContent="";
    $("review-history").replaceChildren(); $("selected").textContent="Select an observation.";
    $("save-review").disabled=true;
  }
  function statusFor(err) {
    if (err?.message === "session_expired" || err?.message === "invalid_session") return "Session expired. Sign in again.";
    if (err?.message === "not_authorized") return "This matter, source or review is not authorized for the current user.";
    if (err?.message === "stale_revision") return "The source or review changed. Refresh before trying again.";
    return "This operation is unavailable. Check the configured service and current permissions.";
  }
  async function authenticate() {
      if(state.session) { await bearer(); return state.session; }
      const generation=state.generation;
      let session;
      if (window.caseproofSession && typeof window.caseproofSession.getBearer === "function") {
        session=window.caseproofSession; state.external=true;
      } else {
        if (!state.publishable) throw Error("config_unavailable");
        const email=$("email").value.trim(), password=$("password").value;
        if (!email || !password) throw Error("credentials_required");
        const response=await fetch("https://ldwmocpxwskvhoojndrd.supabase.co/auth/v1/token?grant_type=password",{
          method:"POST",redirect:"error",credentials:"omit",cache:"no-store",
          headers:{"Content-Type":"application/json",apikey:state.publishable},
          body:JSON.stringify({email,password}),
        });
        const data=await response.json();
        if (!response.ok || typeof data.access_token !== "string" || !data.access_token)
          throw Error("invalid_session");
        let token=data.access_token, expiresAt=Date.now()+(Math.max(0,data.expires_in||0)*1000);
        session={getBearer:async()=>{if(Date.now()>=expiresAt-15000)throw Error("session_expired");return token;},
          clear:()=>{token="";expiresAt=0;}};
        state.external=false;
      }
      if(generation!==state.generation){session.clear?.();throw Error("session_expired");}
      state.session=session;
      $("password").value="";$("signout").hidden=false;
      return session;
  }
  async function startSession(evt) {
    evt.preventDefault();
    const caseId=$("case-id").value.trim(), briefId=$("brief-id").value.trim();
    if (!UUID.test(caseId)||!UUID.test(briefId)) {notice("Enter canonical matter and brief-version UUIDs.","danger");return;}
    $("connect").disabled=true;$("find-matters").disabled=true;
    try {
      const session=await authenticate();
      if(state.external && (session.caseId!==caseId || session.briefVersionId!==briefId))
        throw Error("provider_mismatch");
      state.caseId=caseId;state.briefId=briefId;
      clearView(); await load();
    } catch(err) {
      if(err.message==="provider_mismatch")notice("The connected Word session belongs to a different matter/brief.","danger");
      else if(err.message==="credentials_required")notice("Enter your development Auth email and password.","danger");
      else notice(statusFor(err),"danger");
    } finally {$("connect").disabled=false;$("find-matters").disabled=false;}
  }
  async function findMatters() {
    const generation=state.generation;
    $("connect").disabled=true;$("find-matters").disabled=true;
    const node=$("matter-options");node.replaceChildren();
    try {
      await authenticate();
      const data=await api("/dev/clearbrief/matters");
      if(generation!==state.generation || !state.session)return;
      if(data.schema!=="caseproof-clearbrief-matters-v1" || !Array.isArray(data.matters))throw Error("invalid_schema");
      if(!data.matters.length)node.append(el("p","No matters are currently available to this account.","small"));
      for(const matter of data.matters){
        if(!UUID.test(matter.case_id))throw Error("invalid_schema");
        if(state.external && matter.case_id!==state.session.caseId)continue;
        const button=el("button","Matter "+matter.case_id+" · "+label(matter.state),"source-item");
        button.type="button";
        button.addEventListener("click",()=>{$("case-id").value=matter.case_id;});
        node.append(button);
      }
      notice("Select a matter and enter its brief version to continue.");
    } catch(error){
      if(generation===state.generation)notice(error.message==="credentials_required" ?
        "Enter your development Auth email and password." : statusFor(error),"danger");
    } finally {$("connect").disabled=false;$("find-matters").disabled=false;}
  }
  function renderSources() {
    const node=$("sources");node.replaceChildren();
    const rows=state.inventory?.rows;
    if(!Array.isArray(rows)){node.append(el("p","Evidence library is not wired for this matter.","empty"));$("source-count").textContent="—";return;}
    $("source-count").textContent=String(rows.length);
    if(!rows.length)node.append(el("p","No authorized sources are indexed in this matter.","empty"));
    for(const row of rows) {
      const button=el("button","","source-item");button.type="button";
      button.append(el("div",row.source_id||"Unnamed source"));
      button.firstChild.append(el("span",(row.media_type||"unknown format")+" · "+(row.pages?.length??0)+" page states"));
      button.append(el("span",row.status||"unknown","state"));
      button.addEventListener("click",()=>selectSource(row));
      node.append(button);
    }
    const complete=state.inventory?.complete===true;
    $("coverage").textContent=complete?"Inventory complete":"Partial / unknown";
  }
  async function selectSource(row) {
    if(state.busy||state.loading)return;
    const seq=++state.previewSeq, generation=state.generation;
    $("source-preview").textContent="Loading source preview…";
    state.selected=null;state.previewReady=false;$("save-review").disabled=true;
    try {
      const data=await api(path()+"/sources/"+encodeURIComponent(row.source_id));
      if(generation!==state.generation||seq!==state.previewSeq||state.selected!==null)return;
      if(data.schema!=="caseproof-clearbrief-brief-source-preview-v1" || data.row?.source_id!==row.source_id ||
        data.case_id!==state.caseId || data.brief_version_id!==state.briefId)
        throw Error("invalid_schema");
      if(!row.version_id || !row.representation_id || !sha.test(row.original_sha256 || "") ||
        data.row.version_id!==row.version_id || data.row.original_sha256!==row.original_sha256 ||
        data.row.representation_id!==row.representation_id)
        throw Error("source_version_mismatch");
      const preview=$("source-preview");preview.replaceChildren();
      preview.append(el("strong",row.source_id));
      preview.append(el("p","SHA-256: "+row.original_sha256,"small mono"));
      preview.append(el("p",(row.warnings||[]).join(" · ")||"No recorded parser warnings","small"));
      preview.append(el("p",data.text||"No available represented text."));
      const download=el("button","Download verified original","secondary");download.type="button";
      download.addEventListener("click",()=>downloadOriginal(row));
      preview.append(download);
      $("selected").textContent="Viewing source only. Select an observation to record a review.";
    } catch(error){if(generation===state.generation&&seq===state.previewSeq&&state.selected===null)
      $("source-preview").textContent=error?.message==="source_version_mismatch" ?
        "Source version, digest or representation changed. Refresh the inventory before viewing or downloading." :
        statusFor(error);}
  }
  async function downloadOriginal(row) {
    const generation=state.generation;
    try {
      const response=await api(path()+"/evidence/"+encodeURIComponent(row.source_id)+
        "/versions/"+encodeURIComponent(row.version_id)+"/original",{raw:true});
      const blob=await response.blob();
      if(generation!==state.generation||!state.session)return;
      if(blob.size>20*1024*1024||blob.size===0)throw Error("invalid_original");
      const url=URL.createObjectURL(blob),a=document.createElement("a");
      a.href=url;a.download="caseproof-original";a.rel="noopener";a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      notice("Original downloaded. Its source identity must still be independently validated.","ok");
    }catch(error){if(generation===state.generation)notice(statusFor(error),"danger");}
  }
  function allObservations() {
    if(!state.check)return [];
    return [
      ...(state.check.citation_observations||[]).map(a=>({
        id:"citation:"+a.reference_id,kind:"Citation",state:a.state,source:a.source_id,
        version:a.source_version_id, sourceSha:a.source_sha256, representation:a.representation_id,
        span:a.text_start===null?"Unresolved anchor":"Offsets "+a.text_start+"–"+a.text_end,
        raw:a,
      })),
      ...(state.check.factual_observations||[]).map(a=>({
        id:"fact:"+a.claim_id,kind:"Factual value",state:a.state||a.status||"unknown",
        source:a.source_id,version:a.source_version_id,sourceSha:a.source_sha256,
        representation:a.representation_id,span:"Version-bound candidate",raw:a,
      })),
    ];
  }
  function renderChecks() {
    const node=$("observations");node.replaceChildren();
    const values=allObservations();
    const scope=$("check-scope");scope.replaceChildren();
    if(state.check){
      const c=state.check, declared=Array.isArray(c.declared)?c.declared:[],
        processed=Array.isArray(c.processed)?c.processed:[],
        excluded=Array.isArray(c.excluded)?c.excluded:[],
        incomplete=Array.isArray(c.incomplete)?c.incomplete:[];
      const partial=excluded.length>0||incomplete.length>0||declared.length!==processed.length;
      scope.className="check-scope"+(partial?" partial":"");
      scope.append(el("strong","Check scope · "+processed.length+" processed of "+declared.length+" declared"));
      scope.append(el("span",excluded.length+" excluded · "+incomplete.length+" incomplete · "+
        (partial?"NOT fully assessed":"declared scope processed")));
      if(partial){
        const names=arr=>arr.slice(0,6).map(pair=>Array.isArray(pair)?pair.join(" / "):String(pair)).join("; ");
        if(excluded.length)scope.append(el("small","Excluded: "+names(excluded)));
        if(incomplete.length)scope.append(el("small","Incomplete: "+names(incomplete)));
      }
    }else{
      scope.className="check-scope partial";
      scope.textContent="Check not available. Declared sources and exclusions have not been assessed.";
    }
    $("citation-count").textContent=String(state.check?.citation_observations?.length??0);
    $("fact-count").textContent=String(state.check?.factual_observations?.length??0);
    if(!state.check){node.append(el("p","Check is unavailable. No success or correctness is implied.","empty"));return;}
    if(!values.length){node.append(el("p","No observations in this declared scope. This is not a certification.","empty"));return;}
    for(const item of values){
      const button=el("button","","observation");button.type="button";
      button.setAttribute("aria-pressed",String(state.selected?.id===item.id));
      button.append(el("span",item.kind+" / "+label(item.state),"tag"));
      button.append(el("strong",item.id.replace("citation:","Reference ").replace("fact:","Fact ")));
      button.append(el("small",(item.source||"No confirmed source")+" · "+item.span));
      button.addEventListener("click",()=>{if(state.loading||state.busy||state.pending)return;
        state.selected=item;renderChecks();renderSelected();});
      node.append(button);
    }
  }
  function renderSelected(){
    const selected=state.selected;
    $("selected").replaceChildren();
    state.previewReady=false;
    $("save-review").disabled=true;
    if(!selected){$("selected").textContent="Select a finding to inspect and review.";return;}
    $("selected").append(el("strong",selected.kind+" · "+selected.id));
    $("selected").append(el("p","Check state: "+label(selected.state)));
    $("selected").append(el("p","Source: "+(selected.source||"not resolved"),"small"));
    $("selected").append(el("p","This result is a candidate observation, not a legal finding.","small"));
    // A claim may be reviewed only against the exact checked source version,
    // digest and representation, never a newer catalog entry sharing its source_id.
    if(!selected.source){
      $("source-preview").textContent="No source resolved for this observation. Evidence support is unknown.";
      state.previewReady=true;$("save-review").disabled=!state.review||state.loading||state.busy;return;
    }
    const rows=state.inventory?.rows||[];
    const matches=rows.filter(r=>r.source_id===selected.source &&
      r.version_id===selected.version && r.original_sha256===selected.sourceSha &&
      r.representation_id===selected.representation);
    if(matches.length!==1){
      $("source-preview").textContent="The checked source version, digest or representation cannot be uniquely reopened. Refresh; review is blocked.";
      return;
    }
    $("source-preview").textContent="Verifying exact source version and representation…";
    void selectPreviewOnly(matches[0],selected.id);
  }
  async function selectPreviewOnly(row,selectedId){
    const seq=++state.previewSeq,generation=state.generation;
    const current=()=>generation===state.generation && seq===state.previewSeq &&
      state.selected?.id===selectedId && !state.loading && state.session;
    try{
      const d=await api(path()+"/sources/"+encodeURIComponent(row.source_id));
      if(!current())return;
      if(d.schema!=="caseproof-clearbrief-brief-source-preview-v1"||d.row?.source_id!==row.source_id||
        d.case_id!==state.caseId||d.brief_version_id!==state.briefId||
        d.row.version_id!==row.version_id||
        d.row.original_sha256!==row.original_sha256||
        d.row.representation_id!==row.representation_id ||
        d.row.version_id!==state.selected.version ||
        d.row.original_sha256!==state.selected.sourceSha ||
        d.row.representation_id!==state.selected.representation)
        throw Error("source_version_mismatch");
      $("source-preview").textContent=d.text||"Source has no available text representation.";
      state.previewReady=true;$("save-review").disabled=!state.review||state.busy||state.loading;
    }catch(error){if(current()){
      state.previewReady=false;$("save-review").disabled=true;
      $("source-preview").textContent=error?.message==="source_version_mismatch"?
        "Source version/representation mismatch. This finding cannot be reviewed from this preview.":
        statusFor(error);
    }}
  }
  function renderReview(){
    const rev=state.review;
    $("review-count").textContent=rev?String(rev.revision):"—";
    const node=$("review-history");node.replaceChildren();
    if(!rev){node.append(el("p","Durable review is not connected or permission was denied.","empty"));return;}
    const decisions=Array.isArray(rev.decisions)?rev.decisions:[];
    node.append(el("h4","Version-bound review history ("+decisions.length+")"));
    for(const d of decisions){
      const entry=el("div","","history-entry");
      entry.append(el("strong",label(d.disposition)+" · "+d.observation_id));
      entry.append(el("p",d.rationale));
      node.append(entry);
    }
  }
  async function load(){
    if(state.busy||state.pending){notice("Resolve the pending review save before refreshing this snapshot.","danger");return;}
    const generation=++state.generation;
    state.previewSeq+=1;state.loading=true;state.check=null;state.review=null;state.previewReady=false;
    state.inventory=null;state.selected=null;
    $("save-review").disabled=true;
    $("review-form").setAttribute("aria-busy","true");
    $("selected").textContent="Checking current brief and permissions…";
    $("source-preview").textContent="Source preview cleared while the current scope reloads.";
    $("observations").replaceChildren();$("review-history").replaceChildren();
    $("check-scope").textContent="Checking current source denominator…";
    $("workspace").hidden=false;
    $("matter-meta").textContent="Matter "+state.caseId+" · brief "+state.briefId;
    notice("Checking private access and current evidence scope…");
    try{
      const checked=await api(path()+"/check",{method:"POST"});
      if(generation!==state.generation)return;
      if(checked.schema!=="caseproof-m2-check-headless-v1" || checked.case_id!==state.caseId ||
        checked.brief_version_id!==state.briefId || !sha.test(checked.snapshot_hash))
        throw Error("invalid_schema");
      state.check=checked;
      notice("Authorized check completed. Findings remain unreviewed until saved.","ok");
    }catch(error){if(generation!==state.generation)return;
      state.check=null;notice(statusFor(error),"danger");}
    if(generation!==state.generation)return;
    try {
      const inv=await api(path()+"/sources");
      if(generation===state.generation)
        state.inventory=(inv.schema==="caseproof-clearbrief-brief-sources-v1" &&
          inv.case_id===state.caseId && inv.brief_version_id===state.briefId)?inv:null;
    }catch{if(generation!==state.generation)return;state.inventory=null;}
    try {
      const review=await api(path()+"/review");
      if(generation===state.generation && review.schema==="caseproof-clearbrief-review-v1" &&
        review.case_id===state.caseId && review.snapshot_hash===state.check?.snapshot_hash)
        state.review=review;
      else state.review=null;
    }catch{if(generation!==state.generation)return;state.review=null;}
    if(generation!==state.generation)return;
    state.loading=false;$("review-form").removeAttribute("aria-busy");
    state.selected=null;
    renderSources();renderChecks();renderReview();renderSelected();
  }
  async function submitReview(evt){
    evt.preventDefault();
    if(state.busy||state.loading||!state.previewReady||!state.selected||!state.check||!state.review)return;
    const generation=state.generation;
    const rationale=$("rationale").value.trim();
    if(!rationale){notice("A review rationale is required.","danger");return;}
    if(!state.pending)state.pending={
      request_id:crypto.randomUUID(),snapshot_hash:state.check.snapshot_hash,
      observation_id:state.selected.id,expected_revision:state.review.revision,
      disposition:$("disposition").value,rationale,
    };
    const submit=$("save-review");submit.disabled=true;state.busy=true;
    try{
      const receipt=await api(path()+"/review",{method:"POST",json:state.pending});
      if(generation!==state.generation)return;
      if(receipt.schema!=="caseproof-clearbrief-review-receipt-v1" ||
        receipt.snapshot_hash!==state.check.snapshot_hash)throw Error("invalid_receipt");
      state.pending=null;$("rationale").value="";
      const review=await api(path()+"/review");
      if(generation!==state.generation)return;
      if(review.schema!=="caseproof-clearbrief-review-v1"||review.revision!==receipt.revision)
        throw Error("reload_required");
      state.review=review;renderReview();
      notice("Review saved at revision "+receipt.revision+". This does not approve publication.","ok");
    }catch(error){
      if(generation!==state.generation)return;
      notice("Save outcome not confirmed. Keep the same request and retry; do not edit it. "+statusFor(error),"danger");
    }finally{state.busy=false;if(generation===state.generation)
      submit.disabled=!state.previewReady||!state.selected||!state.review;}
  }
  async function search(){
    const generation=state.generation;
    const query=$("query").value.trim(),node=$("search-results");node.replaceChildren();
    if(query.length<2){node.append(el("p","Enter at least two characters.","small"));return;}
    try{
      const d=await api(path()+"/evidence/search",{method:"POST",json:{query}});
      if(generation!==state.generation||!state.session)return;
      if(d.schema!=="caseproof-evidence-search-v1"||d.case_id!==state.caseId ||
         d.brief_version_id!==state.briefId||!Array.isArray(d.hits))throw Error("invalid_schema");
      node.append(el("p",d.coverage+" coverage · "+d.hits.length+" matches","small"));
      for(const h of d.hits){
        const item=el("div","","result-item");
        item.append(el("strong",h.source_id+" · "+(h.locator||"unmapped")));
        item.append(el("p",h.text));
        const button=el("button","Inspect source");button.type="button";
        button.addEventListener("click",()=>{const r=state.inventory?.rows?.find(x=>x.source_id===h.source_id);
          if(r)void selectSource(r);else notice("Matching source is not in the authorized inventory.","danger");});
        item.append(button);node.append(item);
      }
      if(!d.hits.length)node.append(el("p","No match in the searched scope; review exclusions and incomplete sources.","small"));
    }catch(error){if(generation===state.generation)node.append(el("p",statusFor(error),"error"));}
  }
  async function upload(evt){
    evt.preventDefault();
    const generation=state.generation;
    const documentId=$("document-id").value.trim(),versionId=$("version-id").value.trim();
    const file=$("original-file").files?.[0];
    if(!UUID.test(documentId)||!UUID.test(versionId)||!file||file.size<=0||file.size>20*1024*1024){
      notice("Select an existing exact document/version UUID and an original under 20 MiB.","danger");return;
    }
    const mime={txt:"text/plain",pdf:"application/pdf",docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg"}[file.name.split(".").pop()?.toLowerCase()];
    if(!mime){notice("This original format is unsupported.","danger");return;}
    $("upload").disabled=true;
    try{
      const token=await bearer();
      const response=await fetch("/dev/signed/matters/"+encodeURIComponent(state.caseId)+
        "/documents/"+encodeURIComponent(documentId)+"/versions/"+encodeURIComponent(versionId)+"/original",{
          method:"PUT",credentials:"omit",redirect:"error",cache:"no-store",
          headers:{"Authorization":"Bearer "+token,"Content-Type":mime},body:file,
        });
      if(generation!==state.generation||!state.session)return;
      if(response.status!==201)throw Error("unavailable");
      notice("Original uploaded to its pre-registered version. Reopen the verified source after indexing.","ok");
      await load();
    }catch(error){if(generation===state.generation)
      notice("Upload was denied or its outcome is unknown. Verify the exact version before retrying.","danger");}
    finally{$("upload").disabled=false;}
  }

  // M1/M2 genuinely authored development journey; no browser-side fixture or fake source.
  const journey = {caseId:"", source:null, brief:null, snapshot:null, observation:null, revision:0, pending:null, busy:false};
  function journeyOutput(message, value) {
    $("journey-result").textContent=message;
    if(value!==undefined)$("journey-state").textContent=JSON.stringify(value,null,2);
  }
  async function journeyOrganizations() {
    try {
      await authenticate();
      const result=await api("/dev/live/create-organizations");
      if(result.schema!=="caseproof-dev-create-orgs-v1"||!Array.isArray(result.organizations))
        throw Error("invalid_schema");
      const select=$("journey-org");select.replaceChildren();
      for(const org of result.organizations){
        if(!UUID.test(org.org_id))throw Error("invalid_schema");
        const option=document.createElement("option");option.value=org.org_id;
        option.textContent=org.name+" · "+org.org_id;select.append(option);
      }
      journeyOutput(result.organizations.length ?
        "Choose an authorized organization to create a private matter." :
        "No active organization grants case:create. Contact your development administrator.");
    }catch(e){journeyOutput(statusFor(e));}
  }
  async function journeyCreate(event) {
    event.preventDefault();
    if(journey.busy)return;
    journey.busy=true;
    const org=$("journey-org").value,name=$("journey-matter-name").value.trim();
    try{
      if(!UUID.test(org)||!name)throw Error("invalid_data");
      await authenticate();
      const result=await api("/dev/live/matters",{method:"POST",json:{
        org_id:org,name,request_id:crypto.randomUUID()}});
      if(!UUID.test(result.case_id))throw Error("invalid_schema");
      journey.caseId=result.case_id;journey.source=null;journey.brief=null;
      journey.snapshot=null;journey.observation=null;journey.revision=0;journey.pending=null;
      $("case-id").value=result.case_id;
      journeyOutput("Matter created with a private owner grant and atomic audit.",result);
    }catch(e){journeyOutput(statusFor(e));}
    finally{journey.busy=false;}
  }
  async function journeyIngest(event){
    event.preventDefault();
    if(journey.busy)return;
    journey.busy=true;
    try{
      const caseId=journey.caseId || $("case-id").value.trim(),file=$("journey-file").files?.[0];
      if(!UUID.test(caseId)||!file||file.size<1||file.size>1048576||
         !file.name.toLowerCase().endsWith(".txt"))throw Error("invalid_data");
      await authenticate();
      const bytes=new Uint8Array(await file.arrayBuffer());
      new TextDecoder("utf-8",{fatal:true}).decode(bytes);
      const digest=new Uint8Array(await crypto.subtle.digest("SHA-256",bytes));
      const hex=Array.from(digest,b=>b.toString(16).padStart(2,"0")).join("");
      const reg=await api("/dev/live/matters/"+caseId+"/sources",{method:"POST",json:{
        filename:file.name,sha256:hex,byte_length:bytes.length,media_type:"text/plain",
        request_id:crypto.randomUUID()}});
      let binary="";for(let i=0;i<bytes.length;i+=8192)
        binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
      const route="/dev/live/matters/"+caseId+"/sources/"+reg.document_id+"/"+reg.version_id;
      const uploaded=await api(route+"/upload",{method:"POST",json:{content_base64:btoa(binary)}});
      if(!uploaded.verified||uploaded.sha256!==hex)throw Error("unverified_upload");
      const ingested=await api(route+"/ingest?request_id="+crypto.randomUUID(),{method:"POST"});
      if(ingested.original_sha!==hex||ingested.exhibit_confirmed!==false)
        throw Error("unverified_ingestion");
      journey.caseId=caseId;journey.source=ingested;
      $("case-id").value=caseId;
      journeyOutput("Verified original and immutable UTF-8 source representation.",ingested);
    }catch(e){journeyOutput("TXT ingestion not confirmed. "+statusFor(e));}
    finally{journey.busy=false;}
  }
  async function journeyBrief(event){
    event.preventDefault();
    if(journey.busy)return;
    journey.busy=true;
    try{
      const caseId=journey.caseId||$("case-id").value.trim();
      if(!UUID.test(caseId))throw Error("invalid_data");
      let source=journey.source;
      if(!source){
        const data=await api("/dev/live/matters/"+caseId+"/state");
        source=data.sources?.[0];if(!source)throw Error("missing_ingested_source");
      }
      const text=$("journey-draft").value,quote=$("journey-quote").value;
      if(!quote||!text.includes(quote)||!/[0-9]/.test(quote))throw Error("invalid_data");
      const result=await api("/dev/live/matters/"+caseId+"/briefs",{
        method:"POST",json:{source_version_id:source.version_id,text,quote,request_id:crypto.randomUUID()}});
      if(!UUID.test(result.brief_version_id))throw Error("invalid_schema");
      journey.caseId=caseId;journey.source=source;journey.brief=result;
      journey.snapshot=null;journey.revision=0;journey.pending=null;
      $("brief-id").value=result.brief_version_id;
      journeyOutput("Authored versioned brief saved. The factual check is still pending.",result);
    }catch(e){journeyOutput("Brief creation not confirmed. "+statusFor(e));}
    finally{journey.busy=false;}
  }
  async function journeyCheck(){
    if(journey.busy)return;
    journey.busy=true;
    try{
      const c=journey.caseId||$("case-id").value.trim();
      const b=journey.brief?.brief_version_id||$("brief-id").value.trim();
      if(!UUID.test(c)||!UUID.test(b))throw Error("invalid_data");
      const base="/dev/live/matters/"+c+"/briefs/"+b;
      const check=await api(base+"/check",{method:"POST"});
      if(!sha.test(check.snapshot_hash)||typeof check.outcome!=="string")throw Error("invalid_schema");
      journey.caseId=c;journey.brief={brief_version_id:b};
      journey.snapshot=check.snapshot_hash;journey.observation=check.observation_id;journey.revision=check.review_revision;
      journeyOutput("Deterministic source quote check completed; not a legal conclusion.",check);
    }catch(e){journeyOutput("Check unavailable. "+statusFor(e));}
    finally{journey.busy=false;}
  }
  async function journeyReview(event){
    event.preventDefault();
    if(journey.busy)return;
    journey.busy=true;
    try{
      if(!journey.snapshot||!journey.brief)throw Error("run_check_first");
      const base="/dev/live/matters/"+journey.caseId+"/briefs/"+journey.brief.brief_version_id;
      if(!journey.pending)journey.pending={
        snapshot_hash:journey.snapshot,observation_id:journey.observation,
        request_id:crypto.randomUUID(),expected_revision:journey.revision,
        disposition:$("journey-disposition").value,rationale:$("journey-rationale").value.trim()};
      const saved=await api(base+"/reviews",{method:"POST",json:journey.pending});
      if(saved.review_revision!==journey.revision+1&&!saved.replayed)
        throw Error("invalid_receipt");
      journey.revision=saved.review_revision;journey.pending=null;
      journeyOutput("Version-bound human review saved atomically.",saved);
    }catch(e){journeyOutput("Review outcome unknown; retry with the same request. "+statusFor(e));}
    finally{journey.busy=false;}
  }
  async function journeyReopen(){
    if(journey.busy)return;
    journey.busy=true;
    try{
      await authenticate();
      const c=journey.caseId||$("case-id").value.trim();
      if(!UUID.test(c))throw Error("invalid_data");
      const reopened=await api("/dev/live/matters/"+c+"/state");
      if(reopened.schema!=="dev-live-txt-v1")throw Error("invalid_schema");
      const b=reopened.briefs?.[0];
      if(b){
        const check=await api("/dev/live/matters/"+c+"/briefs/"+b.brief_version_id+"/check",{method:"POST"});
        const review=await api("/dev/live/matters/"+c+"/briefs/"+b.brief_version_id+"/reviews/"+check.snapshot_hash);
        journey.snapshot=check.snapshot_hash;journey.observation=check.observation_id;journey.revision=review.review_revision;
        journey.brief={brief_version_id:b.brief_version_id};
        $("brief-id").value=b.brief_version_id;
        reopened.review=review;reopened.check=check;
      }
      journey.caseId=c;journey.source=reopened.sources?.[0]||null;
      $("case-id").value=c;
      journeyOutput("Reopened matter, ingested text, authored brief and review directly from Supabase.",reopened);
    }catch(e){journeyOutput("Reopening not confirmed. "+statusFor(e));}
    finally{journey.busy=false;}
  }
  function signout(){
    state.generation+=1;state.previewSeq+=1;
    if(!state.external)state.session?.clear?.();
    state.session=null;state.external=false;state.caseId="";state.briefId="";
    Object.assign(journey,{caseId:"",source:null,brief:null,snapshot:null,observation:null,revision:0,pending:null,busy:false});
    $("journey-state").textContent="";
    $("matter-options").replaceChildren();
    $("password").value="";$("signout").hidden=true;clearView();notice("Session ended. No credentials were saved.");
  }
  async function init(){
    $("connection-form").addEventListener("submit",startSession);
    $("journey-find-orgs").addEventListener("click",journeyOrganizations);
    $("journey-create-form").addEventListener("submit",journeyCreate);
    $("journey-file-form").addEventListener("submit",journeyIngest);
    $("journey-brief-form").addEventListener("submit",journeyBrief);
    $("journey-check").addEventListener("click",journeyCheck);
    $("journey-review-form").addEventListener("submit",journeyReview);
    $("journey-reopen").addEventListener("click",journeyReopen);
    $("find-matters").addEventListener("click",findMatters);
    $("review-form").addEventListener("submit",submitReview);
    $("search").addEventListener("click",search);
    $("upload-form").addEventListener("submit",upload);
    $("signout").addEventListener("click",signout);
    $("refresh").addEventListener("click",()=>{void load();});
    $("recheck").addEventListener("click",()=>{void load();});
    if(window.caseproofSession?.getBearer){
      $("credentials").hidden=true;$("auth-mode").textContent="Connected host session";
      $("case-id").value=window.caseproofSession.caseId||"";
      $("brief-id").value=window.caseproofSession.briefVersionId||"";
      return;
    }
    try {
      const response=await fetch("/dev/clearbrief/config",{credentials:"omit",cache:"no-store"});
      const config=await response.json();
      if(response.ok&&config.schema==="caseproof-clearbrief-dev-config-v1"&&
         typeof config.publishable_key==="string"&&config.publishable_key.startsWith("sb_publishable_")){
        state.publishable=config.publishable_key;$("auth-mode").textContent="Supabase dev authentication";
      }else{
        $("auth-mode").textContent="Backend session required";$("credentials").hidden=true;
        $("connect").disabled=true;notice("No signed identity provider is configured. Connect a trusted host session.","danger");
      }
    }catch{ $("auth-mode").textContent="Backend session required";$("credentials").hidden=true;
      $("connect").disabled=true;notice("The signed identity provider is unavailable.","danger");}
  }
  void init();
})();


