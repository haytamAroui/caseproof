# Word integration spike (synthetic only)

This read-only task pane is an initial host experiment, not M3 acceptance. It reads a selected passage and displays a fixed synthetic example. It does not search, authenticate, connect to the API, verify evidence, insert citations, save results, or handle customer data. Selection is rendered as text, never HTML. The manifest requests `ReadDocument` only.

For local sideloading, serve this directory over trusted HTTPS at `https://localhost:3000`, then sideload `manifest.xml` using the Word host's development add-in workflow. Office.js is loaded from Microsoft's Office CDN; the developer environment needs access to it. The manifest URL and certificate trust must match the actual developer host; do not deploy it as-is.

No Word host has been tested for this change. Record host/version and test results before claiming support. The next step is a safe, revision-bound insertion design and real host tests; do not infer citation support from this read-only shell. Follow `docs/m3/WORD_INTEGRATION_ACCEPTANCE.md` and do not use confidential documents.
