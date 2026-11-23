"use strict";
/* Page-image rendering, zoom overlay lifecycle and stale-response cleanup.
   Synthetic fixture data only; the shim models the DOM surface workspace.js
   uses for this flow, nothing more. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const CASE = "11111111-1111-4111-8111-111111111111";
const BRIEF = "22222222-2222-4222-8222-222222222222";
const SHA = "a".repeat(64);

function makeDom() {
  const dom = { activeElement: null, keydown: [] };
  class Element {
    constructor() {
      this.children = []; this.listeners = {}; this.value = "";
      this.textContent = ""; this.className = ""; this.parentNode = null;
      this.nextSibling = null; this.type = ""; this.hidden = false;
    }
    append(...nodes) { for (const n of nodes) { n.parentNode = this; this.children.push(n); } }
    replaceChildren(...nodes) {
      for (const c of this.children) c.parentNode = null;
      this.children = nodes;
      for (const n of nodes) n.parentNode = this;
      this.textContent = "";
    }
    insertBefore(node, ref) {
      node.parentNode = this;
      const i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) this.children.push(node); else this.children.splice(i, 0, node);
    }
    removeChild(node) {
      this.children = this.children.filter(c => c !== node);
      node.parentNode = null;
    }
    get firstChild() { return this.children[0]; }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    setAttribute() {}
    removeAttribute() {}
    focus() { dom.activeElement = this; }
    click() { if (this.listeners.click) this.listeners.click({ target: this }); }
  }
  const nodes = new Map();
  const get = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  const document = {
    getElementById: get,
    createElement: () => new Element(),
    body: new Element(),
    addEventListener(name, handler) { (dom[name] = dom[name] || []).push(handler); },
    removeEventListener(name, handler) {
      dom[name] = (dom[name] || []).filter(h => h !== handler);
    },
  };
  return { dom, document, get, Element };
}

function findClass(root, cls, out = []) {
  for (const c of root.children || []) {
    if (!c || !Array.isArray(c.children)) continue;
    if (String(c.className).split(" ").includes(cls)) out.push(c);
    findClass(c, cls, out);
  }
  return out;
}

async function boot({ pageFetch, observations }) {
  const { dom, document, get } = makeDom();
  const created = [], revoked = [];
  const row = { source_id: "source", version_id: "version-a", original_sha256: SHA,
    representation_id: "representation-a", media_type: "application/pdf", warnings: [], pages: [] };
  const json = data => ({ ok: true, json: async () => data });
  const fetch = async url => {
    if (url.endsWith("/check")) return json({ schema: "caseproof-m2-check-headless-v1",
      case_id: CASE, brief_version_id: BRIEF, snapshot_hash: "b".repeat(64),
      citation_observations: observations, factual_observations: [] });
    if (url.endsWith("/sources")) return json({ schema: "caseproof-clearbrief-brief-sources-v1",
      case_id: CASE, brief_version_id: BRIEF, rows: [row] });
    if (url.endsWith("/sources/source")) return json({ schema: "caseproof-clearbrief-brief-source-preview-v1",
      case_id: CASE, brief_version_id: BRIEF, row, text: "sensitive version text",
      spans: [[0, 10, "pdf", 1]],
      page_mappings: [{ pdf_page: 1, printed_page: 3, bundle_page: 7 }] });
    if (url.endsWith("/review")) return json({ schema: "caseproof-clearbrief-review-v1",
      case_id: CASE, snapshot_hash: "b".repeat(64), revision: 0 });
    if (url.endsWith("/pages/1")) return pageFetch();
    throw Error("unexpected request " + url);
  };
  const window = { caseproofSession: { caseId: CASE, briefVersionId: BRIEF, getBearer: async () => "test" } };
  const Image = class { constructor() { this.src = ""; this.alt = ""; } };
  const URLShim = {
    createObjectURL(blob) { const u = "blob:fake-" + (created.length + 1); created.push(u); return u; },
    revokeObjectURL(u) { revoked.push(u); },
  };
  vm.runInNewContext(fs.readFileSync("apps/web/clearbrief/workspace.js", "utf8"),
    { document, window, fetch, console, setTimeout, Image, URL: URLShim });
  // Model the review-card parent the product inserts the image block into.
  const card = get("review-card-parent");
  card.append(get("source-preview"));
  await get("connection-form").listeners.submit({ preventDefault() {} });
  return { dom, document, get, created, revoked, card };
}

const flush = async (n = 4) => { for (let i = 0; i < n; i++) await new Promise(r => setTimeout(r, 0)); };

const OBS_A = { reference_id: "ref-01", state: "exact_match", source_id: "source",
  source_version_id: "version-a", source_sha256: SHA, representation_id: "representation-a",
  text_start: 5, text_end: 14 };
const OBS_B = { reference_id: "ref-02", state: "reference_unresolved", source_id: "source",
  source_version_id: "version-a", source_sha256: SHA, representation_id: "representation-a",
  text_start: null, text_end: null };

test("mapped PDF finding renders digest-checked page image and zoom with keyboard close and focus restore", async () => {
  const env = await boot({ observations: [OBS_A],
    pageFetch: async () => ({ ok: true,
      headers: { get: k => (k === "x-caseproof-original-sha256" ? SHA : null) },
      blob: async () => "PNGBYTES" }) });
  const { dom, get, created } = env;
  get("observations").children[0].listeners.click();
  await flush();
  const boxes = findClass(get("review-card-parent"), "page-image");
  assert.equal(boxes.length, 1, "one page-image block attached beside the preview");
  const img = boxes[0].children.find(c => c instanceof Object && "src" in c && c.alt);
  assert(img, "image element rendered");
  assert.equal(img.src, "blob:fake-1");
  assert.equal(created.length, 1);
  const openBtn = boxes[0].children.find(c => String(c.className || "").includes("page-zoom-open"));
  openBtn.listeners.click();
  const zooms = findClass(env.document.body, "page-zoom");
  assert.equal(zooms.length, 1, "zoom overlay open");
  const closeBtn = zooms[0].children[0].children.find(c => c.textContent === "Close");
  assert.equal(dom.activeElement, closeBtn, "focus lands on Close");
  // Escape closes and focus returns to the invoking button.
  assert.equal(dom.keydown.length, 1, "keydown handler registered");
  dom.keydown[0]({ key: "Escape" });
  assert.equal(findClass(env.document.body, "page-zoom").length, 0, "Escape closes overlay");
  assert.equal(dom.keydown.length, 0, "keydown handler removed");
  assert.equal(dom.activeElement, openBtn, "focus restored to the open button");
});

test("stale page response cannot land on a newer finding and leaves no blob behind", async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const env = await boot({ observations: [OBS_A, OBS_B],
    pageFetch: async () => { await gate; return { ok: true,
      headers: { get: k => (k === "x-caseproof-original-sha256" ? SHA : null) },
      blob: async () => "PNGBYTES" }; } });
  const { get, created, revoked } = env;
  get("observations").children[0].listeners.click();
  await flush();
  assert.equal(findClass(get("review-card-parent"), "page-image").length, 1,
    "loading block attached for the first finding");
  // Switch finding while the page fetch is still in flight.
  get("observations").children[1].listeners.click();
  await flush();
  release();
  await flush();
  assert.equal(created.length, 0, "late response never mints a blob URL");
  const boxes = findClass(get("review-card-parent"), "page-image");
  assert.equal(boxes.length, 0, "no page image on the text-only finding");
  assert.equal(revoked.length, 0, "nothing to revoke because nothing was created");
});

test("unavailable physical page fails visibly without an image", async () => {
  const env = await boot({ observations: [OBS_A],
    pageFetch: async () => ({ ok: false, status: 404 }) });
  const { get, created } = env;
  get("observations").children[0].listeners.click();
  await flush();
  const boxes = findClass(get("review-card-parent"), "page-image");
  assert.equal(boxes.length, 1);
  assert(boxes[0].children.some(c => String(c.textContent).includes("unavailable")),
    "honest unavailable message");
  assert(!boxes[0].children.some(c => c && c.src), "no image element");
  assert.equal(created.length, 0);
});
