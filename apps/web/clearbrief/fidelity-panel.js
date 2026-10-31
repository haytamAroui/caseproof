"use strict";
/* Shared dossier panel; trusted API supplies observations, never browser flags. */
window.CaseProofFidelity = {mount({root, api, context}) {
  let report=null, sequence=0, pending=null, busy=false;
  const urls=new Set(), drafts=new Map();
  const node=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
  const heading=node("h2","Compare text with the source image");
  const status=node("p","Visual fidelity has not been assessed.","notice");status.setAttribute("role","status");
  const load=node("button","Inspect dossier");load.type="button";
  const coverage=node("section", "", "fidelity-coverage");coverage.setAttribute("aria-label","Verification coverage");
  const list=node("div", "", "fidelity-list");
  const base=()=>{const c=context();return `/v2/matters/${encodeURIComponent(c.caseId)}/briefs/${encodeURIComponent(c.briefId)}/dossier`;};
  const clear=()=>{for(const u of urls)URL.revokeObjectURL(u);urls.clear();list.replaceChildren();coverage.replaceChildren();report=null;};
  const fail=()=>{status.textContent="Cannot open this snapshot. Check your session and access, then retry.";status.className="notice danger";};
  async function renderFinding(f,seq) {
    if(seq!==sequence)return;
    const assessment=f.visual_assessment||{state:"not_assessed",reason:"visual_not_run",regions:[]};
    const article=node("article","","fidelity-finding");
    const title=node("h3",f.literal);article.append(title);
    article.append(node("p",`Identity: ${f.identity} · Page: ${f.page_mapping} · Fidelity: ${f.fidelity} · Support: ${f.support}`,"small"));
    if(f.identity_reason)article.append(node("p",`Inventory: ${f.identity_reason}`,"notice"));
    if(f.translation_review_required)article.append(node("p",`Translation review required · Draft: ${f.draft_language||"undeclared"} · Source: ${f.source_language||"undeclared"}. A literal comparison cannot confirm translated prose.`,"notice"));
    if(f.quoted_text)article.append(node("p",`Draft quotation: ${f.quoted_text}`));
    if(f.literal_assessment)article.append(node("p",`Literal: ${f.literal_assessment.state} — ${f.literal_assessment.reason}`,"small"));
    const warning=node("p",(assessment.state==="representation_conflict"?"⚠ Representation conflict":assessment.state==="ocr_unreliable"?"⚠ OCR unreliable":"○ Visual fidelity not assessed")+" — "+assessment.reason,
      assessment.state==="representation_conflict"?"notice danger":"notice");
    article.append(warning);list.append(article);
    let originalOpened=false;
    const inspected=[];
    const crops=node("div","","fidelity-crops");article.append(crops);
    const cropStatus=node("p",assessment.regions.length?"Loading preserved crops…":"No region anchored to this reference.","small");article.append(cropStatus);
    if(f.source_text_context){article.append(node("strong",`Source text (${f.source_language||"language undeclared"}) — original representation, not a translation`),node("pre",f.source_text_context));}
    if(f.source_text_context_partial)article.append(node("p","Source context is truncated. Inspect the full preserved page before deciding.","notice"));
    if(f.translation_review_required&&!assessment.regions.length)article.append(node("p","Translated text has no literal source anchor. Download the preserved source page and inspect its context before recording support.","notice"));
    const form=document.createElement("form");form.noValidate=true;
    const actionLabel=node("label","Human disposition");const action=document.createElement("select");
    for(const [value,text] of [["CONFIRMED_QUALIFIED","Qualified / needs further evidence"],["CONFIRMED_CONTRADICTED","Contradicted"],["CONFIRMED_SUPPORTED","Supported after human inspection"]]) {const o=node("option",text);o.value=value;action.append(o);}
    actionLabel.append(action);form.append(actionLabel);
    const draftKey=base()+":"+f.reference_id;
    const rationaleLabel=node("label","Rationale");const rationale=document.createElement("textarea");rationale.maxLength=1000;rationale.rows=4;rationale.value=drafts.get(draftKey)||"";rationale.addEventListener("input",()=>drafts.set(draftKey,rationale.value));rationaleLabel.append(rationale);form.append(rationaleLabel);
    const confirmLabel=node("label","I inspected the displayed source regions for this snapshot.");const confirm=document.createElement("input");confirm.type="checkbox";confirmLabel.prepend(confirm);form.append(confirmLabel);
    const save=node("button","Save human review");save.type="submit";save.disabled=true;form.append(save);article.append(form);
    const ready=()=>assessment.regions.length?inspected.length===assessment.regions.length:originalOpened;
    confirm.addEventListener("change",()=>{save.disabled=busy||!confirm.checked||!ready();});
    if(f.source_page?.version_id&&f.source_page?.pdf_page){
      const sourceButton=node("button","Download preserved source page");sourceButton.type="button";
      sourceButton.addEventListener("click",async()=>{sourceButton.disabled=true;
        try{const response=await api(base()+`/sources/${encodeURIComponent(f.source_page.version_id)}/pages/${f.source_page.pdf_page}`,{raw:true});
          if(seq!==sequence)return;
          if(response.headers.get("X-CaseProof-Original-SHA256")!==f.source_sha256||response.headers.get("X-CaseProof-PDF-Page")!==String(f.source_page.pdf_page))throw Error("source_identity");
          const blob=await response.blob();if(seq!==sequence)return;
          const url=URL.createObjectURL(blob);urls.add(url);const link=document.createElement("a");link.href=url;link.download="caseproof-source-page.pdf";link.rel="noopener";link.click();
          originalOpened=true;cropStatus.textContent="Preserved source page downloaded. Open it and inspect its original-language context before confirming.";
          save.disabled=busy||!confirm.checked||!ready();
        }catch{if(seq===sequence)cropStatus.textContent="Source page unavailable. Review remains blocked until the source can be inspected.";}
        finally{if(seq===sequence)sourceButton.disabled=false;}
      });article.append(sourceButton);
    }
    form.addEventListener("submit",async e=>{e.preventDefault();if(busy||save.disabled)return;
      if(!rationale.value.trim()){cropStatus.textContent="Enter a rationale before saving.";rationale.setAttribute("aria-invalid","true");rationale.focus();return;}
      const payload={snapshot_hash:report.snapshot_hash,reference_id:f.reference_id,decision:action.value,rationale:rationale.value.trim(),reviewed_region_ids:inspected};
      const signature=JSON.stringify(payload);
      if(pending&&pending.signature!==signature){cropStatus.textContent="Resolve the previous uncertain save before changing its input.";return;}
      pending=pending||{signature,payload:{...payload,request_id:crypto.randomUUID()}};busy=true;save.disabled=true;load.disabled=true;form.setAttribute("aria-busy","true");
      try{await api(base()+"/reviews",{method:"POST",json:pending.payload});if(seq!==sequence)return;pending=null;cropStatus.textContent="Human review saved. The original conflict remains in the report.";}
      catch(error){
        if(seq!==sequence)return;
        if([400,401,403,404,409,422].includes(error?.code)){
          pending=null;confirm.checked=false;
          cropStatus.textContent="Review rejected. Load the current snapshot and inspect again. Your rationale is kept in this session.";
        }else cropStatus.textContent="Review was not confirmed. Retry the same input; refresh after a snapshot conflict.";
      }
      finally{if(seq===sequence){busy=false;load.disabled=false;form.removeAttribute("aria-busy");save.disabled=!confirm.checked||!ready();}}
    });
    try{
      const batch=assessment.regions.length?await api(base()+`/snapshots/${report.snapshot_hash}/crops`,
        {method:"POST",json:{region_ids:assessment.regions.map(r=>r.region_id)}}):null;
      if(seq!==sequence)return;
      if(batch&&(batch.snapshot_hash!==report.snapshot_hash||!Array.isArray(batch.crops)||batch.crops.length!==assessment.regions.length))throw Error("crop_batch_scope");
      for(const r of assessment.regions){
        const selected=batch.crops.filter(c=>c.region_id===r.region_id);
        if(selected.length!==1)throw Error("crop_batch_identity");
        const crop=selected[0];
        const bytes=Uint8Array.from(atob(crop.crop_base64),c=>c.charCodeAt(0));
        const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))).map(x=>x.toString(16).padStart(2,"0")).join("");
        if(seq!==sequence)return;
        if(hash!==r.crop_sha256||crop.crop_sha256!==r.crop_sha256||crop.original_sha256!==r.original_sha256)throw Error("crop_integrity");
        const view=node("section","","fidelity-region");
        view.append(node("p",`Page ${r.page_number} · ${r.reason}`,"small"));
        const side=node("div","","fidelity-pair");const text=node("div","");text.append(node("strong","Extracted text"),node("pre",r.extracted_text||"No independent text layer"),node("strong","Visual transcription"),node("pre",r.visual_text||"Unreadable"));
        const image=document.createElement("img");image.alt=`Preserved source crop, page ${r.page_number}`;image.width=Math.max(1,r.bbox[2]-r.bbox[0]);image.height=Math.max(1,r.bbox[3]-r.bbox[1]);
        const url=URL.createObjectURL(new Blob([bytes],{type:"image/png"}));urls.add(url);image.src=url;await image.decode();if(seq!==sequence)return;side.append(text,image);view.append(side);crops.append(view);inspected.push(r.region_id);
      }
      cropStatus.textContent=assessment.regions.length?"Preserved crop hashes checked. Human inspection is still required.":"No region anchored; visual fidelity remains unassessed.";
    }catch{cropStatus.textContent="Crop unavailable or integrity check failed. Review is blocked; retry loading.";confirm.disabled=true;save.disabled=true;}
  }
  load.addEventListener("click",async()=>{if(busy)return;if(pending){status.textContent="Resolve the uncertain review save before loading another snapshot.";return;}
    const seq=++sequence;clear();load.disabled=true;status.textContent="Comparing source representations…";
    try{const data=await api(base());if(seq!==sequence)return;
      if(data.schema!=="caseproof-dossier-v1"||!Array.isArray(data.findings))throw Error("invalid_report");report=data;
      const c=data.coverage||{};const manifest=c.docx_regions;
      coverage.append(node("h3","Declared processing coverage"));
      coverage.append(node("p",`Detected: ${c.references_detected??c.detected??"unknown"} · Identity/page checked: ${c.references_checked??c.checked??"unknown"} · Recognition recall: not measured.`));
      coverage.append(node("p",manifest?`DOCX regions discovered: ${manifest.regions_discovered} · Scanned: ${manifest.regions_scanned} · Unsupported: ${manifest.regions_unsupported??"unknown"} · Coverage unknown: ${manifest.coverage_unknown}.`:"Detailed DOCX region coverage was not recorded for this snapshot.","notice"));
      const details=node("details","");details.append(node("summary","Regions and reasons"));
      for(const r of (manifest?.regions||[]).slice(0,100))details.append(node("p",`${r.part} · ${r.kind} · ${r.status} · ${r.reason}`,"small"));
      if((manifest?.regions||[]).length>100)details.append(node("p","Showing 100 regions; export contains the full ledger."));
      coverage.append(details);
      coverage.append(node("p",`Source pages: ${c.source_pages_total??"unknown"} · Isolated OCR processed: ${c.source_pages_ocr_processed??"unknown"} · Failed/skipped: ${c.source_pages_failed_or_skipped??"unknown"}. Unprocessed pages remain unassessed.`,"small"));
      status.textContent=`${data.findings.length} references. Visual agreement is uncalibrated; no legal conclusion is automated.`;
      if(!data.findings.length)list.append(node("p","No explicit references were found. Review processing coverage."));
      for(const f of data.findings){if(seq!==sequence)return;await renderFinding(f,seq);}
    }catch{if(seq===sequence){clear();fail();}}finally{if(seq===sequence)load.disabled=false;}
  });
  root.append(heading,node("p","Inspect uncertainty beside preserved source pixels. A matching quotation alone does not establish visual fidelity.","small"),load,status,coverage,list);
  return {clear(){sequence++;clear();pending=null;busy=false;load.disabled=false;drafts.clear();status.textContent="Session cleared. Reauthenticate before inspecting.";}};
}};
