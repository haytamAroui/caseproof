# M1 live positive Storage acceptance (development only)

Live dev fixture migration **`20261027214851_caseproof_m1_dev_live_positive_fixture_rpc` is installed and its three functions were verified as service-role-only via Supabase MCP**. This adds a small **service-role-only SQL fixture issuer**, an added step in the existing protected manual GitHub workflow, and genuine verified signed-user Storage acceptance. It does not add permanent remote DB DSNs or access tokens.

## Trust and execution

- Project pinned to `ldwmocpxwskvhoojndrd`, `caseproof-dev`.
- Already configured GitHub protected `CASEPROOF_DEV_PUBLISHABLE_KEY` and `CASEPROOF_DEV_AUTH_ADMIN_KEY` are used. No third secret.
- The new `public.caseproof_dev_fixture_begin/revoke/cleanup` RPCs can only be executed with the existing service-role key (no `anon`/`authenticated` privileges). SQL requires three confirmed `caseproof-ci-*@example.com` Auth accounts, exactly one empty fixture namespace, approved M1 Storage migration and private bucket. The RPCs have no arbitrary SQL inputs or customer-file privileges and are **dev-only**.
- Each user-facing PostgREST source lookup and every upload/read/revocation attempt uses the user's **actual JWT**, not the service key.

## Protected steps

1. Create three confirmed temporary Supabase Auth users with `GoTrueDevAdmin`, independently sign in and resolve JWT identity.
2. Issue two synthetic organizations, two memberships in org A, one in org B; create one matter + document + version + SHA with only user A granted `evidence:read`+`evidence:upload`.
3. A fetches version via the live `security_invoker` view; uploads to `caseproof-originals-dev` using signed Storage transport; reads back with exact SHA/length validation.
4. User B, a **member of org A but ungranted for the case**, and user C, member of org B, must each fail actual GET of the **existing** object through raw Storage and the signed source library.
5. Revoke A's exact grant via service-role-only RPC; A must fail actual GET of the existing object.
6. Delete the original through Supabase **Storage API**; then exact SQL fixture rows; then Auth accounts in existing `finally` handler. Outputs separate stage receipts without secrets, users or paths.

Run workflow manually on `main`: [CaseProof LIVE M1 authorized original](https://github.com/haytamAroui/caseproof/actions/workflows/m1-m2-one-click-e2e.yml).

## What it does NOT prove

- It **does not** execute genuine live M2 checking, reviewing, correction or recheck. The existing one-click workflow tests those components in *disposable* PostgreSQL only.
- Word end-to-end and customer release are separate.
- A passing PR check alone is not signed-user acceptance; only a green **protected workflow_dispatch** executing actual remote calls counts.

The dev-only migration is already installed via MCP and committed under its canonical generated version. Independent security review remains required before customer release. The authorized positive test remains unrun pending the merge and manual protected workflow trigger.