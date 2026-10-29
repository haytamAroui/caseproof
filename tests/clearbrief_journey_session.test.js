"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

class Element{
  constructor(){this.children=[];this.listeners={};this.value="";this.textContent="";this.hidden=false;}
  addEventListener(name,fn){this.listeners[name]=fn;}
  replaceChildren(...items){this.children=items;this.textContent="";}
  append(...items){this.children.push(...items);}
  setAttribute(){}
  removeAttribute(){}
}

async function runDelayed(responsePath, eventName){
  const nodes=new Map();
  const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  const caseId="11111111-1111-4111-8111-111111111111";
  get("case-id").value=caseId;
  let resolveResponse,requested=false;
  const pending=new Promise(resolve=>{resolveResponse=resolve;});
  const fetch=async(url)=>{
    if(url===responsePath){requested=true;return pending;}
    throw Error("unexpected request "+url);
  };
  const window={caseproofSession:{caseId,briefVersionId:"22222222-2222-4222-8222-222222222222",getBearer:async()=>"signed-token"}};
  vm.runInNewContext(fs.readFileSync("apps/web/clearbrief/workspace.js","utf8"),{
    document:{getElementById:get,createElement:()=>new Element()},window,fetch,
    console,setTimeout,
  });
  const running=get(eventName).listeners.click();
  for(let i=0;i<20&&!requested;i++)await Promise.resolve();
  assert.equal(requested,true);
  get("signout").listeners.click();
  resolveResponse({ok:true,json:async()=>responsePath.endsWith("/state")?
    {schema:"dev-live-txt-v1",sources:[{text:"CONFIDENTIAL SOURCE"}],briefs:[]}:
    {schema:"caseproof-dev-create-orgs-v1",organizations:[{name:"SECRET ORG",
      org_id:"33333333-3333-4333-8333-333333333333"}]}});
  await running;
  assert.equal(get("journey-state").textContent,"");
  assert.doesNotMatch(get("journey-result").textContent,/CONFIDENTIAL|SECRET/);
  assert.equal(get("journey-org").children.length,0);
}

test("late ingested matter state cannot render after signout",async()=>{
  await runDelayed("/dev/live/matters/11111111-1111-4111-8111-111111111111/state","journey-reopen");
});

test("late organization listing cannot render after signout",async()=>{
  await runDelayed("/dev/live/create-organizations","journey-find-orgs");
});
