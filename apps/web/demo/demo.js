/* CaseProof demo journey — loopback demo UI. All checks execute the real
   engine via the local demo API; the reviewer and case inputs are simulated. */
"use strict";

const state = { session: null, started: false, findings: null, rules: [] };

const CITATION_LABELS = {
  exact_match: ["Citation exacte", "pass"],
  quote_not_found: ["Citation introuvable", "fail"],
  reference_checked_no_quotation: ["Pièce identifiée — aucune citation textuelle à comparer", "undetermined"],
  reference_unresolved: ["Référence hors registre des pièces", "unverified"],
  reference_ambiguous: ["Pièce ambiguë ou non confirmée", "unverified"],
  representation_conflict: ["Conflit de représentation", "unverified"],
  ocr_unreliable: ["OCR non fiable", "unverified"],
  page_unmapped: ["Page non mappée", "unverified"],
  source_unavailable: ["Source indisponible", "unverified"],
  incomplete_extraction: ["Extraction incomplète", "unverified"],
  multiple_matches: ["Correspondances multiples", "unverified"],
};
const FACT_LABELS = {
  value_match: ["Correspond", "pass"],
  candidate_difference: ["Écart détecté", "fail"],
  needs_context: ["Contexte requis", "undetermined"],
  not_assessed: ["Non évalué", "unverified"],
};
const RULE_LABELS = {
  PASS: ["Conforme", "pass"], FAIL: ["Non conforme", "fail"],
  UNDETERMINED: ["Indéterminé", "undetermined"], UNVERIFIED: ["Non vérifié", "unverified"],
};
const REGION_KIND_LABELS = {
  MAIN_BODY: "corps du document", COMMENT_EXCLUDED: "commentaire",
  HIDDEN_TEXT_EXCLUDED: "texte masqué", STRUCTURED_CONTENT: "contenu structuré",
  UNKNOWN_WORD_PART: "partie Word inconnue",
};

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function chip(label, css) { return `<span class="chip ${css}">${esc(label)}</span>`; }

function showError(message) {
  const box = document.getElementById("errors");
  box.hidden = false;
  box.textContent = message;
}
function clearError() { document.getElementById("errors").hidden = true; }

async function api(path, options = {}) {
  const headers = { "x-demo-session": state.session, "origin": location.origin, ...(options.headers || {}) };
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.message ? ` — ${data.message}` : "";
    const missing = data.missing ? ` (${data.missing.join(", ")})` : "";
    throw new Error(`${data.error || `HTTP ${response.status}`}${detail}${missing}`);
  }
  return data;
}
async function post(path, body, headers = { "content-type": "application/json" }) {
  return api(path, { method: "POST", body: headers["content-type"] === "application/json" ? JSON.stringify(body) : body, headers });
}

function excerptHtml(excerpt) {
  if (!excerpt) return "<p class=\"meta\">Passage source non localisé.</p>";
  return `<p>${excerpt.truncated_start ? "… " : ""}${esc(excerpt.before)}<span class="match">${esc(excerpt.match)}</span>${esc(excerpt.after)}${excerpt.truncated_end ? " …" : ""}</p>`;
}

function renderExtraction(extraction, warnings) {
  if (!extraction) return "";
  const rows = (extraction.citations || []).map((c) => `
    <tr><td><code>${esc(c.marker_id)}</code></td><td>${esc(c.target)}</td>
    <td>${c.has_quote ? "avec citation" : "sans citation textuelle"}</td>
    <td>${esc(c.exhibit_label)}</td></tr>`).join("");
  const warningList = (warnings || []).map((w) => `<li>${esc(w)}</li>`).join("");
  return `
    <p class="meta">Extraction des citations : automatique et déterministe depuis le texte réellement lu
      (sans LLM, à valider par l'avocat) — ${(extraction.citations || []).length} référence(s) détectée(s)${extraction.orphan_quotes ? `, ${extraction.orphan_quotes} citation(s) sans référence` : ""}.</p>
    ${rows ? `<table><tr><th>Réf.</th><th>Citation détectée</th><th>Citation textuelle</th><th>Pièce résolue</th></tr>${rows}</table>` : ""}
    ${warningList ? `<ul class="warn-note">${warningList}</ul>` : ""}`;
}

function renderDocument(doc) {
  const regions = doc.regions
    .filter((r) => r.status !== "READ")
    .map((r) => `<li>${esc(REGION_KIND_LABELS[r.kind] || r.kind)} — ${esc(r.part)} : <strong>${esc(r.status)}</strong></li>`)
    .join("");
  document.getElementById("document").innerHTML = `
    <p><strong>${doc.body_read ? "Document courant" : "Fichier sélectionné (lecture refusée)"} :</strong> ${esc(doc.name)} · sha256 <code>${esc(doc.sha256.slice(0, 12))}…</code>${doc.body_read && doc.active_version ? ` · version vérifiée : <code>${esc(doc.active_version)}</code>` : ""}</p>
    ${doc.body_read
      ? `<p class="ok-note">Corps lu par le lecteur Word du produit (mesure réelle).</p>`
      : `<p class="warn-note">Le lecteur Word du produit refuse le corps de ce fichier (fail-closed) — ce fichier n'est PAS le document vérifié et aucune vérification n'est possible tant qu'il est sélectionné :</p><ul>${regions}</ul>`}
    ${doc.body_read ? renderExtraction(doc.extraction, doc.extraction_warnings) : ""}
    <p>Téléverser un autre .docx pour le mesurer et le vérifier :
      <input type="file" id="upload" accept=".docx"></p>
    <p class="meta" id="upload-status"></p>`;
  document.getElementById("upload").addEventListener("change", onUpload);
  // Le bouton de vérification n'est actif que si le corps du document est lisible ;
  // tout changement de document invalide l'export du résultat précédent.
  document.getElementById("run").disabled = !doc.body_read;
  document.getElementById("export-json").disabled = true;
  document.getElementById("export-html").disabled = true;
}

async function onUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  clearError();
  const status = document.getElementById("upload-status");
  status.textContent = "Lecture du fichier…";
  try {
    const bytes = await file.arrayBuffer();
    const result = await post("/demo/api/document", bytes, {
      "content-type": "application/octet-stream",
      "x-demo-filename": file.name,
    });
    status.textContent = result.note;
    state.started = false;
    renderDocument({ ...result.document, active_version: result.active_version, extraction: result.extraction, extraction_warnings: result.extraction_warnings });
    // Tout résultat d'un document précédent est caduc : on l'efface partout.
    document.getElementById("findings").innerHTML = "";
    document.getElementById("rules").innerHTML = "";
    document.getElementById("correction").innerHTML = "";
    document.getElementById("run-status").textContent = "Nouveau document chargé : relancez les vérifications.";
  } catch (err) {
    status.textContent = "";
    showError(err.message);
  }
}

function renderStatic(data) {
  document.getElementById("subtitle").textContent = `${data.title} · moteur ${data.runner}`;
  document.getElementById("audience-note").textContent = data.audience_note ? ` ${data.audience_note}` : "";
  renderDocument(data.document);
  const corpusRows = data.corpus.articles.map((a) => `
    <tr><td>${esc(a.act)} art. ${esc(a.article)}</td><td>${esc(a.language)}</td>
    <td>${esc(a.version)}</td><td><a href="${esc(a.source_uri)}">${esc(a.source_uri)}</a></td>
    <td><code>${esc(a.sha256.slice(0, 12))}…</code></td></tr>`).join("");
  document.getElementById("corpus").innerHTML = `
    <p class="meta">${data.corpus.articles.length} article(s) ingéré(s), ${data.corpus.failures.length} échec(s). Originals préservés, empreinte vérifiée.</p>
    <table><tr><th>Texte</th><th>Langue</th><th>Version déclarée</th><th>Source</th><th>Empreinte</th></tr>${corpusRows}</table>`;
  const sourceRows = data.sources.map((s) => `
    <tr><td>${esc(s.label)}</td><td>${esc(s.version_id)}</td>
    <td>${s.imported ? "importée — provenance déclarée, non vérifiée" : s.synthetic ? "synthétique (créé pour la démo)" : "source publique réelle"}</td>
    <td><code>${esc(s.sha256.slice(0, 12))}…</code></td></tr>`).join("");
  const exhibitRows = (data.exhibits || []).map((e) => `
    <tr><td>${esc(e.display_label)}</td>
    <td>${e.confirmed ? "confirmée" : "NON confirmée — les références vers elle restent ambiguës"}</td>
    <td>${!e.confirmed && e.imported ? `<button class="decision exhibit-confirm" data-exhibit="${esc(e.exhibit_id)}">Confirmer la pièce (simulé)</button>` : ""}</td></tr>`).join("");
  document.getElementById("sources").innerHTML =
    `<table><tr><th>Pièce</th><th>Version</th><th>Origine</th><th>Empreinte</th></tr>${sourceRows}</table>
    <h3>Registre des pièces</h3>
    <table><tr><th>Pièce</th><th>État</th><th></th></tr>${exhibitRows}</table>
    <h3>Importer une source (texte .txt/.md, .docx ou .pdf texte-natif)</h3>
    <p class="meta">La provenance est déclarée par vous, jamais vérifiée par l'outil ; la pièce importée reste non confirmée tant que la relecture (simulée) ne l'a pas confirmée.</p>
    <p><input type="file" id="source-file" accept=".txt,.md,.docx,.pdf"></p>
    <p><input type="text" id="source-act" placeholder="Acte (ex. loi du 20 février 1991)" size="30">
    <input type="text" id="source-article" placeholder="Article (ex. 15)" size="10">
    <input type="text" id="source-alias" placeholder="Nom cité dans les conclusions" size="24"></p>
    <p><input type="text" id="source-uri" placeholder="URL de la source déclarée" size="60">
    <button id="source-import">Importer</button></p>
    <p class="meta" id="source-status"></p>`;
  document.querySelectorAll("button.exhibit-confirm").forEach((b) => b.addEventListener("click", onExhibitConfirm));
  document.getElementById("source-import").addEventListener("click", onSourceImport);
  renderFacts(data.facts);
}

function renderFacts(facts) {
  const factRows = facts.map((f) => `
    <tr><td><code>${esc(f.name)}</code></td><td>${esc(f.value)}</td>
    <td>${f.confirmed ? "confirmé" : "non confirmé"}</td>
    <td><button class="decision fact-toggle" data-name="${esc(f.name)}" data-confirmed="${f.confirmed ? "0" : "1"}">${f.confirmed ? "Retirer la confirmation" : "Confirmer (simulé)"}</button></td></tr>`).join("");
  document.getElementById("facts").innerHTML =
    `<p class="meta">La confirmation est un acte de relecture simulé : les règles déterministes sont réévaluées réellement.</p>
    <table><tr><th>Fait</th><th>Valeur</th><th>État</th><th></th></tr>${factRows}</table>`;
  document.querySelectorAll("button.fact-toggle").forEach((b) => b.addEventListener("click", onFactToggle));
}

function invalidateFindings(message) {
  state.started = false;
  document.getElementById("findings").innerHTML = "";
  document.getElementById("rules").innerHTML = "";
  document.getElementById("correction").innerHTML = "";
  document.getElementById("export-json").disabled = true;
  document.getElementById("export-html").disabled = true;
  document.getElementById("run-status").textContent = message;
}

async function refreshState() {
  const data = await api("/demo/api/state");
  renderStatic(data);
}

async function onSourceImport() {
  clearError();
  const file = document.getElementById("source-file").files[0];
  const fields = {
    act: document.getElementById("source-act").value.trim(),
    article: document.getElementById("source-article").value.trim(),
    alias: document.getElementById("source-alias").value.trim(),
    source_uri: document.getElementById("source-uri").value.trim(),
  };
  const status = document.getElementById("source-status");
  if (!file || !fields.act || !fields.article || !fields.alias || !fields.source_uri) {
    showError("Fichier et provenance déclarée (acte, article, nom cité, URL) requis.");
    return;
  }
  status.textContent = "Import en cours…";
  try {
    const bytes = await file.arrayBuffer();
    const params = new URLSearchParams({ ...fields, filename: file.name });
    const result = await post(`/demo/api/source?${params}`, bytes, { "content-type": "application/octet-stream" });
    status.textContent = result.note;
    invalidateFindings("Nouvelle source importée : relancez les vérifications.");
    await refreshState();
    document.getElementById("source-status").textContent = result.note;
  } catch (err) {
    status.textContent = "";
    showError(err.message);
  }
}

async function onExhibitConfirm(event) {
  clearError();
  try {
    const result = await post("/demo/api/exhibits/confirm", { exhibit_id: event.target.dataset.exhibit });
    invalidateFindings(result.note);
    await refreshState();
  } catch (err) { showError(err.message); }
}

async function onFactToggle(event) {
  clearError();
  const button = event.target;
  try {
    const result = await post("/demo/api/facts", {
      name: button.dataset.name, confirmed: button.dataset.confirmed === "1",
    });
    renderFacts(result.facts);
    if (result.rule_results.length) {
      document.getElementById("rules").innerHTML =
        `<h3>Règles de fond (moteur déterministe)</h3>` + result.rule_results.map(ruleCard).join("");
      bindDecisions();
    }
  } catch (err) { showError(err.message); }
}

function decisionButtons(observationId, kind) {
  return `<div class="decisions-row">
    <button class="decision" data-obs="${esc(observationId)}" data-disp="confirmed_candidate">Écart confirmé</button>
    <button class="decision" data-obs="${esc(observationId)}" data-disp="dismissed">Écarté</button>
    <button class="decision" data-obs="${esc(observationId)}" data-disp="needs_information">Info requise</button>
    <span class="meta" id="decided-${esc(observationId)}"></span>
  </div>`;
}

function citationCard(obs, afterCorrection) {
  const [label, css] = CITATION_LABELS[obs.state] || [obs.state, "unverified"];
  return `<div class="card">
    <h3>${chip(label, css)} référence <code>${esc(obs.reference_id)}</code>${afterCorrection ? " — après correction" : ""}</h3>
    <p>${esc(obs.scope_note || "")}</p>
    ${obs.quote ? `<div class="sidebyside"><div><strong>Citation dans les conclusions</strong><p>${esc(obs.quote)}</p></div>
    <div><strong>Passage source</strong>${excerptHtml(obs.source_excerpt)}</div></div>` : ""}
    ${obs.source_label ? `<p class="meta">Source : ${esc(obs.source_label)}</p>` : ""}
    ${obs.source_excerpt ? `<p class="meta">${obs.source_pdf_page != null
      ? `Page physique ${obs.source_pdf_page} du PDF — résolue du passage vérifié, jamais déclarée`
      : "Page non mappée — la navigation se fait par la citation exacte ci-dessus"}</p>` : ""}
    ${["exact_match"].includes(obs.state) ? "" : decisionButtons(obs.observation_id)}
  </div>`;
}

function factCard(obs, afterCorrection) {
  const [label, css] = FACT_LABELS[obs.state] || [obs.state, "unverified"];
  return `<div class="card">
    <h3>${chip(label, css)} fait <code>${esc(obs.claim_id)}</code>${afterCorrection ? " — après correction" : ""}</h3>
    <p><strong>${esc(obs.kind)} (${esc(obs.role)})</strong> — ${esc(obs.explanation)}</p>
    <div class="sidebyside"><div><strong>Conclusions</strong><p>${esc(obs.brief_passage || "")}</p>
    <p>Valeur : <code>${esc(obs.brief_token)}</code></p></div>
    <div><strong>Passage source</strong>${excerptHtml(obs.source_excerpt)}
    <p>Valeur : <code>${esc(obs.source_token)}</code></p></div></div>
    ${obs.state === "value_match" ? "" : decisionButtons(obs.observation_id)}
  </div>`;
}

function ruleCard(result) {
  const [label, css] = RULE_LABELS[result.status] || [result.status, "unverified"];
  const decision = result.decision
    ? `<p class="ok-note">Décision (simulée) : ${esc(result.decision.disposition)} — ${esc(result.decision.rationale)} (validité : ${esc(result.decision.validity)})</p>`
    : "";
  const subs = (result.subresults || []).map(([k, v]) => `<li><code>${esc(k)}</code> : ${esc(v)}</li>`).join("");
  return `<div class="card">
    <h3>${chip(label, css)} ${esc(result.rule_id)} <small>v${esc(result.rule_version)}</small></h3>
    <p><strong>Référence :</strong> ${esc(result.reference)}</p>
    <p><strong>Motif :</strong> ${esc(result.reason)}</p>
    ${subs ? `<ul>${subs}</ul>` : ""}
    ${decision}
    <div class="decisions-row">
      ${["confirmed", "qualified", "rejected", "waived"].map((d) =>
        `<button class="decision rule-decision" data-rule="${esc(result.rule_id)}" data-disp="${d}">${{ confirmed: "Confirmé", qualified: "Qualifié", rejected: "Rejeté", waived: "Dérogation" }[d]}</button>`).join("")}
      <span class="meta" id="rule-decided-${esc(result.rule_id)}"></span>
    </div>
  </div>`;
}

function renderCorrection(findings) {
  const targets = findings.citations.filter((c) => c.state !== "exact_match" && c.quote);
  const box = document.getElementById("correction");
  if (!targets.length) {
    box.innerHTML = `<p class="meta">Aucune citation à corriger dans la version courante.</p>`;
    return;
  }
  const target = targets[0];
  box.innerHTML = `
    <p>Corriger une citation dans les conclusions (passe <code>${esc(target.reference_id)}</code>), puis le moteur revérifie réellement tout le dossier :</p>
    <p><strong>Texte actuel :</strong></p><p><code>${esc(target.quote)}</code></p>
    <textarea id="correction-after" placeholder="Texte corrigé (aligné sur la source)"></textarea>
    <input type="text" id="correction-rationale" placeholder="Motif de la correction">
    <button id="correct" class="primary">Corriger et revérifier</button>
    <div id="correction-result"></div>`;
  document.getElementById("correct").addEventListener("click", () => onCorrect(target.reference_id));
}

async function onCorrect(referenceId) {
  clearError();
  const after = document.getElementById("correction-after").value.trim();
  const rationale = document.getElementById("correction-rationale").value.trim();
  if (!after || !rationale) { showError("Texte corrigé et motif requis."); return; }
  try {
    const result = await post("/demo/api/correction", {
      passage_id: `passage:${referenceId}`,
      after, rationale,
    });
    const flips = Object.entries(result.flips).map(([ref, f]) =>
      `<li><code>${esc(ref)}</code> : ${esc(f.before)} → ${esc(f.after)}</li>`).join("");
    document.getElementById("findings").innerHTML =
      result.findings.citations.map((c) => citationCard(c, true)).join("") +
      result.findings.facts.map((f) => factCard(f, true)).join("");
    renderCorrection(result.findings);
    bindDecisions();
    document.getElementById("correction").insertAdjacentHTML("afterbegin", `
      <div id="correction-feedback">
      <p class="ok-note">Nouvelle version ${esc(result.brief_version)} revérifiée (instantané <code>${esc(result.snapshot.slice(0, 12))}…</code>).</p>
      <ul>${flips}</ul>
      <p class="meta">${esc(result.note)}</p></div>`);
  } catch (err) { showError(err.message); }
}

async function onDecision(event) {
  const button = event.target;
  const rationale = window.prompt("Motif de la décision (relecture simulée) :");
  if (!rationale) return;
  clearError();
  try {
    const result = await post("/demo/api/review", {
      observation_id: button.dataset.obs, disposition: button.dataset.disp, rationale,
    });
    document.getElementById(`decided-${button.dataset.obs}`).textContent =
      `enregistré (révision ${result.revision}) — transmission toujours verrouillée : ${result.release_ready}`;
  } catch (err) { showError(err.message); }
}

async function onRuleDecision(event) {
  const button = event.target;
  const rationale = window.prompt("Motif (relecture simulée) :");
  if (!rationale) return;
  clearError();
  try {
    const result = await post("/demo/api/rule-decision", {
      rule_id: button.dataset.rule, disposition: button.dataset.disp,
      rationale, scope: "dossier de démonstration",
    });
    document.getElementById(`rule-decided-${button.dataset.rule}`).textContent =
      `enregistré : ${result.disposition} (statut machine inchangé : ${result.machine_status}, validité : ${result.validity})`;
  } catch (err) { showError(err.message); }
}

function bindDecisions() {
  document.querySelectorAll("button.decision:not(.rule-decision)").forEach((b) => b.addEventListener("click", onDecision));
  document.querySelectorAll("button.rule-decision").forEach((b) => b.addEventListener("click", onRuleDecision));
}

async function onRun() {
  clearError();
  document.getElementById("run-status").textContent = "Vérification en cours…";
  try {
    const result = await post("/demo/api/run", {});
    state.started = true;
    state.findings = result.findings;
    document.getElementById("run-status").textContent =
      `Exécution réelle terminée — instantané ${result.snapshot.slice(0, 12)}…`;
    document.getElementById("export-json").disabled = false;
    document.getElementById("export-html").disabled = false;
    document.getElementById("findings").innerHTML =
      result.findings.citations.map((c) => citationCard(c, false)).join("") +
      result.findings.facts.map((f) => factCard(f, false)).join("");
    document.getElementById("rules").innerHTML =
      `<h3>Règles de fond (moteur déterministe)</h3>` + result.rule_results.map(ruleCard).join("");
    renderCorrection(result.findings);
    bindDecisions();
  } catch (err) {
    document.getElementById("run-status").textContent = "";
    showError(err.message);
  }
}

function download(path, filename) {
  clearError();
  fetch(path, { headers: { "x-demo-session": state.session } })
    .then(async (response) => {
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error === "run_first" ? "Lancez d'abord les vérifications." : (data.error || `HTTP ${response.status}`));
      }
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);
    })
    .catch((err) => showError(err.message));
}

async function boot() {
  try {
    const data = await api("/demo/api/state");
    state.session = data.session;
    renderStatic(data);
    document.getElementById("run").addEventListener("click", onRun);
    document.getElementById("export-json").addEventListener("click", () => download("/demo/api/export.json", "caseproof-demo-export.json"));
    document.getElementById("export-html").addEventListener("click", () => download("/demo/api/export.html", "caseproof-demo-rapport.html"));
  } catch (err) { showError(err.message); }
}

boot();
