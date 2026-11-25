# CaseProof — Owner & External Actions Checklist (25 November 2026)

**Repo baseline:** `main` `68c4c40e` (all 19/19 automatic CI checks green, 0 failures)  
**Purpose:** Everything engineering-owned in git/CI/local security tests is built and verified. The **5 items below require human/owner, provider, legal, or partner actions** outside an AI coding session and remain the only blockers to closing the open milestone/release gates.

---

## 1. Apply Optional Conditions-Retention SQL to `caseproof-dev` — DONE (VERIFIED 25 Nov 2026)
- **Status:** **DONE — VERIFIED ON `caseproof-dev` (`ldwmocpxwskvhoojndrd`) via read-only Supabase MCP on 25 Nov 2026.**
- **Receipt:** Applied directly via Supabase Dashboard SQL Editor (`public.caseproof_retention(text, uuid)` `pg_get_functiondef` SHA-256 `414f9c955ecfaa042f94c797f72a151896b2720c0a9bf2f6f088846e60bdde6f`, `has_conditions_delete=true`, `owner=postgres`, `SECURITY DEFINER`, `search_path=""`, `proacl={postgres=X/postgres,service_role=X/postgres}`, `0 ERROR` / `24 WARN` / `35 INFO` security advisors). Because applied via Dashboard SQL Editor, `supabase_migrations.schema_migrations` remains at `78` rows; recorded in [SIGNED_matter_conditions_retention.sql](../../db/proposals/SIGNED_matter_conditions_retention.sql) (still **NOT applied to production**).

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
