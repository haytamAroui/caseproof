# CaseProof — external pilot acceptance handoff (T61, T70, T72–T79)

**State: NOT PILOT APPROVED.** Created 5 November 2026 on the signed
engineering baseline [PR #198](https://github.com/haytamAroui/caseproof/pull/198).
This is the prioritized handoff for outside reviewers. It does not contain
a fictitious security sign-off, a Microsoft Word host run, a real client
authorization or a lawyer's result.

Use [the structured gate register](PILOT_EXTERNAL_GATE_REGISTER.json)
for status only; its validator cannot verify signers, legal rights, real
deployment behavior or operator authority. Keep actual sensitive evidence
in approved, access-controlled storage, never in GitHub/Actions.

## Stage 1 — independent security, privacy and recoverability

**T70 (first):** Provide [read-only live dev catalog observation](../security/T70_READONLY_LIVE_CATALOG_AUDIT_2026-11-05.md)
to an independent application/database security reviewer. Inspect the 19
authenticated-callable privileged functions, seven RLS-protected read tables,
33 no-policy private tables, auth leaked-password warning, cross-matter
revocation, stale grants, storage shares and signed source/release retrieval.
Capture defects, severities, remediation, independent rerun and decision.
Do not automatically change SECURITY DEFINER functions or RLS in production.

**T73 (first):** Have the actual deployment controller/privacy officer select
hosted, hybrid, firm-controlled or offline. Pin build+configuration hashes,
operator, region(s), subprocessors, contractual terms/DPA, processing lawfulness,
client privilege/professional-secrecy, legal hold, access roles, telemetry,
backups, OCR/worker and support egress. Re-run a whole-perimeter scoped
network/retention assessment for that configuration.
Read-only Supabase MCP confirmed the **development project's** reported
region \`eu-central-1\`, one non-public original Storage bucket, and
signed/matter-scoped Storage RLS. It did not establish provider-wide
data residency, subprocessors, traffic destinations, backup schedules,
secure deletion, or the law firm's processor agreements. This is
**partial T73 evidence only**.
 A project region alone
does not establish where all services, backups or support data reside. Use
[SEC-01–16](../security/PILOT_DATA_SECURITY_GATE.md) and
[deployment assessment runbook](../security/DEPLOYMENT_EVIDENCE_RUNBOOK.md).
In signed dev, **originals do travel to Supabase private Storage**. Do not
claim local-only/zero egress.

**T74 (first):** **Do not confuse database backup recovery with
original-file recovery.** Supabase's
[backup documentation](https://supabase.com/docs/guides/platform/backups)
states that database backups contain Storage object metadata, **not
the uploaded object bytes**. The operational exercise must prove
independent recovery of the original Storage objects and the database
metadata, SHA-256 parity, historical read authorization, and deletion
replay across both. The connected Supabase MCP does not expose a
non-destructive database+Storage clone/restore operation and no backup
schedule, backup-region or authorized isolated restore has been verified.
Do not use `restore_project` on the running development project to
satisfy this test.

**T74 (first):** The disposable PostgreSQL 17 restore and erasure replay
already passed, but do an **authorized operational restore test** for the
selected Supabase backup and Storage snapshot into an isolated/quarantined
target. Record RPO/RTO, version/region, snapshot identity, backup retention,
original SHA-256 readback, OCR/crop/snapshot/review/release authorizations,
legal holds, and **re-deletion of pre-backup erased content before access**.
Re-run revoked-user and cross-matter read tests after restore. Never test
destructive restore by modifying the existing live \`caseproof-dev\` data.
Operations/privacy owners must review both successful recovery and failures.

**T72 (alongside):** Inspect exact production and developer dependency
advisories, pinned lockfiles, SBOM, provenance, update and incident cadence.
A supply-chain CI pass does not authorize known advisories.

### Live Supabase Free-tier recovery constraint (MCP observation, 5 November 2026)

The connected Supabase MCP returned organization plan \`free\` for the
organization currently hosting \`caseproof-dev\`. According to the
[official database-backups guide](https://supabase.com/docs/guides/platform/backups),
Supabase's **managed daily backups are provided on paid plans**, while
Free-tier operators must arrange and maintain their own backup copies.
The project was not upgraded; managed daily backup/PITR availability and
retention **have not been established**. The available MCP tools do not
offer an approved isolated database+Storage clone/restore workflow.

**Crucially, even managed database backups back up Storage metadata but NOT
object bytes.** The lawful operator must choose and test **both**:
(1) encrypted, version-pinned PostgreSQL backup/restore with documented RPO,
RTO, access roles, re-erasure and legal hold; and (2) independently
authorized, encrypted backup/recovery of private Storage originals and
derivatives, with SHA-256 parity and post-restore signed-user isolation.
A database-only dump is inadequate for CaseProof's source provenance.

Two possible operator decisions (neither taken here): a paid provider
backup/isolated clone **plus separate Storage-object recovery**, or
operator-maintained encrypted database dumps **plus separate Storage-object
backups**. Any plan upgrade or new resources may have costs and require an
explicit owner decision before provisioning. Supabase CLI v3, announced
4 November 2026, runs database operations locally by default;
hosted CLI runbooks must verify \`--remote\` behavior before use
([release note](https://supabase.com/changelog?types=breaking-change)).
No production data, private object or backup bytes were accessed in this
audit.

**T74 disposition: BLOCKED — no approved operational end-to-end restore.**

## Stage 2 — actual document hosts and manual accessibility

**T61 (after engineering gates):** Test with real **Microsoft Word desktop**
(on recorded OS, Office version and settings) and LibreOffice Writer.
Use rights-cleared DOCX originals, corrected derivatives and annotated exports.
Check paragraph styles/runs, numbered legal headings, tables, nested elements,
footnotes/endnotes, comments, tracked revisions, fields, links, images, page
breaks, print layout and saving/reopening. Compare original and derivative
hashes and expected changes. Record screenshots and defects in private
storage. The existing LibreOffice CI smoke is not a Word desktop test.
Reviewer and practitioner must approve the defined support matrix or record
unsupported constructs.

**T75 (after final frontend design):** Run keyboard-only and human AT checks:
NVDA/JAWS on Windows plus VoiceOver where the supported matrix calls for it;
browser/OS/screen-reader versions; Dutch/French/English text; 320px and real
200% zoom; forced colors/reduced motion; accessible authentication; modal
focus/restore; error announcements; upload, pages/crops, finding decisions,
correction, release and history. Log WCAG 2.2 A/AA criteria, findings,
severities, retests and independent accessibility reviewer decision.
Automated axe and Playwright are prerequisite evidence, not human sign-off.
References: [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) and
[UK government manual AT testing](https://www.gov.uk/service-manual/helping-people-to-use-your-service/testing-for-accessibility).

## Stage 3 — permitted corpus and two-lawyer study

**T76:** Collect **3–5 representative** NL/FR (and supported EN/manual
cases) rights-cleared DOCX/inventory/text PDF/scanned PDF dossiers.
Obtain written rights-holder authorization, controller processing permission,
approved processors/regions, data class, access policy, legal hold and
deletion schedule **before any client bytes enter CaseProof**. Hash and
inventory sources only inside approved private custody. Independently label
reference identity, physical/printed/bundle pages, fidelity, OCR abstentions
and seeded/source-known errors. Keep disagreements and third adjudication
explicit. Use [existing corpus protocol](P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md).

**T78:** Two different practicing reviewers (codes only in metrics) review
counterbalanced manual versus CaseProof conditions on the same adjudicated
corpus **without seeing each other's results**. Each reviewer uses both
conditions, but not both conditions on the same dossier. Capture actual
seconds, independently measured gold denominators, errors found,
false-verification outcomes, page/source mistakes, abstentions and usability.
\`application.pilot_study.assess_study\` checks metadata and yields aggregate
metrics, **not validated legal accuracy**. A zero-error denominator gives
\`null\` recall, not 100%. Stop on wrong-source verified claims,
unauthorized access, irreversible correction or unknown permission.

**T79:** Only a named law firm, security/privacy owner, operations owner,
accessibility/document reviewer and pilot sponsor can make the scoped,
dated final decision. Record approval for **specific environment, capacity,
client data class, legal purposes, permitted dates and rollback conditions**.
Engineering merge and synthetic CI remain separate.

## Capacity dependency D01 / T20–T29

The merged [development policy](../adr/0035-pilot-capacity-envelope.md) is
not a 150–200-page accepted product envelope. See
[capacity expansion decision matrix](CAPACITY_EXPANSION_DECISION.md).
Do not enroll client dossiers larger than the independently measured/approved
profile; use synthetic data to benchmark candidate configurations before
any extension.

## Evidence package format

For each external gate, use a private immutable receipt covering:
\`gate_id\`, exact \`build_sha\`, \`configuration_sha256\`,
\`environment\`, \`data_class\`, \`evidence_uri\`, reviewer,
reviewer independence, date, findings/severity, unresolved conditions,
stop/rollback action, expiry/validity and signed reviewer decision.
The public register contains only non-sensitive references and digest values.
An unverified reviewer string is not authentication. No client secrets,
files, personal names or sensitive case metadata in CI.

Current decision: **BLOCKED for real client material and pilot release.**
