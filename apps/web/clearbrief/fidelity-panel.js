"use strict";
/* Shared dossier panel; trusted API supplies observations, never browser flags. */
window.CaseProofFidelity = {mount({root, api, context}) {
  let report=null, sequence=0, pending=null, busy=false;
  const urls=new Set();
  const node=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
  const heading=node("h2","Compare text with the source image");
  const status=node("p","Visual fidelity has not been assessed.","notice");status.setAttribute("role","status");
  const load=node("button","Inspect dossier");load.type="button";
  const list=node("div", "", "fidelity-list");
  const base=()=>{const c=context();return `/v2/matters/${encodeURIComponent(c.caseId)}/briefs/${encodeURIComponent(c.briefId)}/dossier`;};
  const clear=()=>{for(const u of urls)URL.revokeObjectURL(u);urls.clear();list.replaceChildren();report=null;};
  const fail=()=>{status.textContent="Cannot open this snapshot. Check your session and access, then retry.";status.className="notice danger";};
  async function renderFinding(f,seq) {
    const assessment=f.visual_assessment||{state:"not_assessed",reason:"visual_not_run",regions:[]};
    const article=node("article","","fidelity-finding");
    const title=node("h3",f.literal);article.append(title);
    article.append(node("p",`Identity: ${f.identity} · Page: ${f.page_mapping} · Fidelity: ${f.fidelity} · Support: ${f.support}`,"small"));
    const warning=node("p",(assessment.state==="representation_conflict"?"⚠ Representation conflict":assessment.state==="ocr_unreliable"?"⚠ OCR unreliable":"○ Visual fidelity not assessed")+" — "+assessment.reason,
      assessment.state==="representation_conflict"?"notice danger":"notice");
    article.append(warning);list.append(article);
    const inspected=[];
    const crops=node("div","","fidelity-crops");article.append(crops);
    const cropStatus=node("p",assessment.regions.length?"Loading preserved crops…":"No region anchored to this reference.","small");article.append(cropStatus);
    const form=document.createElement("form");form.noValidate=true;
    const actionLabel=node("label","Human disposition");const action=document.createElement("select");
    for(const [value,text] of [["CONFIRMED_QUALIFIED","Qualified / needs further evidence"],["CONFIRMED_CONTRADICTED","Contradicted"],["CONFIRMED_SUPPORTED","Supported after human inspection"]]) {const o=node("option",text);o.value=value;action.append(o);}
    actionLabel.append(action);form.append(actionLabel);
    const rationaleLabel=node("label","Rationale");const rationale=document.createElement("textarea");rationale.maxLength=1000;rationale.rows=4;rationaleLabel.append(rationale);form.append(rationaleLabel);
    const confirmLabel=node("label","I inspected the displayed source regions for this snapshot.");const confirm=document.createElement("input");confirm.type="checkbox";confirmLabel.prepend(confirm);form.append(confirmLabel);
    const save=node("button","Save human review");save.type="submit";save.disabled=true;form.append(save);article.append(form);
    confirm.addEventListener("change",()=>{save.disabled=busy||!confirm.checked||inspected.length!==assessment.regions.length;});
    form.addEventListener("submit",async e=>{e.preventDefault();if(busy||save.disabled)return;
      if(!rationale.value.trim()){cropStatus.textContent="Enter a rationale before saving.";rationale.setAttribute("aria-invalid","true");rationale.focus();return;}
      const payload={snapshot_hash:report.snapshot_hash,reference_id:f.reference_id,decision:action.value,rationale:rationale.value.trim(),reviewed_region_ids:inspected};
      const signature=JSON.stringify(payload);
      if(pending&&pending.signature!==signature){cropStatus.textContent="Resolve the previous uncertain save before changing its input.";return;}
      pending=pending||{signature,payload:{...payload,request_id:crypto.randomUUID()}};busy=true;save.disabled=true;load.disabled=true;form.setAttribute("aria-busy","true");
      try{await api(base()+"/reviews",{method:"POST",json:pending.payload});if(seq!==sequence)return;pending=null;cropStatus.textContent="Human review saved. The original conflict remains in the report.";}
      catch{cropStatus.textContent="Review was not confirmed. Retry the same input; refresh after a snapshot conflict.";}
      finally{busy=false;load.disabled=false;form.removeAttribute("aria-busy");save.disabled=!confirm.checked;}
    });
    try{
      for(const r of assessment.regions){
        const response=await api(base()+`/snapshots/${report.snapshot_hash}/regions/${r.region_id}/crop`,{raw:true});
        const bytes=await response.arrayBuffer();if(seq!==sequence)return;
        const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))).map(x=>x.toString(16).padStart(2,"0")).join("");
        if(hash!==r.crop_sha256||response.headers.get("X-CaseProof-Snapshot")!==report.snapshot_hash||response.headers.get("X-CaseProof-Original-SHA256")!==r.original_sha256)throw Error("crop_integrity");
        const view=node("section","","fidelity-region");
        view.append(node("p",`Page ${r.page_number} · ${r.reason}`,"small"));
        const side=node("div","","fidelity-pair");const text=node("div","");text.append(node("strong","Extracted text"),node("pre",r.extracted_text||"No independent text layer"),node("strong","Visual transcription"),node("pre",r.visual_text||"Unreadable"));
        const image=document.createElement("img");image.alt=`Preserved source crop, page ${r.page_number}`;image.width=Math.max(1,r.bbox[2]-r.bbox[0]);image.height=Math.max(1,r.bbox[3]-r.bbox[1]);
        const url=URL.createObjectURL(new Blob([bytes],{type:"image/png"}));urls.add(url);image.src=url;side.append(text,image);view.append(side);crops.append(view);inspected.push(r.region_id);
      }
      cropStatus.textContent=assessment.regions.length?"Preserved crop hashes checked. Human inspection is still required.":"No region anchored; visual fidelity remains unassessed.";
    }catch{cropStatus.textContent="Crop unavailable or integrity check failed. Review is blocked; retry loading.";confirm.disabled=true;save.disabled=true;}
  }
  load.addEventListener("click",async()=>{if(busy)return;if(pending){status.textContent="Resolve the uncertain review save before loading another snapshot.";return;}
    const seq=++sequence;clear();load.disabled=true;status.textContent="Comparing source representations…";
    try{const data=await api(base());if(seq!==sequence)return;
      if(data.schema!=="caseproof-dossier-v1"||!Array.isArray(data.findings))throw Error("invalid_report");report=data;
      status.textContent=`${data.findings.length} references. Visual agreement is uncalibrated; no legal conclusion is automated.`;
      if(!data.findings.length)list.append(node("p","No explicit references were found. Review processing coverage."));
      for(const f of data.findings)await renderFinding(f,seq);
    }catch{clear();fail();}finally{if(seq===sequence)load.disabled=false;}
  });
  root.append(heading,node("p","Inspect uncertainty beside preserved source pixels. A matching quotation alone does not establish visual fidelity.","small"),load,status,list);
  return {clear(){sequence++;clear();pending=null;status.textContent="Session cleared. Reauthenticate before inspecting.";}};
}};
