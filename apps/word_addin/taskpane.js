/* Development-only task pane. No tokens, document text, or results are persisted. */
(() => {
  const button = document.getElementById('inspect');
  const queryInput = document.getElementById('query');
  const status = document.getElementById('status');
  const result = document.getElementById('result');
  const selectionView = document.getElementById('selection');
  const coverage = document.getElementById('coverage');
  const hitsView = document.getElementById('hits');
  let busy = false;
  let uncertain = false;
  let generation = 0;

  // Supplied in memory by an authenticated host composition, not document XML.
  // No provider is installed in this spike; it must never be mocked as real auth.
  function session() {
    const provider = window.caseproofSession;
    if (!provider || typeof provider.getBearer !== 'function' ||
        typeof provider.caseId !== 'string' || !provider.caseId ||
        typeof provider.briefVersionId !== 'string' || !provider.briefVersionId) {
      throw new Error('No authenticated matter session is connected.');
    }
    return provider;
  }
  async function search(provider, query) {
    const token = await provider.getBearer();
    if (typeof token !== 'string' || !token.trim() || token.length > 8192) throw new Error('Session expired.');
    const url = `/v2/matters/${encodeURIComponent(provider.caseId)}/briefs/${encodeURIComponent(provider.briefVersionId)}/evidence/search`;
    const response = await fetch(url, {
      method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ query }),
    });
    if (!response.ok) throw new Error('Evidence search is unavailable or access was revoked.');
    const data = await response.json();
    if (data.schema !== 'caseproof-evidence-search-v1' || data.case_id !== provider.caseId ||
        data.brief_version_id !== provider.briefVersionId || !Array.isArray(data.hits) ||
        !['complete', 'partial'].includes(data.coverage) || !Number.isSafeInteger(data.exhibit_revision)) {
      throw new Error('Evidence response could not be verified.');
    }
    return data;
  }
  async function capture() {
    return Word.run(async (context) => {
      const selected = context.document.getSelection();
      const body = context.document.body;
      selected.load('text');
      body.load('text');
      await context.sync();
      const text = selected.text;
      const documentText = body.text;
      if (typeof text !== 'string' || !text.trim() || text.length > 1000 ||
          typeof documentText !== 'string' || documentText.length > 200000 ||
          documentText.indexOf(text) < 0 || documentText.indexOf(text) !== documentText.lastIndexOf(text)) {
        throw new Error('Select one unique passage in the document body.');
      }
      return { text, documentText };
    });
  }
  function identity(hit) {
    return JSON.stringify([hit.source_id, hit.source_version_id, hit.representation_id,
      hit.source_sha256, hit.locator, hit.page, hit.start, hit.end, hit.text, hit.citation]);
  }
  async function insert(provider, query, original, snapshot, hit, action) {
    if (busy || uncertain || action.disabled) return;
    if (provider.mode !== 'synthetic') {
      status.textContent = 'Citation editing is restricted to the synthetic development session.';
      return;
    }
    busy = true;
    action.disabled = true;
    status.textContent = 'Rechecking evidence and document…';
    let submitted = false;
    let succeeded = false;
    try {
      const fresh = await search(provider, query);
      if (fresh.case_id !== snapshot.case_id || fresh.brief_version_id !== snapshot.brief_version_id ||
          fresh.exhibit_revision !== snapshot.exhibit_revision ||
          !fresh.hits.some(candidate => identity(candidate) === identity(hit))) {
        throw new Error('Evidence or exhibit mapping changed. Search again.');
      }
      if (!hit.citation || (!Number.isSafeInteger(hit.citation.pdf_page) || hit.citation.pdf_page < 1) ||
          typeof hit.citation.label !== 'string' || !hit.citation.label.trim() ||
          hit.citation.label.length > 160 || /[\r\n]/.test(hit.citation.label)) {
        throw new Error('This passage has no unambiguous confirmed citation.');
      }
      await Word.run(async (context) => {
        const selected = context.document.getSelection();
        const body = context.document.body;
        selected.load('text');
        body.load('text');
        await context.sync();
        if (selected.text !== original.text || body.text !== original.documentText) {
          throw new Error('The document or selection changed. Search again.');
        }
        submitted = true;
        selected.insertText(` (${hit.citation.label}, p. ${hit.citation.pdf_page})`, 'After');
        await context.sync();
      });
      succeeded = true;
      result.hidden = true;
      status.textContent = 'Citation inserted. Use Word Undo if needed; recheck the changed draft.';
      generation += 1;
    } catch (error) {
      if (submitted) {
        uncertain = true;
        status.textContent = 'The edit outcome is unknown. Inspect the document and reconcile the edit before any retry.';
      } else {
        status.textContent = error instanceof Error ? error.message : 'The citation could not be inserted.';
      }
    } finally {
      busy = false;
      if (!uncertain && !succeeded) action.disabled = false;
    }
  }
  function render(provider, query, original, data) {
    hitsView.replaceChildren();
    selectionView.textContent = original.text;
    coverage.textContent = data.coverage === 'complete' ? 'Search scope: complete.' :
      `Search scope is partial; ${data.omitted_sources} source(s) were not searched.`;
    if (!data.hits.length) {
      const empty = document.createElement('p');
      empty.textContent = 'No matching passages found.';
      hitsView.appendChild(empty);
    }
    for (const hit of data.hits) {
      const article = document.createElement('article');
      const source = document.createElement('p');
      source.className = 'label';
      source.textContent = hit.citation ? `${hit.citation.label} · PDF page ${hit.citation.pdf_page}` : 'Citation mapping unavailable';
      const excerpt = document.createElement('blockquote');
      excerpt.textContent = hit.text;
      const action = document.createElement('button');
      action.textContent = 'Insert citation';
      action.disabled = !hit.citation || provider.mode !== 'synthetic';
      action.addEventListener('click', () => insert(provider, query, original, data, hit, action));
      article.append(source, excerpt, action);
      hitsView.appendChild(article);
    }
    result.hidden = false;
  }
  if (typeof Office === 'undefined') {
    status.textContent = 'Office could not load. Open this add-in in Word.';
    return;
  }
  Office.onReady((info) => {
    if (info.host !== Office.HostType.Word || !Office.context.requirements.isSetSupported('WordApi', '1.1')) {
      status.textContent = 'This add-in requires WordApi 1.1.';
      return;
    }
    button.disabled = false;
    status.textContent = 'Select a passage and search your matter.';
  });
  button.addEventListener('click', async () => {
    if (busy || uncertain) return;
    const current = ++generation;
    const query = queryInput.value.trim();
    result.hidden = true;
    hitsView.replaceChildren();
    if (query.length < 2 || query.length > 120 || query.split(/\s+/).length > 16) {
      status.textContent = 'Enter between 2 and 120 characters to search.';
      return;
    }
    busy = true;
    button.disabled = true;
    status.textContent = 'Searching…';
    try {
      const provider = session();
      const original = await capture();
      const data = await search(provider, query);
      if (current !== generation) return;
      render(provider, query, original, data);
      status.textContent = 'Inspect the source passage before inserting a citation.';
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : 'Evidence search failed.';
    } finally {
      busy = false;
      button.disabled = false;
    }
  });
})();
