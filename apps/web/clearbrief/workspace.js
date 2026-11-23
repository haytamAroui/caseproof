"use strict";
/* ClearBrief development-only lawyer workspace: no fake data or browser token storage. */
(() => {
  const $ = id => document.getElementById(id);
  const state = {session:null, external:false, caseId:"", briefId:"", inventory:null, check:null,
    review:null, selected:null, previewReady:false, pending:null, busy:false, loading:false, generation:0, previewSeq:0, publishable:null, justPublished:false,
    catalog:null, publishRevision:0, pageImageUrl:null, pageImageNode:null, pageZoomNode:null, pageZoomReturn:null, pageZoomKey:null};
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
  // Signed workbench (check/review on the signed adapters) when the host exposes it;
  // otherwise the legacy v2 routes. Chosen from /dev/clearbrief/config, never guessed.
  let signedWorkbench = false;
  const reviewPath = () => signedWorkbench
    ? "/dev/signed/matters/" + encodeURIComponent(state.caseId) + "/briefs/" + encodeURIComponent(state.briefId)
    : path();
  const LEGAL_LABEL={PASS:"in corpus",FAIL:"quotation not in article text",UNVERIFIED:"article absent from chosen corpus",UNDETERMINED:"cannot be decided"};
  async function loadLegalReferences(generation){
    const box=$("legal-refs");if(!box)return;box.replaceChildren();box.hidden=false;
    try{
      const d=await api(reviewPath()+"/legal-references");
      if(generation!==state.generation)return;
      if(d.schema!=="caseproof-signed-legal-references-v1"||d.brief_version_id!==state.briefId||!Array.isArray(d.references))throw Error("invalid_schema");
      box.append(el("h4","Cited legal articles"));
      if(d.corpus!=="configured"){box.append(el("p","No legal corpus is chosen for this matter: cited articles are not checked. Nothing was looked up online.","empty"));return;}
      box.append(el("p",d.references.length+" cited reference(s) checked against "+d.corpus_articles+" corpus article(s). "+d.note,"small"));
      for(const r of d.references){
        const item=el("div","","result-item");
        item.append(el("strong",r.status+" · "+(LEGAL_LABEL[r.status]||r.status)));
        item.append(el("p",r.raw_text,"small"));
        item.append(el("p","Reason: "+r.reason+(r.corpus_version?" · corpus version "+r.corpus_version:""),"small mono"));
        if(r.corpus_text_sha256)item.append(el("p","Corpus text SHA-256 "+r.corpus_text_sha256.slice(0,16)+"\u2026 · "+(r.corpus_source_uri||""),"small mono"));
        box.append(item);
      }
    }catch(error){if(generation===state.generation){box.replaceChildren();box.append(el("p","Legal references unavailable: "+statusFor(error),"error"));}}
  }
  const labelOf = (id) => (id && state.inventory?.labels?.[id]) || id;
  async function previewCorrection(evt) {
    evt.preventDefault();
    const generation = state.generation, out = $("correction-result");
    const selected = state.selected?.id, snapshot = state.check?.snapshot_hash;
    const before = $("correction-before").value, after = $("correction-after").value;
    if (!signedWorkbench || !selected || !sha.test(snapshot || "") || !before || !after) return;
    out.textContent = "Checking against the current verified representation…";
    try {
      const d = await api(reviewPath() + "/correction-preview", {method: "POST",
        json: {snapshot_hash: snapshot, observation_id: selected, before, after,
          rationale: $("rationale").value.trim() || "Correction proposed after review"}});
      if (generation !== state.generation) return;
      if (d.schema !== "caseproof-signed-correction-preview-v1" || d.persisted !== false ||
          d.invalidates_check_hash !== snapshot || !sha.test(d.proposed_text_sha256))
        throw Error("invalid_schema");
      out.textContent = "Preview only, nothing saved. Proposed text digest " +
        d.proposed_text_sha256.slice(0, 16) + "\u2026 It requires a new brief version and a new check.";
    } catch (error) {
      if (generation === state.generation)
        out.textContent = error && error.code === 409
          ? "The text is not found exactly once in the current checked version, or the check is out of date."
          : statusFor(error);
    }
  }
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
  const fidelityPanel=window.CaseProofFidelity?.mount({root:$("fidelity-panel"),
    api:async(url,options)=>{await authenticate();return api(url,options);},
    context:()=>({caseId:$("case-id").value.trim(),briefId:$("brief-id").value.trim()})});
  function closePageZoom() {
    const dialog = state.pageZoomNode;
    state.pageZoomNode = null;
    if (state.pageZoomKey) {
      document.removeEventListener("keydown", state.pageZoomKey);
      state.pageZoomKey = null;
    }
    const returnTo = state.pageZoomReturn;
    state.pageZoomReturn = null;
    if (dialog && dialog.parentNode) dialog.parentNode.removeChild(dialog);
    if (returnTo && returnTo.parentNode && typeof returnTo.focus === "function") returnTo.focus();
  }
  function openPageZoom(url, physical, returnTo) {
    closePageZoom();
    const dialog = el("div", "", "page-zoom");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-label", "Physical page " + physical + " rendering at full size");
    const bar = el("div", "", "page-zoom-bar");
    bar.append(el("p", "Physical page rendering of the verified original bytes · a rendering, not a verification. · page " + physical, "small"));
    const close = el("button", "Close", "secondary");
    close.type = "button";
    close.addEventListener("click", closePageZoom);
    bar.append(close);
    const scroller = el("div", "", "page-zoom-scroll");
    const img = new Image();
    img.alt = "Physical PDF page " + physical + " rendering of the verified original, full size";
    img.src = url;
    scroller.append(img);
    dialog.append(bar, scroller);
    dialog.addEventListener("click", event => { if (event.target === dialog) closePageZoom(); });
    state.pageZoomReturn = returnTo || null;
    state.pageZoomKey = event => { if (event && event.key === "Escape") closePageZoom(); };
    document.addEventListener("keydown", state.pageZoomKey);
    document.body.append(dialog);
    state.pageZoomNode = dialog;
    close.focus();
  }
  function revokePageImage() {
    closePageZoom();
    if (state.pageImageUrl) { URL.revokeObjectURL(state.pageImageUrl); state.pageImageUrl = null; }
    const node = state.pageImageNode;
    state.pageImageNode = null;
    if (node && node.parentNode) node.parentNode.removeChild(node);
  }
  function clearView() {
    revokePageImage();
    fidelityPanel?.clear();
    state.inventory=null; state.check=null; state.review=null; state.selected=null; state.previewReady=false; state.pending=null; state.showAll=false;
    state.previewSeq+=1;state.loading=false;
    $("check-scope").textContent="Check source scope not assessed.";
    $("workspace").hidden=true; $("connection").hidden=false; $("record").disabled=true;
    $("record-status").textContent="";
    $("sources").replaceChildren(); $("observations").replaceChildren();
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
      state.catalog=null;state.publishRevision=0;
      clearView(); await load(); void loadCatalog();
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
      button.append(el("div",labelOf(row.source_id)||"Unnamed source"));
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
      const data=await api(reviewPath()+"/sources/"+encodeURIComponent(row.source_id));
      if(generation!==state.generation||seq!==state.previewSeq||state.selected!==null)return;
      if(data.schema!=="caseproof-clearbrief-brief-source-preview-v1" || data.row?.source_id!==row.source_id ||
        data.case_id!==state.caseId || data.brief_version_id!==state.briefId)
        throw Error("invalid_schema");
      if(!row.version_id || !row.representation_id || !sha.test(row.original_sha256 || "") ||
        data.row.version_id!==row.version_id || data.row.original_sha256!==row.original_sha256 ||
        data.row.representation_id!==row.representation_id)
        throw Error("source_version_mismatch");
      const preview=$("source-preview");preview.replaceChildren();
      preview.append(el("strong",labelOf(row.source_id)));
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
  const SIGNED_UNSUPPORTED={
    original:"Original download is not available in the signed workbench yet: no signed route returns original bytes. Nothing was requested.",
    page:"Page rendering is not available in the signed workbench yet: no signed route renders pages. The locator above is the only page evidence shown.",
    search:"Evidence search is not available in the signed workbench yet: no signed search route exists. Nothing was searched."};
  async function downloadOriginal(row) {
    const generation=state.generation;
    if(signedWorkbench){notice(SIGNED_UNSUPPORTED.original,"danger");return;}
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
      ...(state.check.legal_observations||[]).map(a=>({
        id:"legal:"+a.reference_id,kind:"Legal reference",state:a.status,source:null,
        span:"Offsets "+a.start+"\u2013"+a.end+" \u00b7 "+a.raw_text,raw:a,
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
    if(!state.check){$("observations-filter").hidden=true;node.append(el("p","Check is unavailable. No success or correctness is implied.","empty"));return;}
    if(!values.length){$("observations-filter").hidden=true;node.append(el("p","No observations in this declared scope. This is not a certification.","empty"));return;}
    const cleanStates=new Set(["exact_match","ready","PASS"]);
    const attention=values.filter(v=>!cleanStates.has(v.state));
    const clean=values.filter(v=>cleanStates.has(v.state));
    state.showAll=state.showAll===true;
    const ordered=state.showAll?values:[...attention,...clean];
    const toggle=$("observations-filter");
    toggle.hidden=false;
    toggle.textContent=state.showAll?
      "Exceptions first ("+attention.length+" to review · "+clean.length+" clean)":
      "Show all "+values.length+" ("+attention.length+" to review first · "+clean.length+" clean)";
    toggle.onclick=()=>{state.showAll=!state.showAll;renderChecks();};
    for(const item of ordered){
      const button=el("button","","observation");button.type="button";
      button.setAttribute("aria-pressed",String(state.selected?.id===item.id));
      button.append(el("span",item.kind+" / "+label(item.state),"tag"));
      button.append(el("strong",item.id.replace("citation:","Reference ").replace("fact:","Fact ").replace("legal:","Legal reference ")));
      button.append(el("small",(labelOf(item.source)||"No confirmed source")+" · "+item.span));
      button.addEventListener("click",()=>{if(state.loading||state.busy||state.pending)return;
        state.selected=item;renderChecks();renderSelected();});
      node.append(button);
    }
  }
  async function renderLegalPassage(selected){
    const generation=state.generation,box=$("source-preview");
    box.replaceChildren(el("p","Loading the cited article from the chosen corpus\u2026","small"));
    try{
      const d=await api(reviewPath()+"/legal-references/"+encodeURIComponent(selected.raw.reference_id)+"/passage");
      if(generation!==state.generation||state.selected!==selected)return;
      if(d.schema!=="caseproof-signed-legal-passage-v1"||d.observation_id!==selected.id||d.snapshot_hash!==state.check?.snapshot_hash)
        throw Error("invalid_schema");
      box.replaceChildren();
      const grid=el("div","","side-by-side");
      const left=el("div"),right=el("div");
      left.append(el("strong","Your brief"));
      const [s,e]=d.citation_span,ex=d.brief_excerpt;
      const p=el("p","","brief-excerpt");
      p.append(document.createTextNode(ex.slice(0,s)));
      const mark=el("mark",ex.slice(s,e));p.append(mark);
      p.append(document.createTextNode(ex.slice(e)));left.append(p);
      right.append(el("strong","Chosen corpus article"));
      if(d.article_text===null)right.append(el("p","The article is not in the corpus chosen for this matter. Nothing was looked up elsewhere.","small"));
      else{right.append(el("p",d.article_text,"article-text"));
        right.append(el("p",(d.corpus_key||"")+" \u00b7 version "+(d.corpus_version||"")+" \u00b7 SHA-256 "+(d.corpus_text_sha256||"").slice(0,16)+"\u2026","small mono"));
        right.append(el("p",d.corpus_source_uri||"","small mono"));}
      grid.append(left,right);box.append(grid);
      box.append(el("p","Result: "+d.status+" \u00b7 "+d.reason+". "+d.note,"small"));
      state.previewReady=true;$("save-review").disabled=!state.review||state.loading||state.busy;
    }catch(error){if(generation===state.generation&&state.selected===selected)box.textContent="Article passage unavailable: "+statusFor(error);}
  }
  function renderSelected(){
    const selected=state.selected;
    revokePageImage();
    $("selected").replaceChildren();
    state.previewReady=false;
    $("save-review").disabled=true;
    if(!selected){$("selected").textContent="Select a finding to inspect and review.";return;}
    $("selected").append(el("strong",selected.kind+" · "+selected.id));
    $("selected").append(el("p","Check state: "+label(selected.state)));
    $("selected").append(el("p","Source: "+(labelOf(selected.source)||"not resolved"),"small"));
    $("selected").append(el("p","This result is a candidate observation, not a legal finding.","small"));
    // A claim may be reviewed only against the exact checked source version,
    // digest and representation, never a newer catalog entry sharing its source_id.
    if(selected.kind==="Legal reference"){void renderLegalPassage(selected);return;}
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
      const d=await api(reviewPath()+"/sources/"+encodeURIComponent(row.source_id));
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
      const preview=$("source-preview");preview.replaceChildren();
      const text=d.text||"";
      // Backend offsets are Unicode code points (Python semantics), never
      // UTF-16 code units: slice over code points so astral characters
      // before or inside the match cannot shift the highlight.
      const chars=[...text];
      const obs=state.selected?.raw||{};
      const start=obs.text_start,end=obs.text_end;
      if(Number.isInteger(start)&&Number.isInteger(end)&&start>=0&&end>start&&end<=chars.length){
        preview.append(el("p","Matched passage · offsets "+start+"–"+end+" in this verified source representation:","small"));
        const passage=el("p","","matched-passage");
        passage.append(el("span",chars.slice(0,start).join("")),el("mark",chars.slice(start,end).join(""),"matched"),el("span",chars.slice(end).join("")));
        preview.append(passage);
        // Page provenance: each numbering space stays distinct; anything not
        // recorded is "not mapped", never inferred from another space.
        const spans=Array.isArray(d.spans)?d.spans:[];
        const pages=new Set(spans.filter(s=>Array.isArray(s)&&s.length===4&&
          Number.isInteger(s[0])&&Number.isInteger(s[1])&&s[0]<end&&start<s[1]&&
          Number.isInteger(s[3])).map(s=>s[3]));
        const physical=pages.size===1?[...pages][0]:null;
        const maps=Array.isArray(d.page_mappings)?d.page_mappings:[];
        const reg=physical===null?null:(maps.find(m=>m&&m.pdf_page===physical)||null);
        preview.append(el("p","Page provenance · physical PDF page: "+(physical===null?"not mapped":physical)+
          " · printed label: "+(reg&&Number.isInteger(reg.printed_page)?reg.printed_page:"not mapped")+
          " · bundle position: "+(reg&&Number.isInteger(reg.bundle_page)?reg.bundle_page:"not mapped"),"small"));
        // Physical page image: an authenticated, digest-checked rendering of
        // the verified original bytes. Availability depends only on the
        // resolved physical page, never on printed/bundle labels. The image
        // is a rendering, never a visual-verification verdict. Late responses
        // are dropped and revoked so they cannot land on another finding.
        if(physical!==null&&row.media_type==="application/pdf"&&signedWorkbench){
          const nb=el("div","","page-image");nb.append(el("p",SIGNED_UNSUPPORTED.page,"small"));
          preview.parentNode.insertBefore(nb,preview.nextSibling);state.pageImageNode=nb;
        } else if(physical!==null&&row.media_type==="application/pdf"){
          const imgBox=el("div","","page-image");
          imgBox.append(el("p","Physical page rendering of the verified original bytes · a rendering, not a verification.","small"));
          imgBox.append(el("p","Loading physical page "+physical+"…","small"));
          preview.parentNode.insertBefore(imgBox,preview.nextSibling);
          state.pageImageNode=imgBox;
          try{
            const resp=await api(path()+"/evidence/"+encodeURIComponent(row.source_id)+
              "/versions/"+encodeURIComponent(row.version_id)+"/pages/"+physical,{raw:true});
            if(resp.headers.get("x-caseproof-original-sha256")!==row.original_sha256)
              throw Error("source_version_mismatch");
            const blob=await resp.blob();
            if(!current())return;
            const url=URL.createObjectURL(blob);
            if(state.pageImageUrl)URL.revokeObjectURL(state.pageImageUrl);
            state.pageImageUrl=url;
            const img=new Image();
            img.alt="Physical PDF page "+physical+" rendering of the verified original";
            img.src=url;
            const zoomHint=el("button","Open readable full-size page view","ghost page-zoom-open");
            zoomHint.type="button";
            zoomHint.addEventListener("click",()=>openPageZoom(url,physical,zoomHint));
            imgBox.replaceChildren(
              el("p","Physical page rendering of the verified original bytes · a rendering, not a verification.","small"),
              img,zoomHint);
          }catch(error){if(current())
            imgBox.replaceChildren(el("p","Physical page image unavailable for this source; the text representation above stands on its own.","small"));}
        }
      }else{
        if(String(state.selected?.id||"").startsWith("citation:"))
          preview.append(el("p","No aligned passage offsets are recorded for this observation; the source text is shown without highlight.","small"));
        preview.append(el("p",text||"Source has no available text representation."));
      }
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
    state.inventory=null;state.selected=null;revokePageImage();
    if(state.justPublished)$("publish-status").textContent="Reloading current scope after publication\u2026";
    $("save-review").disabled=true;
    $("review-form").setAttribute("aria-busy","true");
    $("selected").textContent="Checking current brief and permissions…";
    $("source-preview").textContent="Source preview cleared while the current scope reloads.";
    $("observations").replaceChildren();$("review-history").replaceChildren();
    $("check-scope").textContent="Checking current source denominator…";
    $("connection").hidden=true;
    $("workspace").hidden=false;
    $("record").disabled=false;
    $("matter-meta").textContent="Matter "+state.caseId+" · brief "+state.briefId;
    notice("Checking private access and current evidence scope…");
    try{
      const checked=await api(reviewPath()+"/check",{method:"POST"});
      if(generation!==state.generation)return;
      if((checked.schema!=="caseproof-m2-check-headless-v1"&&checked.schema!=="caseproof-signed-check-v1") || checked.case_id!==state.caseId ||
        checked.brief_version_id!==state.briefId || !sha.test(checked.snapshot_hash))
        throw Error("invalid_schema");
      state.check=checked;
      notice("Authorized check completed. Findings remain unreviewed until saved.","ok");
    }catch(error){if(generation!==state.generation)return;
      state.check=null;
      notice(error&&error.code===409 ? "This published snapshot is out of date after a source or exhibit change. Publish a new brief version, then re-run the check." : statusFor(error),"danger");}
    if(generation!==state.generation)return;
    try {
      const inv=await api(reviewPath()+"/sources");
      if(generation===state.generation)
        state.inventory=(inv.schema==="caseproof-clearbrief-brief-sources-v1" &&
          inv.case_id===state.caseId && inv.brief_version_id===state.briefId)?inv:null;
    }catch{if(generation!==state.generation)return;state.inventory=null;}
    if(signedWorkbench)await loadLegalReferences(generation);
    if(generation!==state.generation)return;
    try {
      const review=await api(reviewPath()+"/review");
      if(generation===state.generation && review.schema==="caseproof-clearbrief-review-v1" &&
        review.case_id===state.caseId && review.snapshot_hash===state.check?.snapshot_hash)
        state.review=review;
      else state.review=null;
    }catch{if(generation!==state.generation)return;state.review=null;}
    if(generation!==state.generation)return;
    state.loading=false;$("review-form").removeAttribute("aria-busy");
    state.selected=null;
    renderSources();renderChecks();renderReview();renderSelected();
    // The scope is settled: the preview pane shows its idle cue again, never
    // the transient "cleared while the scope reloads" loading text.
    $("source-preview").textContent="Select a source or a finding to inspect its verified representation.";
    if(state.justPublished){
      state.justPublished=false;
      $("publish-status").textContent="Scope current after publication at revision "+state.publishRevision+". Run the factual check.";
    }
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
      const receipt=await api(reviewPath()+"/review",{method:"POST",json:state.pending});
      if(generation!==state.generation)return;
      if(receipt.schema!=="caseproof-clearbrief-review-receipt-v1" ||
        receipt.snapshot_hash!==state.check.snapshot_hash)throw Error("invalid_receipt");
      state.pending=null;$("rationale").value="";
      const review=await api(reviewPath()+"/review");
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
    if(signedWorkbench){node.append(el("p",SIGNED_UNSUPPORTED.search,"small"));return;}
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
  function populateVersions(preferredVersion) {
    const select=$("upload-version");select.replaceChildren();
    const document=(state.catalog||[]).find(d=>d.document_id===$("upload-document").value);
    const versions=document?document.versions:[];
    for(const version of versions){
      const option=el("option","v"+version.version_number+" · "+version.media_type+" · "+version.byte_length+" bytes");
      option.value=version.version_id;select.append(option);
    }
    if(preferredVersion&&versions.some(v=>v.version_id===preferredVersion))
      select.value=preferredVersion;
    $("publish").disabled=versions.length===0;
  }
  async function registerSource(evt){
    evt.preventDefault();
    // Declare-then-upload in one flow: the server registers the digest first
    // and the byte upload fails closed unless it matches the declaration.
    const session=state.session,caseId=state.caseId;
    const label=$("register-label").value.trim();
    const file=$("register-file").files?.[0];
    const mime=file?{txt:"text/plain",pdf:"application/pdf",docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg"}[file.name.split(".").pop()?.toLowerCase()]:null;
    if(!label||!file||file.size<=0||file.size>20*1024*1024||!mime){
      notice("Enter a label and choose a supported original under 20 MiB.","danger");return;
    }
    $("register").disabled=true;
    try{
      const digestBytes=new Uint8Array(await crypto.subtle.digest("SHA-256",await file.arrayBuffer()));
      const digestHex=Array.from(digestBytes,(b)=>b.toString(16).padStart(2,"0")).join("");
      const d=await api("/dev/signed/matters/"+encodeURIComponent(caseId)+"/documents",{
        method:"POST",json:{label,media_type:mime,byte_length:file.size,sha256_hex:digestHex}});
      if(state.session!==session||state.caseId!==caseId)return;
      if(d.schema!=="caseproof-signed-document-register-v1"||!UUID.test(d.document_id)||!UUID.test(d.version_id))
        throw Error("invalid_schema");
      const token=await bearer();
      const response=await fetch("/dev/signed/matters/"+encodeURIComponent(caseId)+
        "/documents/"+encodeURIComponent(d.document_id)+"/versions/"+encodeURIComponent(d.version_id)+"/original",{
          method:"PUT",credentials:"omit",redirect:"error",cache:"no-store",
          headers:{"Authorization":"Bearer "+token,"Content-Type":mime},body:file,
        });
      if(state.session!==session||state.caseId!==caseId)return;
      if(response.status!==201)throw Error("unavailable");
      $("register-label").value="";$("register-file").value="";
      $("register-status").textContent="Source declared and uploaded: "+file.name+" \u00b7 "+file.size+" bytes \u00b7 SHA-256 "+digestHex.slice(0,16)+"\u2026";
      notice("New source declared, registered and uploaded; its bytes matched the declaration.","ok");
      await loadCatalog();
      if(state.catalog.some(doc=>doc.document_id===d.document_id)){
        $("upload-document").value=d.document_id;
        populateVersions(d.version_id);
        $("publish").disabled=false;$("publish-status").textContent="";
      }
    }catch(error){if(state.session===session&&state.caseId===caseId)
      notice("Source declaration failed: "+(error&&error.message?error.message:"unavailable"),"danger");}
    finally{$("register").disabled=false;}
  }
  function mappingRows(){
    // Optional user-declared page mappings: physical page required per filled
    // row, each numbering space independent, numeric domain only. Empty rows
    // are ignored; duplicates fail before sending, never silently overwrite.
    const rows=[...document.querySelectorAll("#mapping-rows .mapping-row")];
    const mappings=[],seen=new Set();
    for(const row of rows){
      const pdf=row.querySelector(".map-pdf").value.trim();
      const printed=row.querySelector(".map-printed").value.trim();
      const bundle=row.querySelector(".map-bundle").value.trim();
      if(!pdf&&!printed&&!bundle)continue;
      const num=(v)=>/^[0-9]+$/.test(v)&&Number(v)>=1&&Number(v)<=100000?Number(v):null;
      const pdfN=num(pdf);
      if(pdfN===null||seen.has(pdfN))return null;
      if((printed&&num(printed)===null)||(bundle&&num(bundle)===null))return null;
      seen.add(pdfN);
      const m={pdf_page:pdfN};
      if(printed)m.printed_page=num(printed);
      if(bundle)m.bundle_page=num(bundle);
      mappings.push(m);
    }
    return mappings;
  }
  function resetMappingRows(){
    const box=$("mapping-rows");
    box.querySelectorAll(".mapping-row").forEach((row,i)=>{if(i>0)row.remove();});
    box.querySelectorAll("input").forEach((input)=>{input.value="";});
  }
  async function declareExhibit(evt){
    evt.preventDefault();
    // Register digest, upload matching bytes, then confirm the exhibit into
    // the check denominator at the current register revision.
    const session=state.session,caseId=state.caseId;
    const label=$("exhibit-label").value.trim();
    const file=$("exhibit-file").files?.[0];
    const mappings=mappingRows();
    if(mappings===null){
      notice("Page mappings: each filled row needs a unique numeric physical page; printed label and bundle position are numeric or empty.","danger");return;
    }
    const mime=file?{txt:"text/plain",pdf:"application/pdf",docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg"}[file.name.split(".").pop()?.toLowerCase()]:null;
    if(!label||!file||file.size<=0||file.size>20*1024*1024||!mime){
      notice("Enter an exhibit label and choose a supported file under 20 MiB.","danger");return;
    }
    $("exhibit").disabled=true;
    try{
      const digestBytes=new Uint8Array(await crypto.subtle.digest("SHA-256",await file.arrayBuffer()));
      const digestHex=Array.from(digestBytes,(b)=>b.toString(16).padStart(2,"0")).join("");
      const d=await api("/dev/signed/matters/"+encodeURIComponent(caseId)+"/documents",{
        method:"POST",json:{label,media_type:mime,byte_length:file.size,sha256_hex:digestHex}});
      if(state.session!==session||state.caseId!==caseId)return;
      if(d.schema!=="caseproof-signed-document-register-v1"||!UUID.test(d.document_id)||!UUID.test(d.version_id))
        throw Error("invalid_schema");
      const token=await bearer();
      const response=await fetch("/dev/signed/matters/"+encodeURIComponent(caseId)+
        "/documents/"+encodeURIComponent(d.document_id)+"/versions/"+encodeURIComponent(d.version_id)+"/original",{
          method:"PUT",credentials:"omit",redirect:"error",cache:"no-store",
          headers:{"Authorization":"Bearer "+token,"Content-Type":mime},body:file,
        });
      if(state.session!==session||state.caseId!==caseId)return;
      if(response.status!==201)throw Error("unavailable");
      const confirmBody={document_id:d.document_id,version_id:d.version_id,display_label:label};
      if(mappings.length)confirmBody.page_mappings=mappings;
      const c=await api("/dev/signed/matters/"+encodeURIComponent(caseId)+"/exhibits/confirm",{
        method:"POST",json:confirmBody});
      if(state.session!==session||state.caseId!==caseId)return;
      if(c.schema!=="caseproof-signed-exhibit-confirm-v1"||typeof c.exhibit_id!=="string"||
         !Number.isInteger(c.exhibit_revision))
        throw Error("invalid_schema");
      $("exhibit-label").value="";$("exhibit-file").value="";
      resetMappingRows();
      $("exhibit-status").textContent="Exhibit declared, uploaded and confirmed at register revision "+
        c.exhibit_revision+": "+file.name+" \u00b7 "+file.size+" bytes \u00b7 SHA-256 "+digestHex.slice(0,16)+"\u2026";
      notice("Exhibit confirmed into the check scope. Published snapshots are stale: publish a new brief version and re-run the check.","ok");
      await load();
    }catch(error){if(state.session===session&&state.caseId===caseId)
      notice("Exhibit declaration failed: "+(error&&error.message?error.message:"unavailable"),"danger");}
    finally{$("exhibit").disabled=false;}
  }
  async function loadCatalog() {
    const generation=state.generation;
    // Recharging the catalog must never silently move the publish target:
    // keep the user's current document/version selection when still present.
    const keepDocument=$("upload-document").value,keepVersion=$("upload-version").value;
    try{
      const data=await api("/dev/signed/matters/"+encodeURIComponent(state.caseId)+"/documents");
      if(generation!==state.generation||!state.session)return;
      state.catalog=(data.schema==="caseproof-signed-documents-v1"&&Array.isArray(data.documents))?data.documents:[];
      if(Number.isInteger(data.own_draft_revision)&&data.own_draft_revision>=0)state.publishRevision=data.own_draft_revision;
    }catch{if(generation!==state.generation)return;state.catalog=[];}
    const select=$("upload-document");select.replaceChildren();
    for(const document of state.catalog){
      const option=el("option",document.label+" · "+document.document_id.slice(0,8)+"\u2026");
      option.value=document.document_id;select.append(option);
    }
    if(keepDocument&&state.catalog.some(d=>d.document_id===keepDocument))
      select.value=keepDocument;
    populateVersions(keepVersion);
  }
  async function publishVersion(evt){
    evt.preventDefault();
    // Capture the exact context the publication is made in; a late success is
    // applied only to that same session and matter, never to a switched one.
    const session=state.session,caseId=state.caseId;
    const documentId=$("upload-document").value.trim(),versionId=$("upload-version").value.trim();
    if(!UUID.test(documentId)||!UUID.test(versionId)){
      notice("Select the registered document/version whose uploaded original to publish.","danger");return;
    }
    $("publish").disabled=true;
    try{
      const d=await api("/dev/signed/matters/"+encodeURIComponent(caseId)+"/briefs/publish",{
        method:"POST",json:{document_id:documentId,version_id:versionId,
          document_role:"own_draft",expected_revision:state.publishRevision}});
      if(state.session!==session||state.caseId!==caseId)return;
      if(d.schema!=="caseproof-signed-brief-publish-v1"||!Number.isInteger(d.published_revision)||
         !UUID.test(d.brief_version_id))
        throw Error("invalid_schema");
      // Server truth always advances; the success UI is applied only when the
      // user still works on the same document/version selection, so a late
      // success never silently replaces newly selected work.
      state.publishRevision=d.published_revision;
      state.briefId=d.brief_version_id;
      if($("upload-document").value.trim()===documentId&&$("upload-version").value.trim()===versionId){
        $("brief-id").value=d.brief_version_id;
        state.justPublished=true;
        notice("Brief version published from the verified uploaded original.","ok");
      }else{
        notice("Publication of the previously selected version completed at revision "+
          d.published_revision+"; current selection unchanged.","ok");
      }
      await load();
    }catch(error){if(state.session===session&&state.caseId===caseId)
      notice(statusFor(error),"danger");}
    finally{$("publish").disabled=false;}
  }
  async function upload(evt){
    evt.preventDefault();
    const session=state.session,caseId=state.caseId;
    const documentId=$("upload-document").value.trim(),versionId=$("upload-version").value.trim();
    const file=$("original-file").files?.[0];
    if(!UUID.test(documentId)||!UUID.test(versionId)||!file||file.size<=0||file.size>20*1024*1024){
      notice("Select a registered document/version and an original under 20 MiB.","danger");return;
    }
    const mime={txt:"text/plain",pdf:"application/pdf",docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg"}[file.name.split(".").pop()?.toLowerCase()];
    if(!mime){notice("This original format is unsupported.","danger");return;}
    $("upload").disabled=true;
    try{
      const token=await bearer();
      const response=await fetch("/dev/signed/matters/"+encodeURIComponent(caseId)+
        "/documents/"+encodeURIComponent(documentId)+"/versions/"+encodeURIComponent(versionId)+"/original",{
          method:"PUT",credentials:"omit",redirect:"error",cache:"no-store",
          headers:{"Authorization":"Bearer "+token,"Content-Type":mime},body:file,
        });
      if(state.session!==session||state.caseId!==caseId)return;
      if(response.status!==201)throw Error("unavailable");
      $("publish").disabled=false;
      $("publish-status").textContent="";
      notice("Original uploaded to its pre-registered version. Reopen the verified source after indexing.","ok");
      const digestBytes=new Uint8Array(await crypto.subtle.digest("SHA-256",await file.arrayBuffer()));
      const digestHex=Array.from(digestBytes,(b)=>b.toString(16).padStart(2,"0")).join("");
      const uploadCurrent=$("upload-current");if(uploadCurrent)uploadCurrent.textContent="Current original: "+file.name+" · "+file.size+" bytes · SHA-256 "+digestHex.slice(0,16)+"\u2026 · version "+versionId;
      await load();
    }catch(error){if(state.session===session&&state.caseId===caseId)
      notice("Upload was denied or its outcome is unknown. Verify the exact version before retrying.","danger");}
    finally{$("upload").disabled=false;}
  }

  // M1/M2 genuinely authored development journey; no browser-side fixture or fake source.
  const journey = {caseId:"", source:null, brief:null, snapshot:null, observation:null, revision:0, pending:null, createRequest:null, briefRequest:null, uploadIdentity:null, registerRequest:null, ingestRequest:null, correctionRequest:null, correctionPreview:null, busy:false};
  function journeyOutput(message, value) {
    $("journey-result").textContent=message;
    if(value!==undefined)$("journey-state").textContent=JSON.stringify(value,null,2);
  }
  async function journeyOrganizations() {
    const generation=state.generation;
    try {
      await authenticate();
      if(generation!==state.generation)return;
      const result=await api("/dev/live/create-organizations");
      if(generation!==state.generation)return;
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
    }catch(e){if(generation===state.generation)journeyOutput(statusFor(e));}
  }
  async function journeyCreate(event) {
    const generation=state.generation;
    event.preventDefault();
    if(journey.busy)return;
    journey.busy=true;
    const org=$("journey-org").value,name=$("journey-matter-name").value.trim();
    try{
      if(!UUID.test(org)||!name)throw Error("invalid_data");
      await authenticate();
      if(generation!==state.generation)return;
      if(!journey.createRequest)journey.createRequest=crypto.randomUUID();
      const result=await api("/dev/live/matters",{method:"POST",json:{
        org_id:org,name,request_id:journey.createRequest}});
      if(generation!==state.generation)return;
      if(!UUID.test(result.case_id))throw Error("invalid_schema");
      journey.createRequest=null;
      journey.caseId=result.case_id;journey.source=null;journey.brief=null;
      journey.snapshot=null;journey.observation=null;journey.revision=0;journey.pending=null;
      $("case-id").value=result.case_id;
      journeyOutput("Matter created with a private owner grant and atomic audit.",result);
    }catch(e){if(generation===state.generation)journeyOutput(statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  async function journeyIngest(event){
    const generation=state.generation;
    event.preventDefault();
    if(journey.busy)return;
    journey.busy=true;
    try{
      const caseId=journey.caseId || $("case-id").value.trim(),file=$("journey-file").files?.[0];
      if(!UUID.test(caseId)||!file||file.size<1||file.size>5242880)
        throw Error("invalid_data");
      const ext=file.name.toLowerCase().split(".").pop();
      const media=ext==="txt"?"text/plain":ext==="pdf"?"application/pdf":
        ext==="docx"?"application/vnd.openxmlformats-officedocument.wordprocessingml.document":null;
      if(!media||(media==="text/plain"&&file.size>1048576)||
         (file.type&&file.type!==media&&file.type!=="application/octet-stream"))
        throw Error("invalid_data");
      await authenticate();
      if(generation!==state.generation)return;
      const bytes=new Uint8Array(await file.arrayBuffer());
      if(generation!==state.generation)return;
      if(media==="text/plain")new TextDecoder("utf-8",{fatal:true}).decode(bytes);
      if(media==="application/pdf"&&
         String.fromCharCode(...bytes.subarray(0,5))!=="%PDF-")throw Error("invalid_pdf");
      if(media.endsWith("wordprocessingml.document")&&
         (bytes[0]!==0x50||bytes[1]!==0x4b||bytes[2]!==0x03||bytes[3]!==0x04))
        throw Error("invalid_docx");
      const digest=new Uint8Array(await crypto.subtle.digest("SHA-256",bytes));
      if(generation!==state.generation)return;
      const hex=Array.from(digest,b=>b.toString(16).padStart(2,"0")).join("");
      const identity=caseId+":"+hex+":"+file.name;
      if(journey.uploadIdentity!==identity){journey.uploadIdentity=identity;
        journey.registerRequest=crypto.randomUUID();journey.ingestRequest=crypto.randomUUID();}
      const reg=await api("/dev/live/matters/"+caseId+"/sources",{method:"POST",json:{
        filename:file.name,sha256:hex,byte_length:bytes.length,media_type:media,
        request_id:journey.registerRequest}});
      if(generation!==state.generation)return;
      let binary="";for(let i=0;i<bytes.length;i+=8192)
        binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
      const route="/dev/live/matters/"+caseId+"/sources/"+reg.document_id+"/"+reg.version_id;
      const uploaded=await api(route+"/upload",{method:"POST",json:{content_base64:btoa(binary)}});
      if(generation!==state.generation)return;
      if(!uploaded.verified||uploaded.sha256!==hex)throw Error("unverified_upload");
      const ingested=await api(route+"/ingest?request_id="+journey.ingestRequest,{method:"POST"});
      if(generation!==state.generation)return;
      if(ingested.original_sha!==hex||ingested.exhibit_confirmed!==false)
        throw Error("unverified_ingestion");
      journey.uploadIdentity=null;journey.registerRequest=null;journey.ingestRequest=null;
      journey.caseId=caseId;journey.source=ingested;
      $("case-id").value=caseId;
      journeyOutput("Verified original and immutable parser representation. Partial coverage and unconfirmed exhibits are not cite-ready.",ingested);
    }catch(e){if(generation===state.generation)journeyOutput("Original ingestion not confirmed. "+statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  async function journeyBrief(event){
    const generation=state.generation;
    event.preventDefault();
    if(journey.busy)return;
    journey.busy=true;
    try{
      const caseId=journey.caseId||$("case-id").value.trim();
      if(!UUID.test(caseId))throw Error("invalid_data");
      let source=journey.source;
      if(!source){
        const data=await api("/dev/live/matters/"+caseId+"/state");
      if(generation!==state.generation)return;
        source=data.sources?.[0];if(!source)throw Error("missing_ingested_source");
      }
      const text=$("journey-draft").value,quote=$("journey-quote").value;
      if(!quote||!text.includes(quote)||!/[0-9]/.test(quote))throw Error("invalid_data");
      if(!journey.briefRequest)journey.briefRequest=crypto.randomUUID();
      const result=await api("/dev/live/matters/"+caseId+"/briefs",{
        method:"POST",json:{source_version_id:source.version_id,text,quote,request_id:journey.briefRequest}});
      if(generation!==state.generation)return;
      if(!UUID.test(result.brief_version_id))throw Error("invalid_schema");
      journey.briefRequest=null;
      journey.caseId=caseId;journey.source=source;journey.brief=result;
      $("journey-correction-before").value=quote;
      journey.correctionPreview=null;journey.correctionRequest=null;
      journey.snapshot=null;journey.revision=0;journey.pending=null;
      $("brief-id").value=result.brief_version_id;
      journeyOutput("Authored versioned brief saved. The factual check is still pending.",result);
    }catch(e){if(generation===state.generation)journeyOutput("Brief creation not confirmed. "+statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  async function journeyCheck(){
    const generation=state.generation;
    if(journey.busy)return;
    journey.busy=true;
    try{
      const c=journey.caseId||$("case-id").value.trim();
      const b=journey.brief?.brief_version_id||$("brief-id").value.trim();
      if(!UUID.test(c)||!UUID.test(b))throw Error("invalid_data");
      const base="/dev/live/matters/"+c+"/briefs/"+b;
      const check=await api(base+"/check",{method:"POST"});
      if(generation!==state.generation)return;
      if(!sha.test(check.snapshot_hash)||typeof check.outcome!=="string")throw Error("invalid_schema");
      journey.caseId=c;journey.brief={brief_version_id:b};
      journey.snapshot=check.snapshot_hash;journey.observation=check.observation_id;journey.revision=check.review_revision;
      journeyOutput("Deterministic source quote check completed; not a legal conclusion.",check);
    }catch(e){if(generation===state.generation)journeyOutput("Check unavailable. "+statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  async function journeyReview(event){
    const generation=state.generation;
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
      if(generation!==state.generation)return;
      if(saved.review_revision!==journey.revision+1&&!saved.replayed)
        throw Error("invalid_receipt");
      journey.revision=saved.review_revision;journey.pending=null;
      journey.correctionPreview=null;journey.correctionRequest=null;
      journeyOutput("Version-bound human review saved atomically.",saved);
    }catch(e){if(generation===state.generation)journeyOutput("Review outcome unknown; retry with the same request. "+statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  function correctionPayload(){
    if(!journey.snapshot||!journey.brief||journey.revision<1)
      throw Error("run_review_first");
    const before=$("journey-correction-before").value.trim();
    const after=$("journey-correction-after").value.trim();
    if(before===after||before.length<3||after.length<3||
       before.length>100||after.length>100||!/[0-9]/.test(before)||!/[0-9]/.test(after))
      throw Error("invalid_correction");
    return {snapshot_hash:journey.snapshot,
      expected_review_revision:journey.revision,before,after};
  }
  async function journeyPreviewCorrection(){
    const generation=state.generation;
    if(journey.busy)return;
    journey.busy=true;
    try{
      const payload=correctionPayload();
      const c=journey.caseId,b=journey.brief.brief_version_id;
      const base="/dev/live/matters/"+c+"/briefs/"+b;
      const response=await api(base+"/corrections/preview",{
        method:"POST",json:{...payload,request_id:crypto.randomUUID()}});
      if(generation!==state.generation)return;
      if(response.schema!=="dev-signed-draft-correction-v1"||
         response.committed!==false||typeof response.preview_text!=="string")
        throw Error("invalid_schema");
      journey.correctionPreview={payload,caseId:c,versionId:b};
      journey.correctionRequest=null;
      $("journey-correction-diff").textContent=response.old_text+" → "+response.preview_text;
      journeyOutput("Correction preview only. Source original and draft are unchanged.",response);
    }catch(e){if(generation===state.generation)journeyOutput("Correction preview rejected. "+statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  async function journeyCommitCorrection(){
    const generation=state.generation;
    if(journey.busy)return;
    journey.busy=true;
    try{
      const current=correctionPayload(),p=journey.correctionPreview;
      if(!p||p.caseId!==journey.caseId||
        p.versionId!==journey.brief.brief_version_id||
        JSON.stringify(p.payload)!==JSON.stringify(current))
        throw Error("repreview_changed_correction");
      if(!journey.correctionRequest)journey.correctionRequest=crypto.randomUUID();
      const path="/dev/live/matters/"+p.caseId+"/briefs/"+p.versionId;
      const updated=await api(path+"/corrections/commit",{
        method:"POST",json:{...current,request_id:journey.correctionRequest}});
      if(generation!==state.generation)return;
      if(updated.committed!==true||!UUID.test(updated.brief_version_id))
        throw Error("invalid_schema");
      journey.brief={brief_version_id:updated.brief_version_id};
      $("brief-id").value=updated.brief_version_id;
      $("journey-correction-before").value=current.after;
      $("journey-quote").value=current.after;
      journey.snapshot=null;journey.observation=null;journey.revision=0;
      journey.pending=null;journey.correctionPreview=null;journey.correctionRequest=null;
      $("journey-correction-diff").textContent="New draft saved. Run Check again; the old review does not authorize this revision.";
      journeyOutput("Immutable new draft saved. Recheck and independently review the new snapshot.",updated);
    }catch(e){if(generation===state.generation)journeyOutput("Correction not confirmed. Retry the same request or reopen. "+statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  async function journeyReopen(){
    const generation=state.generation;
    if(journey.busy)return;
    journey.busy=true;
    try{
      await authenticate();
      if(generation!==state.generation)return;
      const c=journey.caseId||$("case-id").value.trim();
      if(!UUID.test(c))throw Error("invalid_data");
      const reopened=await api("/dev/live/matters/"+c+"/state");
      if(generation!==state.generation)return;
      if(reopened.schema!=="dev-live-txt-v1")throw Error("invalid_schema");
      const b=reopened.briefs?.[0];
      if(b){
        const check=await api("/dev/live/matters/"+c+"/briefs/"+b.brief_version_id+"/check",{method:"POST"});
      if(generation!==state.generation)return;
        const review=await api("/dev/live/matters/"+c+"/briefs/"+b.brief_version_id+"/reviews/"+check.snapshot_hash);
      if(generation!==state.generation)return;
        journey.snapshot=check.snapshot_hash;journey.observation=check.observation_id;journey.revision=review.review_revision;
        journey.brief={brief_version_id:b.brief_version_id};
        $("journey-correction-before").value=b.quote||"";
        journey.correctionPreview=null;journey.correctionRequest=null;
        $("brief-id").value=b.brief_version_id;
        reopened.review=review;reopened.check=check;
      }
      journey.caseId=c;journey.source=reopened.sources?.[0]||null;
      $("case-id").value=c;
      journeyOutput("Reopened matter, ingested text, authored brief and review directly from Supabase.",reopened);
    }catch(e){if(generation===state.generation)journeyOutput("Reopening not confirmed. "+statusFor(e));}
    finally{if(generation===state.generation)journey.busy=false;}
  }
  function signout(){
    state.generation+=1;state.previewSeq+=1;revokePageImage();
    if(!state.external)state.session?.clear?.();
    state.session=null;state.external=false;state.caseId="";state.briefId="";
    state.catalog=null;state.publishRevision=0;
    Object.assign(journey,{caseId:"",source:null,brief:null,snapshot:null,observation:null,revision:0,pending:null,createRequest:null,briefRequest:null,uploadIdentity:null,registerRequest:null,ingestRequest:null,correctionRequest:null,correctionPreview:null,busy:false});
    $("journey-state").textContent="";
    $("matter-options").replaceChildren();
    $("password").value="";$("signout").hidden=true;clearView();notice("Session ended. No credentials were saved.");
  }
  function disableRemoteJourney(){
    // The /dev/live/* journey targets a configured remote Supabase project.
    // In a loopback composition without a publishable key those controls are
    // dead steps; disable them honestly instead of offering actions that
    // can only fail. The signed workbench below stays fully usable.
    const card=document.querySelector?.(".journey-card");
    if(card)card.replaceChildren(el("p","Remote Supabase journey unavailable in this composition. "+
      "The signed workbench below is the functional path here.","small"));
    const fidelity=$("fidelity-panel");
    if(fidelity)fidelity.hidden=true;
  }
  async function downloadRecord(){
    if(!state.session)return;
    $("record").disabled=true;
    try{
      const data=await api("/dev/signed/matters/"+encodeURIComponent(state.caseId)+"/review-record");
      if(data.schema!=="caseproof-review-record-v1"||!sha.test(data.record_sha256)||
         data.case_id!==state.caseId)
        throw Error("invalid_schema");
      const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});
      const link=document.createElement("a");
      link.href=URL.createObjectURL(blob);
      link.download="caseproof-review-record.json";link.rel="noopener";link.click();
      URL.revokeObjectURL(link.href);
      $("record-status").textContent="Record SHA-256 "+data.record_sha256.slice(0,16)+
        "\u2026 · revision "+data.brief.head_revision+" · "+data.checks.length+" recorded check(s) · "+
        data.reviews.reduce((n,r)=>n+r.decisions.length,0)+" review decision(s). Transcript of recorded state, not an approval.";
      const qr=$("record-qr"),wrap=$("record-qr-wrap");
      wrap.hidden=true;
      try{
        const token=await bearer();
        const qrResponse=await fetch("/dev/signed/matters/"+encodeURIComponent(state.caseId)+
          "/review-record/verification-qr",
          {headers:{Authorization:"Bearer "+token},credentials:"omit",redirect:"error",cache:"no-store"});
        if(qrResponse.ok){
          const qrBlob=await qrResponse.blob();
          if(qrBlob.type==="image/png"&&qrBlob.size>0&&qrBlob.size<=65536){
            qr.onload=()=>{wrap.hidden=false;};
            qr.onerror=()=>{wrap.hidden=true;};
            qr.src=URL.createObjectURL(qrBlob);
          }
        }
      }catch{wrap.hidden=true;}
    }catch(error){if(error?.message!=="no_session")notice(statusFor(error),"danger");}
    finally{$("record").disabled=!state.session;}
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
    $("journey-correction-preview").addEventListener("click",journeyPreviewCorrection);
    $("journey-correction-commit").addEventListener("click",journeyCommitCorrection);
    $("find-matters").addEventListener("click",findMatters);
    $("review-form").addEventListener("submit",submitReview);
    $("search").addEventListener("click",search);
    $("register-form").addEventListener("submit",registerSource);
    $("exhibit-form").addEventListener("submit",declareExhibit);
    $("mapping-add").addEventListener("click",()=>{
      const box=$("mapping-rows"),rows=box.querySelectorAll(".mapping-row");
      if(rows.length>=8)return;
      const row=rows[0].cloneNode(true);
      row.querySelectorAll("input").forEach((input)=>{input.value="";});
      box.insertBefore(row,$("mapping-add"));
    });
    $("upload-form").addEventListener("submit",upload);
    $("upload-document").addEventListener("change",populateVersions);
    const publishForm=$("publish-form");if(publishForm)publishForm.addEventListener("submit",publishVersion);
    $("signout").addEventListener("click",signout);
    $("record").addEventListener("click",downloadRecord);
    $("refresh").addEventListener("click",()=>{void load();});
    $("recheck").addEventListener("click",()=>{void load();});
    if(window.caseproofSession?.getBearer){
      // A trusted host session declares the signed workbench itself; no extra request.
      signedWorkbench=window.caseproofSession.signedWorkbench===true;
      {const cf=$("correction-form");if(cf)cf.hidden=!signedWorkbench;}
      $("credentials").hidden=true;$("auth-mode").textContent="Connected host session";
      $("case-id").value=window.caseproofSession.caseId||"";
      $("brief-id").value=window.caseproofSession.briefVersionId||"";
      disableRemoteJourney();
      return;
    }
    try {
      const response=await fetch("/dev/clearbrief/config",{credentials:"omit",cache:"no-store"});
      const config=await response.json();
      if(response.ok&&config.schema==="caseproof-clearbrief-dev-config-v1"&&
         typeof config.publishable_key==="string"&&config.publishable_key.startsWith("sb_publishable_")){
        state.publishable=config.publishable_key;signedWorkbench=config.signed_workbench===true;{const cf=$("correction-form");if(cf)cf.hidden=!signedWorkbench;}$("auth-mode").textContent="Supabase dev authentication";
      }else{
        $("auth-mode").textContent="Backend session required";$("credentials").hidden=true;
        $("connect").disabled=true;disableRemoteJourney();
        notice("No signed identity provider is configured. Connect a trusted host session.","danger");
      }
    }catch{ $("auth-mode").textContent="Backend session required";$("credentials").hidden=true;
      $("connect").disabled=true;notice("The signed identity provider is unavailable.","danger");}
  }
  $("correction-form")?.addEventListener("submit", previewCorrection);
  void init();
})();


