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
