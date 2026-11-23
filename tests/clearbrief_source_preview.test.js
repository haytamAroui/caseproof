"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

class Element {
  constructor() { this.children=[]; this.listeners={}; this.value=""; this.textContent=""; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=nodes; this.textContent=""; }
  get firstChild() { return this.children[0]; }
  addEventListener(name, handler) { this.listeners[name]=handler; }
  setAttribute() {}
  removeAttribute() {}
}

async function runPreview(changed) {
  const nodes=new Map();
  const get=id=>{ if(!nodes.has(id)) nodes.set(id,new Element()); return nodes.get(id); };
  const caseId="11111111-1111-4111-8111-111111111111";
  const briefId="22222222-2222-4222-8222-222222222222";
  const row={source_id:"source",version_id:"version-a",original_sha256:"a".repeat(64),
    representation_id:"representation-a",warnings:[],pages:[]};
  const response=data=>({ok:true,json:async()=>data});
  const fetch=async url=>{
    if(url.endsWith("/check")) return response({schema:"caseproof-m2-check-headless-v1",
      case_id:caseId,brief_version_id:briefId,snapshot_hash:"b".repeat(64)});
    if(url.endsWith("/sources")) return response({schema:"caseproof-clearbrief-brief-sources-v1",
      case_id:caseId,brief_version_id:briefId,rows:[row]});
    if(url.endsWith("/sources/source")) return response({schema:"caseproof-clearbrief-brief-source-preview-v1",
      case_id:caseId,brief_version_id:briefId,row:{...row,...changed},text:"sensitive version text"});
    if(url.endsWith("/review")) return response({schema:"caseproof-clearbrief-review-v1",case_id:caseId,
      snapshot_hash:"b".repeat(64),revision:0});
    throw Error("unexpected request");
  };
  const document={getElementById:get,createElement:()=>new Element()};
  const window={caseproofSession:{caseId,briefVersionId:briefId,getBearer:async()=>"test"}};
  vm.runInNewContext(fs.readFileSync("apps/web/clearbrief/workspace.js","utf8"),
    {document,window,fetch,console,setTimeout});
  await get("connection-form").listeners.submit({preventDefault(){}});
  await get("sources").children[0].listeners.click();
  return get("source-preview");
}

test("source preview and download require matching provenance",async()=>{
  const matched=await runPreview({});
  assert(matched.children.some(x=>x.textContent==="sensitive version text"));
  assert(matched.children.some(x=>x.textContent==="Download verified original"));
  for(const change of [{version_id:"version-b"},{original_sha256:"b".repeat(64)},
    {representation_id:"representation-b"},{version_id:null}]) {
    const preview=await runPreview(change);
    assert.match(preview.textContent,/changed.*Refresh/);
    assert.equal(preview.children.length,0);
  }
});

async function runObservationPreview(observation, previewExtra) {
  const nodes=new Map();
  const get=id=>{ if(!nodes.has(id)) nodes.set(id,new Element()); return nodes.get(id); };
  const caseId="11111111-1111-4111-8111-111111111111";
  const briefId="22222222-2222-4222-8222-222222222222";
  const row={source_id:"source",version_id:"version-a",original_sha256:"a".repeat(64),
    representation_id:"representation-a",warnings:[],pages:[]};
  const response=data=>({ok:true,json:async()=>data});
  const fetch=async url=>{
    if(url.endsWith("/check")) return response({schema:"caseproof-m2-check-headless-v1",
      case_id:caseId,brief_version_id:briefId,snapshot_hash:"b".repeat(64),
      citation_observations:observation?[observation]:[],factual_observations:[]});
    if(url.endsWith("/sources")) return response({schema:"caseproof-clearbrief-brief-sources-v1",
      case_id:caseId,brief_version_id:briefId,rows:[row]});
    if(url.endsWith("/sources/source")) return response({schema:"caseproof-clearbrief-brief-source-preview-v1",
      case_id:caseId,brief_version_id:briefId,row,text:"sensitive version text",
      ...(typeof previewExtra!=="undefined"?previewExtra:{})});
    if(url.endsWith("/review")) return response({schema:"caseproof-clearbrief-review-v1",case_id:caseId,
      snapshot_hash:"b".repeat(64),revision:0});
    throw Error("unexpected request");
  };
  const document={getElementById:get,createElement:()=>new Element()};
  const window={caseproofSession:{caseId,briefVersionId:briefId,getBearer:async()=>"test"}};
  vm.runInNewContext(fs.readFileSync("apps/web/clearbrief/workspace.js","utf8"),
    {document,window,fetch,console,setTimeout});
  await get("connection-form").listeners.submit({preventDefault(){}});
  get("observations").children[0].listeners.click();
  await new Promise(r=>setTimeout(r,0));
  await new Promise(r=>setTimeout(r,0));
  return get("source-preview");
}

test("citation observation preview highlights the recorded passage offsets",async()=>{
  const preview=await runObservationPreview({reference_id:"ref-01",state:"exact_match",
    source_id:"source",source_version_id:"version-a",source_sha256:"a".repeat(64),
    representation_id:"representation-a",text_start:5,text_end:14});
  const caption=preview.children.find(x=>x.textContent.includes("offsets 5\u201314"));
  assert(caption,"caption with recorded offsets");
  const passage=preview.children.find(x=>x.className==="matched-passage");
  const mark=passage.children.find(x=>x.className==="matched");
  assert.equal(mark.textContent,"tive vers");
  assert.equal(passage.children.map(x=>x.textContent).join(""),"sensitive version text");
});

test("citation observation without aligned offsets shows unhighlighted text",async()=>{
  const preview=await runObservationPreview({reference_id:"ref-01",state:"reference_unresolved",
    source_id:"source",source_version_id:"version-a",source_sha256:"a".repeat(64),
    representation_id:"representation-a",text_start:null,text_end:null});
  assert(preview.children.some(x=>x.textContent.includes("without highlight")));
  assert(preview.children.some(x=>x.textContent==="sensitive version text"));
  assert(!preview.children.some(x=>x.className==="matched-passage"));
});

test("passage offsets are Unicode code points, not UTF-16 units",async()=>{
  const text="a\u{1F600}b LE droit \u{1F601} fin";
  const span="LE droit \u{1F601}";
  const start=[..."a\u{1F600}b "].length;
  const end=start+[...span].length;
  const nodes=new Map();
  const get=id=>{ if(!nodes.has(id)) nodes.set(id,new Element()); return nodes.get(id); };
  const caseId="11111111-1111-4111-8111-111111111111";
  const briefId="22222222-2222-4222-8222-222222222222";
  const row={source_id:"source",version_id:"version-a",original_sha256:"a".repeat(64),
    representation_id:"representation-a",warnings:[],pages:[]};
  const response=data=>({ok:true,json:async()=>data});
  const fetch=async url=>{
    if(url.endsWith("/check")) return response({schema:"caseproof-m2-check-headless-v1",
      case_id:caseId,brief_version_id:briefId,snapshot_hash:"b".repeat(64),
      citation_observations:[{reference_id:"ref-01",state:"exact_match",source_id:"source",
        source_version_id:"version-a",source_sha256:"a".repeat(64),
        representation_id:"representation-a",text_start:start,text_end:end}],
      factual_observations:[]});
    if(url.endsWith("/sources")) return response({schema:"caseproof-clearbrief-brief-sources-v1",
      case_id:caseId,brief_version_id:briefId,rows:[row]});
    if(url.endsWith("/sources/source")) return response({schema:"caseproof-clearbrief-brief-source-preview-v1",
      case_id:caseId,brief_version_id:briefId,row,text});
    if(url.endsWith("/review")) return response({schema:"caseproof-clearbrief-review-v1",case_id:caseId,
      snapshot_hash:"b".repeat(64),revision:0});
    throw Error("unexpected request");
  };
  const document={getElementById:get,createElement:()=>new Element()};
  const window={caseproofSession:{caseId,briefVersionId:briefId,getBearer:async()=>"test"}};
  vm.runInNewContext(fs.readFileSync("apps/web/clearbrief/workspace.js","utf8"),
    {document,window,fetch,console,setTimeout});
  await get("connection-form").listeners.submit({preventDefault(){}});
  get("observations").children[0].listeners.click();
  await new Promise(r=>setTimeout(r,0));
  await new Promise(r=>setTimeout(r,0));
  const passage=get("source-preview").children.find(x=>x.className==="matched-passage");
  const mark=passage.children.find(x=>x.className==="matched");
  assert.equal(mark.textContent,span);
  assert.equal(passage.children.map(x=>x.textContent).join(""),text);
});

test("page provenance keeps physical, printed and bundle spaces distinct",async()=>{
  const preview=await runObservationPreview({reference_id:"ref-01",state:"exact_match",
    source_id:"source",source_version_id:"version-a",source_sha256:"a".repeat(64),
    representation_id:"representation-a",text_start:5,text_end:14},
    {spans:[[0,22,"text",2]],page_mappings:[{pdf_page:2,printed_page:5,bundle_page:9}]});
  assert(preview.children.some(x=>x.textContent===
    "Page provenance · physical PDF page: 2 · printed label: 5 · bundle position: 9"));
});

test("page provenance abstains per space when nothing is recorded",async()=>{
  const preview=await runObservationPreview({reference_id:"ref-01",state:"exact_match",
    source_id:"source",source_version_id:"version-a",source_sha256:"a".repeat(64),
    representation_id:"representation-a",text_start:5,text_end:14},
    {spans:[[0,22,"text",null]],page_mappings:[]});
  assert(preview.children.some(x=>x.textContent===
    "Page provenance · physical PDF page: not mapped · printed label: not mapped · bundle position: not mapped"));
});

function observation(referenceId, state) {
  return {reference_id:referenceId,state,source_id:"source",source_version_id:"version",
    source_sha256:"a".repeat(64),representation_id:"rep",text_start:0,text_end:3};
}

async function runChecks() {
  const nodes=new Map();
  const get=id=>{ if(!nodes.has(id)) nodes.set(id,new Element()); return nodes.get(id); };
  const caseId="11111111-1111-4111-8111-111111111111";
  const briefId="22222222-2222-4222-8222-222222222222";
  const response=data=>({ok:true,json:async()=>data});
  const check={schema:"caseproof-m2-check-headless-v1",case_id:caseId,brief_version_id:briefId,
    snapshot_hash:"b".repeat(64),declared:[["source","version"]],processed:[["source","version"]],
    excluded:[],incomplete:[],
    citation_observations:[observation("r-clean","exact_match"),
      observation("r-unmapped","page_unmapped"),observation("r-missing","quote_not_found")],
    factual_observations:[]};
  const fetch=async url=>{
    if(url.endsWith("/check")) return response(check);
    if(url.endsWith("/sources")) return response({schema:"caseproof-clearbrief-brief-sources-v1",
      case_id:caseId,brief_version_id:briefId,rows:[]});
    if(url.endsWith("/review")) return response({schema:"caseproof-clearbrief-review-v1",
      case_id:caseId,snapshot_hash:"b".repeat(64),revision:0});
    throw Error("unexpected request");
  };
  const document={getElementById:get,createElement:()=>new Element()};
  const window={caseproofSession:{caseId,briefVersionId:briefId,getBearer:async()=>"test"}};
  vm.runInNewContext(fs.readFileSync("apps/web/clearbrief/workspace.js","utf8"),
    {document,window,fetch,console,setTimeout});
  await get("connection-form").listeners.submit({preventDefault(){}});
  return {observations:get("observations"),toggle:get("observations-filter")};
}

test("observations render exceptions first with an explicit show-all toggle",async()=>{
  const {observations,toggle}=await runChecks();
  assert(toggle.textContent.includes("Show all 3"));
  assert(toggle.textContent.includes("2 to review first"));
  assert(toggle.textContent.includes("1 clean"));
  const order=()=>observations.children.map(x=>x.children[1].textContent);
  assert.deepEqual(order(),["Reference r-unmapped","Reference r-missing","Reference r-clean"]);
  await toggle.onclick();
  assert(toggle.textContent.includes("Exceptions first"));
  assert.deepEqual(order(),["Reference r-clean","Reference r-unmapped","Reference r-missing"]);
  await toggle.onclick();
  assert.deepEqual(order(),["Reference r-unmapped","Reference r-missing","Reference r-clean"]);
});


test("quote-free reference has a resolved source but no quotation anchor or support claim",async()=>{
  const preview=await runObservationPreview({reference_id:"ref-01",state:"reference_checked_no_quotation",
    source_id:"source",source_version_id:"version-a",source_sha256:"a".repeat(64),
    representation_id:"representation-a",text_start:null,text_end:null});
  const caption=preview.children.find(x=>x.textContent.includes("no quotation to anchor"));
  assert(caption && caption.textContent.includes("Source resolved"));
  assert(caption.textContent.includes("support not assessed"));
  assert(!caption.textContent.includes("Unresolved anchor"));
  assert(!preview.children.some(x=>x.className==="matched-passage"));
});
