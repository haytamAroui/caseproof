# ClearBrief lawyer workbench — integrated development slice

This is a **new browser application**, distinct from the old ExceptionDesk invoice review demo. It is mounted only by the loopback development composition, not `apps/api/main.py`. It provides an actual interactive professional workflow over the existing signed M1/M2 application ports; it is **not** a customer release or proof of a live Supabase reviewer graph.

## Use

Start the existing injected `create_litigation_development_app(...)` composition with:

- `checker`: `AuthorizedLitigationChecker`, backed by trusted current matter grants, source-version graph and typed deterministic checking.
- `evidence`: existing authenticated evidence library reader for inventory and source previews.
- `originals`: existing `AuthorizedOriginalReader` for verified version-bound bytes, or `signed_originals`: `SignedSourceLibrary` for previously registered signed Storage original upload and SHA-verified readback.
- `reviews`: `SignedReviewWorkspace(checker, ledger)`, only when **the checker's publisher is the same durable ledger** and all grants are enforced. Without a ledger/review port, review requests return 503, not a success.
- Optional `publishable_key="sb_publishable_..."` for direct user Supabase development password sign-in. Other keys (including `sb_secret_*`) are rejected. A trusted host can alternatively inject `window.caseproofSession` with `getBearer()`, `caseId`, `briefVersionId`, as the Word spike does.

Open `http://127.0.0.1:<port>/dev/clearbrief` from the **same host**. No service key, tenant header or client-assumed role. The UI does not create matters or authorize grants: an authorized existing matter/brief version is required. Signed session access tokens are memory-only; no localStorage, sessionStorage or persistent cookies.

## Completed interactive behavior

1. Signed existing matter open, fail closed for invalid/expired session.
2. Versioned source inventory with incomplete/error states, authorized representation preview and verified original download.
3. Signed lexical search with exact source/citation mapping and reported coverage.
4. Single scoped M2 deterministic check displaying **citations + factual candidate observations**, declared partial scope and clean-zero warning behavior.
5. A visible reviewer panel; typed human disposition + rationale, same actor/snapshot authorization, idempotent request UUID and optimistic revision; reopen saved review history.
6. Rerun/recheck action asks the server to recompute the current checked snapshot. Different/stale checks do not silently reuse a prior review.
7. Pre-registered document-version upload to the private bucket via signed user JWT. No overwrite, digest and object ownership verified by the existing Storage service.
8. Visible disabled Word insertion and customer release until real host and M4 artifacts are accepted.

## Important limits

- No browser-facing matter-creation flow yet. Never use the dev-only **service-role CI fixture RPC** as a customer matter-creation API.
- No real PDF/DOCX viewer or correction application yet; the representation pane displays parsed text with warnings. Existing OCR/page completeness remains separate.
- This PR does not install or migrate live review records; the signed review port can be bound to the existing disposable ledger for integrated tests. A live Supabase reviewer use case needs separately accepted real persistence, secure reviewer authorization and reopened history.
- No automatic Word edit, generated output, legal opinion, approved citation or filing. The green browser/API tests validate the **development product slice**, not the full M1–M4 release path.

## Next implementation

Move the signed product workflow onto the reviewed live M2 application/ledger, add user-authorized matter creation and exhibit confirmation, complete correction preview/apply/recheck, and test actual Word host insert/save/reopen with the same signed source API. Add a full PDF/DOCX/scanned-source journey without promoting unavailable OCR to verified evidence.
