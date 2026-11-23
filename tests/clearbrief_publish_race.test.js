"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

class Element{
  constructor(){this.children=[];this.listeners={};this.value="";this.textContent="";this.hidden=false;this.disabled=false;}
  addEventListener(name,fn){this.listeners[name]=fn;}
  replaceChildren(...items){this.children=items;this.textContent="";}
  append(...items){this.children.push(...items);}
  setAttribute(){}
  removeAttribute(){}
}

const CASE_A="11111111-1111-4111-8111-111111111111";
const CASE_B="99999999-9999-4999-8999-999999999999";
const BRIEF_1="22222222-2222-4222-8222-222222222222";
const BRIEF_2="44444444-4444-4444-8444-444444444444";
const DOC="55555555-5555-4555-8555-555555555555";
const VERSION="66666666-6666-4666-8666-666666666666";

async function flush(times=30){for(let i=0;i<times;i++)await Promise.resolve();}

function setup(){
  const nodes=new Map();
  const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  get("case-id").value=CASE_A;
  get("brief-id").value=BRIEF_1;
  get("upload-document").value=DOC;
  get("upload-version").value=VERSION;
  let resolvePublish;
  const pendingPublish=new Promise(resolve=>{resolvePublish=resolve;});
  const HASH="a".repeat(64);
  const fetch=async(url)=>{
    const u=String(url);
    if(u.endsWith("/briefs/publish"))return pendingPublish;
    if(u.endsWith("/check"))return {ok:true,status:200,json:async()=>({
      schema:"caseproof-m2-check-headless-v1",case_id:CASE_A,brief_version_id:BRIEF_2,
      snapshot_hash:HASH,declared:[],processed:[],excluded:[],incomplete:[],
      citation_observations:[],factual_observations:[]})};
    if(u.endsWith("/sources"))return {ok:true,status:200,json:async()=>({
      schema:"caseproof-clearbrief-brief-sources-v1",case_id:CASE_A,brief_version_id:BRIEF_2,
      rows:[],complete:true})};
    if(u.endsWith("/review"))return {ok:true,status:200,json:async()=>({
      schema:"caseproof-clearbrief-review-v1",case_id:CASE_A,snapshot_hash:HASH,revision:0,
      decisions:[]})};
    return {ok:true,status:200,json:async()=>({schema:"unrelated"})};
  };
  const window={caseproofSession:{caseId:CASE_A,briefVersionId:BRIEF_1,getBearer:async()=>"signed-token"}};
  vm.runInNewContext(fs.readFileSync("apps/web/clearbrief/workspace.js","utf8"),{
    document:{getElementById:get,createElement:()=>new Element()},window,fetch,
    console,setTimeout,
  });
  return {get,window,resolvePublish};
}

function publishResponse(){
  return {ok:true,status:201,json:async()=>({
    schema:"caseproof-signed-brief-publish-v1",published_revision:2,brief_version_id:BRIEF_2})};
}

test("confirmed publish survives a legitimate same-context refresh",async()=>{
  const {get,resolvePublish}=setup();
  const evt={preventDefault(){}};
  await get("connection-form").listeners.submit(evt);
  const running=get("publish-form").listeners.submit(evt);
  await flush();
  get("refresh").listeners.click();
  await flush();
  resolvePublish(publishResponse());
  await running;await flush();
  assert.match(get("publish-status").textContent,/Scope current after publication at revision 2/);
  assert.equal(get("brief-id").value,BRIEF_2);
});

test("late confirmed publish does not replace a switched document/version selection",async()=>{
  const {get,resolvePublish}=setup();
  const evt={preventDefault(){}};
  await get("connection-form").listeners.submit(evt);
  const running=get("publish-form").listeners.submit(evt);
  await flush();
  get("upload-document").value="77777777-7777-4777-8777-777777777777";
  get("upload-version").value="88888888-8888-4888-8888-888888888888";
  resolvePublish(publishResponse());
  await running;await flush();
  assert.equal(get("publish-status").textContent,"");
  assert.equal(get("brief-id").value,BRIEF_1);
  assert.equal(get("upload-document").value,"77777777-7777-4777-8777-777777777777");
  assert.equal(get("upload-version").value,"88888888-8888-4888-8888-888888888888");
});

test("late confirmed publish is discarded after a matter switch",async()=>{
  const {get,window,resolvePublish}=setup();
  const evt={preventDefault(){}};
  await get("connection-form").listeners.submit(evt);
  const running=get("publish-form").listeners.submit(evt);
  await flush();
  get("signout").listeners.click();
  await flush();
  window.caseproofSession={caseId:CASE_B,briefVersionId:BRIEF_1,getBearer:async()=>"other-token"};
  get("case-id").value=CASE_B;
  void get("connection-form").listeners.submit(evt);
  await flush();
  resolvePublish(publishResponse());
  await running;await flush();
  assert.equal(get("publish-status").textContent,"");
  assert.equal(get("brief-id").value,BRIEF_1);
});

test("late confirmed publish is discarded after signout",async()=>{
  const {get,resolvePublish}=setup();
  const evt={preventDefault(){}};
  await get("connection-form").listeners.submit(evt);
  const running=get("publish-form").listeners.submit(evt);
  await flush();
  get("signout").listeners.click();
  await flush();
  resolvePublish(publishResponse());
  await running;await flush();
  assert.equal(get("publish-status").textContent,"");
  assert.equal(get("brief-id").value,BRIEF_1);
});
