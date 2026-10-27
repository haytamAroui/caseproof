# M2-B packet 3 — Private-matter protected checking composition

**Status:** disposable integrated backend, NOT real signed-user/Supabase acceptance.
No route mounted on `apps/api/main.py`. No production SQL or service-key access.
Principal roadmap remains `docs/ROADMAP.md`.

## New integrated workflow

1. An existing `AuthorizedLitigationChecker` verifies a bearer through its
   configured issuer/audience verifier. `PostgresPrivateMatterCheckStore`
   reads **one joined server-owned DB membership + exact active matter grant**.
2. The active private case and exhibit register are read from M1 PostgreSQL.
   The register JSON must match the independent stored SHA-256. Only
   reviewer-confirmed exhibit pages contribute to the checking denominator.
3. The pinned current immutable brief version is loaded from the M2 versioned
   graph with its independently verified private original, case/exhibit
   revisions and exact typed reference/assertion records. A client cannot
   submit replacement brief/source contents or an X-Tenant-Id authority.
4. Each confirmed exhibit source identity resolves through verified
   document/version/intent custody. The trusted Vault reader rehashes the
   original bytes. For exact UTF-8 `text/plain`, an identity representation
   and source span are emitted. **PDF/DOCX remain explicit incomplete**
   (`parser_lineage_not_integrated`) until trusted parser/page semantics
   are plugged in; the checker must never treat raw binary bytes as a quote.
5. The M2 deterministic checker compares pinned brief claims to separately
   confirmed evidence. After checking, a *second bearer verification* and
   exact-grant/revision/source byte revalidation occurs. The optional M2
   durable publisher then revalidates grants and custody in its transaction
   and persists immutable check run snapshots. Human reviewer decision
   storage stays in PR #82; no approval or filing inference.
6. Cross-process/multiple-connection PostgreSQL regression reopens and
   verifies source identity, correctly segregates the **own brief from
   opposing evidence**, denies unknown/foreign/revoked matters, refuses
   corrupt Vault bytes, fails closed on an updated exhibit head, and
   proves one durable run despite repeated checking.

## Remaining gates / operational caution

- `SyntheticVerifier` in disposable tests is not a genuine signed Supabase
  session. A security-reviewed least-privilege runtime client, real Supabase
  JWT, M1 RLS migrations and private Storage reader are still required;
  current fixture Postgres is a localhost owner.
- The current adapter requires a currently available *verified* Vault
  intent for every confirmed exhibit. A future quality-control step needs
  to record missing/unavailable/partial sources **in the denominator**
  without leaking denied originals and without accidentally promoting
  an incomplete dossier. Failed custody currently denies the entire
  check, which is safe but not an optimal reviewer UX.
- Real PDF/DOCX/OCR authoritative normalized span lineage, versioned
  correction/apply/undo and transactional new source version/recheck
  remain M2-B OPEN. Only the text/plain fixture fast path is integrated.
- Missing/invalid privacy approval, external publication, automatic legal
  advice/claims, semantic truth, filing, and certification remain explicitly
  unsupported.

The new script `scripts.verify_m2_private_check_composition` runs against
disposable Postgres after the existing M1/M2/ Vault schemas and tests.
