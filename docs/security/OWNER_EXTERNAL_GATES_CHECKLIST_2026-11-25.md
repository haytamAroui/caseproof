# CaseProof — Owner & External Actions Checklist (25 November 2026)

**Repo baseline:** `main` `68c4c40e` (all 19/19 automatic CI checks green, 0 failures)  
**Purpose:** Everything engineering-owned in git/CI/local security tests is built and verified. The **5 items below require human/owner, provider, legal, or partner actions** outside an AI coding session and remain the only blockers to closing the open milestone/release gates.

---

## 1. Apply Optional Conditions-Retention SQL to `caseproof-dev`
- **Why open:** In `ldwmocpxwskvhoojndrd`, `supabase_mcp:apply_migration` was automatically cancelled twice by the IDE client confirmation handler (`"The client cancelled this confirmation 0.1 s after it was sent. Nothing was run."`).
- **Action (you / operator):**
  1. Either re-enable confirmation prompts for `supabase_mcp:apply_migration` in your IDE client, **or** apply lines 7–88 of [SIGNED_matter_conditions_retention.sql](../../db/proposals/SIGNED_matter_conditions_retention.sql) via Supabase CLI / Dashboard so `supabase_migrations.schema_migrations` records the new version on `caseproof-dev`.
  2. Tell the agent once applied so it can read back the exact deployed SQL + SHA-256 and open the sync PR into `supabase/migrations/` (matching merged PR #237).

---

## 2. Security Operator Gate & Genuine Signed-User Live-RLS Acceptance ([Issue #214](https://github.com/haytamAroui/caseproof/issues/214))
- **Why open:** Requires real credential rotation, Supabase/GitHub operator environment configuration, and protected manual live-CI execution against `caseproof-dev`.
- **Action (you / operator):**
  1. Rotate development `service_role` key, Supabase Management PAT, and OpenAI key (confirming zero exposure in git/logs).
  2. Configure the `caseproof-dev` GitHub Environment with a required human reviewer and verify `main` branch ruleset reviewer requirements ([issue #5](https://github.com/haytamAroui/caseproof/issues/5)).
  3. Trigger the protected live workflows on `main` (`caseproof-dev-real-auth.yml`, `m1-m2-one-click-e2e.yml`) and record timestamps + negative revoked-key receipts.

---

## 3. `M5-01` / `M5-02` Belgian Litigation Partner Discovery (15-Min Demo + Interviews)
- **Why open:** Synthetic engineering accuracy cannot validate practitioner willingness to pay or real-dossier time savings.
- **Action (you / founder):**
  1. Start the local loopback demo: `python -m scripts.run_prefiling_partner_demo`
  2. Conduct **5 disconfirming interviews + 2 observed workflows** using the exact questions & scorecard in [PARTNER_DEMO_AND_INTERVIEW_SCORECARD.md](../m5/PARTNER_DEMO_AND_INTERVIEW_SCORECARD.md) (now including the *Farhat v. Cutera* `DOCX → PDF` handoff question).
  3. Lock target deployment topology (offline/local, firm-controlled, or hosted EU) before spending on production packaging or Level-2 AI (`BE-09`).

---

## 4. `SEC-01`..`SEC-16` External Legal, Privacy & Independent Security Sign-Off
- **Why open:** Engineering drafts and automated CI suites (`SEC-01` [THREAT_MODEL_2026-11-25.md](THREAT_MODEL_2026-11-25.md), `SEC-07` [test_sec07_log_sanitization.py](../../tests/test_sec07_log_sanitization.py), `SEC-11` [test_sec11_adversarial_file_security.py](../../tests/test_sec11_adversarial_file_security.py), `SEC-13` [INCIDENT_RESPONSE_RUNBOOK_2026-11-25.md](INCIDENT_RESPONSE_RUNBOOK_2026-11-25.md)) cannot replace external sign-off.
- **Action (external reviewers + pilot law firm):**
  - Complete Belgian bar professional-secrecy & GDPR DPIA/DPA review ([dpa-working-draft.md](../m5/dpa-working-draft.md), `SEC-10`).
  - Finalize signed subprocessor register (`SEC-09`), independent `SECURITY DEFINER` RPC review (`SEC-04`), independent pentest (`SEC-12`), and actual provider restore drill (`SEC-14`).

---

## 5. `OPS-01` EUIPO / BOIP Trademark Clearance
- **Why open:** The provisional name **CaseProof** has a US *Caseproof LLC* overlap noted in [ROADMAP.md](../ROADMAP.md).
- **Action (IP counsel):** Run formal EUIPO (Benelux/EU) & BOIP clearance before public brand launch or commercial contracts.
