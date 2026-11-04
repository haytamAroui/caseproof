# P6 dependency, dev RPC and privacy triage — 4 November 2026

**Status:** engineering inspection only. No independent security sign-off, confidentiality approval, GDPR certification, or operational deployment authorization.

## Dependency analysis on PR #185 head 33a38a4

[CI supply-chain audit](https://github.com/haytamAroui/caseproof/actions/runs/41826363626) ran installed npm's security-advisory registry audit twice against the same lockfile. Output is summarized without raw documents or credentials.

- **Production graph:** 0 low/moderate/high/critical known npm registry advisories in npm audit --omit=dev. This is neither a pentest nor comprehensive transitive-supply-chain certification.
- **All dependencies:** 11 moderate; 0 high; 0 critical. All affected names appear in **development tooling**, including eslint, @eslint/js, typescript-eslint/@typescript-eslint/*, @eslint/config-array, @eslint-community/eslint-utils and minimatch. Reported remediation is a version change; not applied without lockfile-compatible verification.
- **Residual risk:** future CI and developer tooling executes vulnerable packages. An owner must inspect the actual advisory, exploitability on CI inputs, and a pinned supported patch; require patched lockfile and rerun before broadening claims. No blanket risk waiver is issued. A workflow enforces zero moderate-or-worse production findings and zero high/critical across all dependencies.

## Actual read-only CaseProof dev database catalog

Connected Supabase development project ldwmocpxwskvhoojndrd, selected pg_proc, pg_class, pg_policy and security adviser via read-only access. No DDL or grants were changed.

- 15 security adviser WARNs for authenticated-executable SECURITY DEFINER functions in public; the catalog confirms those functions are postgres-owned and have empty explicit search_path; anon EXECUTE was false for observed CaseProof RPCs. Each must be reviewed for dynamic SQL, actor validation, tenant access and permission escalation. Executability is an attack surface, not proof of exploit.
- 29 INFO private RLS-enabled table-without-policy notices. Selected audit_events/dossier_snapshots/dossier_releases/erasure_receipts had RLS true and no direct SELECT or INSERT grants to authenticated or anon. Absence of policy on a private table is not itself an RLS bypass. Documents and versions have direct SELECT and need their existing row policies tested under real signed identities.
- Adviser warned of disabled leaked-password protection. The auth owner must confirm availability/policy and enable or record approved rationale.
- Two wrappers lacking *direct* auth.uid() calls were examined: caseproof_dev_bundle_manifest delegates to caseproof_dev_bundle_manifest_original, which validates auth.uid(), authenticated JWT role, active organization membership and exact matter grants. caseproof_dossier_snapshot_read delegates to caseproof_dossier's decisions action before accessing a matching case/snapshot. These delegation checks were observed in function definitions; they still need independent adversarial review and runtime signed tests.
- caseproof_signed_ocr_geometry is SECURITY INVOKER and relies on private source privileges/RLS; scope and exposure require signed testing.

## Privacy/processing boundary

[Actual current development flow](../security/PILOT_DATA_FLOW.md): local FastAPI/browser sends originals to private Supabase services; worker-only isolated OCR is not whole-application offline processing. A visible intake notice now repeats the critical disclosure before users preserve documents. No deployment-specific geography, legal hold duration, provider agreement or operator consent has been invented. [ADR 0025](../adr/0025-deployment-data-retention-and-model-authority.md) and [pilot gate](../security/PILOT_DATA_SECURITY_GATE.md) remain binding.

**Closure:** independent security owner, signed cross-matter/roles test receipt, app-specific advisory patch or accepted exception, deployed egress/retention/region and data-processing review. **No production or confidential-matter permission granted.**
