# Synthetic Word evidence workflow

This is a development-only Word integration spike. It connects a task pane to a **localhost-only synthetic API**. Select a unique body passage in a synthetic Word document, search `betaling`, inspect the returned synthetic excerpt and preview its confirmed `Stuk 1` page reference, then insert the reference. The client repeats the search and rechecks the current selection and body text before an edit. A lost edit acknowledgment is marked unknown and blocks retries for the current session.

## Run locally

1. Create a local development certificate and key for `localhost` (including a `localhost` subject alternative name). Trust the certificate in the OS/browser used by Word. Never commit the key or use this certificate for production.
2. Install and build the client once, then start the synthetic server from the repository root:

   ```sh
   npm ci --prefix apps/word_addin
   npm --prefix apps/word_addin run build
   ```

   Run the server bound to loopback:

   ```sh
   uv run --locked uvicorn apps.word_addin.demo_app:app --host 127.0.0.1 --port 3000 --ssl-certfile /path/to/localhost-cert.pem --ssl-keyfile /path/to/localhost-key.pem --no-proxy-headers
   ```

3. Sideload `manifest.xml` using the Word host's development add-in workflow. Open a **synthetic** document, select a unique sentence, search `betaling`, and choose **Download original** or **Insert citation**. The download is checked against the returned SHA-256 digest before it is saved. The demo account and corpus are fixed, public fixtures. Run only in a local development environment.

## Boundaries and known limitations

- No Office host has been tested. The task pane's automated tests use a simulated Word API; record real host/version and save/reopen outcomes before making support claims.
- The localhost demo uses a public synthetic token, a simulated identity/store and fictional source representation. It is not Supabase authentication, a real PDF or a confidential matter. `mode: synthetic` is a development marker, not a security boundary. The demo rejects non-loopback clients; do not run it behind a reverse proxy or expose it on a network.
- The fixture downloads a synthetic plain-text original; its page reference is fictional. There is no embedded private source viewer, actual PDF source link, saved citation graph, authorisation for live Word editing, linked DOCX/PDF output, or Word-integrated M2 recheck. The default demo session activates only on localhost with `?demo=1`.
- Body text and current selection are compared before insertion. Word does not provide an atomic document-wide compare-and-swap here; changes between the final check and insertion, formatting-only edits, coauthoring, footnotes, tables, tracked changes and reopening have not been proven safe. Only unique body text is accepted. A disconnected/unknown operation cannot be safely retried without human reconciliation. Use Word's native Undo in the demo; programmatic undo is not implemented.
- `ReadWriteDocument` is required for the synthetic edit. Do not sideload this add-in into confidential or opponent-original documents. No production release is authorized by this spike.

See `docs/m3/WORD_INTEGRATION_ACCEPTANCE.md` for the full product acceptance contract.

## Development sign-in integration

The task pane also includes a Supabase OAuth/PKCE sign-in candidate adapted from Vaquill. It loads the pinned SDK through a locally built bundle and stores its session and PKCE verifier in an ephemeral in-memory storage instance. To exercise it on an independently configured development origin, that origin must serve the bundled client, same-origin search API and `caseproof-public-config.json` containing only `projectUrl` and `publishableKey` (an `sb_publishable_` key). Secret and service-role keys must never be supplied. The server and callback must use HTTPS; `auth-callback.html` must be in the Supabase redirect allowlist and the selected identity provider must be enabled. The current implementation supports standard `*.supabase.co` project domains and Google OAuth only.

The included manifest and `demo_app.py` run synthetic mode, not a live CaseProof backend. Live authentication and private-matter integration have not been exercised, no customer use is authorized, and live citation editing remains disabled. Real deployment also needs approved origin/manifest configuration, validated Office dialog behavior, session revocation tests and independent security review. Use separate development users and synthetic files.

## Signed development PDF/DOCX search in Microsoft Word — read-only integration

The **separate** [signed development manifest](manifest-live-dev.xml) requests
`ReadDocument`, not editing authority. It points at `https://localhost:3000/index.html`
(no `demo=1`). The loopback CaseProof development API serves the Word pane,
the pinned local SDK bundle, OAuth callback and the same-origin authenticated
`/dev/live/...` source search and original-download routes. These expose only
the public Supabase publishable key and **never** an admin key.

1. Run `npm ci --prefix apps/word_addin` and
   `npm --prefix apps/word_addin run build` to generate
   `apps/word_addin/dist/live-auth.js`. The bundle is **not** committed.
2. Obtain and trust a local development TLS certificate valid for `localhost`.
   Start `uv run --locked uvicorn apps.api.dev_live_entry:app --host
   127.0.0.1 --port 3000 --ssl-certfile <local-cert> --ssl-keyfile <local-key>
   --no-proxy-headers`. Provide `CASEPROOF_DEV_PUBLISHABLE_KEY` securely.
   Do not publish the server to the network or use production secrets. The
   protected service-only ingestion credential, if needed for local ingestion,
   must **never** be supplied through the Word task pane or browser config.
3. In the **development** Supabase project, independently enable an appropriate
   supported OAuth provider and add exactly
   `https://localhost:3000/auth-callback.html` to its redirect allowlist.
   Sideload `manifest-live-dev.xml` into a supported Word host. Enter the
   authorized matter UUID and current authored brief-version UUID, then
   complete Office dialog sign-in and select a unique sentence.
4. Search exact text from a signed ingested PDF/DOCX and inspect the physical
   PDF page/partial parser warning and SHA-256-verified original. No source
   is auto-identified as `Stuk` or `Pièce`. Live search returns
   `citation: null`; the Insert button remains disabled until later
   exhibit-confirmation and Word-host editing acceptance.

**Verification limit:** automated simulated Office and backend tests exercise
routing, data access, digest validation and fail-closed behavior. A real Word
host installation, OAuth dialog, document save/reopen, coauthoring and
cross-host compatibility have **not yet been verified**. This is not customer
processing or a filing/release workflow. Do not use confidential files.
