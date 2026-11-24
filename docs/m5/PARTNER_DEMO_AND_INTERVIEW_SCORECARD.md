# M5 — Belgian Litigation Partner Discovery, 15-Minute Demo Script & Commercial Scorecard

**Date:** 24 November 2026  
**Authority:** [Product Strategy (24 Nov 2026)](../PRODUCT_STRATEGY_2026-11-24.md) · [ADR 0038](../adr/0038-pre-filing-truth-layer-and-competitive-strategy.md) · [ROADMAP M5 & P5-01..04](../ROADMAP.md#m5--five-week-practitioner-experiment-and-conditional-commercial-pilot) · [SEC-01–16 Pilot Security Gate](../security/PILOT_DATA_SECURITY_GATE.md).

**Purpose:** Answer the commercial question *before* building more UI screens: **is pre-filing verification of Belgian conclusions painful enough that a litigation firm will pay for it, and who signs the check?**

> **Non-negotiable rules for every call:**
> 1. **Synthetic / rights-cleared dossiers only.** Never ask a lawyer to upload real client files during discovery or demos; real client dossiers remain blocked until [SEC-01–16](../security/PILOT_DATA_SECURITY_GATE.md) is approved for the target environment.
> 2. **No hype or false legal claims.** Never claim "100% accurate", "AI Act certified", "only tool on the market", or call any manifest/HMAC receipt a qualified electronic signature (eIDAS QES) or *constat d'huissier*.
> 3. **Interview first, demo second.** Spend the first 10 minutes collecting disconfirming evidence before showing a single screen.

---

## Part 1 — 10-Minute Disconfirming Discovery Interview (Before Showing Screens)

Run with **5 Belgian FR/NL litigators** (separating **user** [associate/counsel], **economic buyer** [litigation/managing partner], and **blocker** [IT/KM/risk]). Record exact numbers and objections—not polite compliments.

| # | Core Question (EN) | FR / NL Prompt | What We Are Testing |
| --- | --- | --- | --- |
| 1 | **Last real mistake:** When was the last time a wrong `Pièce/Stuk` page, misquoted excerpt, or omitted statutory reservation slipped into *conclusions* (yours or an opponent's)? What was the consequence? | *FR:* « Quand une erreur de page, de citation ou de réserve omise s'est-elle glissée pour la dernière fois dans des conclusions ? »<br>*NL:* « Wanneer is er voor het laatst een verkeerd paginanummer, citaat of weggelaten voorbehoud in conclusies geslopen? » | Real incident frequency & emotional/reputational cost (not hypothetical fear). |
| 2 | **Current checking workflow & time:** On a typical 50–200 page dossier, who checks references before filing and how many minutes/hours does it take? | *FR:* « Qui relit les renvois aux pièces avant dépôt, et combien de temps cela prend-il sur un dossier de 50 à 200 pages ? »<br>*NL:* « Wie controleert de stukverwijzingen vóór neerlegging en hoeveel tijd kost dat bij een bundel van 50–200 pagina's? » | Actual dossier size (P5-03) and measurable baseline minutes. |
| 3 | **AI drafting & trust:** Does the team use Alice, Nexa, Harvey, Copilot, or ChatGPT to draft *conclusions*? How do partners verify AI-assisted drafts today? | *FR:* « Utilisez-vous Alice, Nexa, Copilot ou Harvey pour rédiger ? Comment l'associé vérifie-t-il les citations générées ? »<br>*NL:* « Gebruikt het kantoor Alice, Nexa, Copilot of Harvey? Hoe controleert de vennoot de gegenereerde verwijzingen? » | Whether AI-drafted briefs amplify the need for an independent Step 3 audit layer. |
| 4 | **Current stack:** Which tools do you use to draft and assemble exhibits (Word, CourtMerge, PiecesPerfect/Praxis, Doxflow, Acrobat)? | *FR:* « Quels outils utilisez-vous pour assembler la farde de pièces (CourtMerge, PiecesPerfect, Acrobat…) ? »<br>*NL:* « Welke tools gebruiken jullie voor de stukkenbundel (CourtMerge, PiecesPerfect, Doxflow, Acrobat…)? » | Exact bundle-renumbering friction and handoff format. |
| 5 | **Confidentiality dealbreakers:** Would you accept EU cloud hosting, firm-controlled deployment, or strictly offline/local execution? What would make your IT/risk lead say no? | *FR:* « Quel déploiement est acceptable (cloud UE, serveur cabinet, 100 % hors ligne) ? Qu'est-ce qui bloquerait ? »<br>*NL:* « Welke hosting is aanvaardbaar (EU-cloud, eigen server, volledig offline)? Wat zou een dealbreaker zijn? » | Hosting topology required before investing in packaging. |
| 6 | **Buyer & budget:** If a tool cut pre-filing check time and caught 2–3 critical reference traps per major brief, **who owns the budget** and what price model fits (per seat/month vs. per dossier)? | *FR:* « Si l'outil faisait gagner 1 h par dépôt critique, qui valide le budget et à quel ordre de prix ? »<br>*NL:* « Wie beslist over het budget voor zo'n controletool en welk prijsmodel past bij het kantoor? » | Willingness to pay and real purchasing authority. |
| 7 | **Disconfirming killer question:** Even if this worked cleanly, why might your lawyers still *not* use it on a Friday afternoon before a filing deadline? | *FR:* « Même si l'outil fonctionne bien, qu'est-ce qui ferait que vos avocats ne l'utiliseraient pas la veille d'un dépôt ? »<br>*NL:* « Zelfs als dit goed werkt, waarom zouden uw advocaten het de dag vóór een conclusietermijn toch niet gebruiken? » | Friction, workflow switching cost, or "good enough manually". |

---

## Part 2 — 15-Minute Live Synthetic Demo Script

**Setup:** Run the official React cockpit (`frontend/`) on a **synthetic FR/NL dossier** (no client files). Keep the 3-pane split screen visible throughout.

| Time | Demo Moment | Exact Action on Screen | What to Say Honestly (Trust Calibration) |
| --- | --- | --- | --- |
| **0:00–2:00** | **1. Frictionless Intake & Immediate Audit** | Upload synthetic conclusions `.docx`, bordereau, stamped PDF bundle, and select a pinned offline legal pack (showing SHA-256 + version). Audit runs immediately without a blocking confirmation wall. | *"You don't leave Word, and we don't force setup before showing value. Anything tied to an unconfirmed mapping stays explicitly `NOT_ASSESSED` until you confirm it inline."* |
| **2:00–5:00** | **2. Wrong Page in a 3-Space Bundle** | Click the top crimson `✕ Écart constaté` item. Right-hand `SourceViewer` snaps immediately to the live PDF page showing `PDF page ≠ Printed page ≠ Bundle page`. | *"CourtMerge or PiecesPerfect merges your bundle and renumbers pages. CaseProof tracks all three page spaces separately and puts the actual PDF pixels beside your sentence."* |
| **5:00–8:00** | **3. Omitted Reservation & Refused Historical Law** | Click the statutory quote finding (`✕ Écart constaté`: dropped opening qualifier *« Hormis les cas où la loi en dispose autrement »*). Then click the historical-version finding (`⊘ Contrôle impossible — requested_version_absent_from_chosen_corpus`). | *"Zero LLM decides these verdicts. If your chosen offline legal pack does not contain the 2019 historical text you cited, CaseProof refuses to fake a match with today's law."* |
| **8:00–10:30** | **4. Honest Flags (`! Appréciation requise`)** | Click the targeted lexical flag (`"signé le 12 mars"` vs source `"envoyé pour signature le 12 mars"`), an `FR ↔ NL` quote (`TRANSLATION_REVIEW_REQUIRED`), and a Lawyer-Defined Condition (*preuve de réception de la mise en demeure*). Record a human decision (`Qualify` / `Confirm`). | *"CaseProof does not pretend to verify legal meaning or translations automatically. It flags these passages for your appraisal beside the source—you decide, and both the machine finding and your decision stay recorded."* |
| **10:30–13:00** | **5. Word Round-Trip Recheck** | Show fixing the wrong page in Word → re-upload the revised `.docx`. Point to untouched decisions (`carried`) vs. modified claims reopened (`À recontrôler`). | *"You stay in Word. When you re-upload version 2, you don't redo the whole review—unchanged checks carry forward, and anything touched by your edit automatically reopens."* |
| **13:00–15:00** | **6. Coverage, Failure Honesty & Export** | Show the explicit Coverage bar (scanned vs. unsupported DOCX regions, `omission` button) and download the immutable verification trace. | *"Notice there is no fake green 'Verified' badge. You get a cold-reopenable diligence trace—server-signed HMAC receipt on hosted/server releases or SHA-256 digest offline—proving integrity, never replacing your legal signature or court filing."* |

---

## Part 3 — The Commercial Ask (End of Meeting)

Never leave a call with *"Looks cool, keep me posted."* Close with one concrete, priced commitment test:

> *"We are selecting 2–3 Belgian litigation teams for a bounded design-partner evaluation on 3–5 dossiers (FR/NL) once security/confidentiality sign-off is complete. We benchmark three numbers against your manual check: **total review time, critical errors caught/missed, and false-alarm friction**. If it saves real partner/associate time and catches errors your current process misses, would you commit in writing to a paid pilot at **€[anchor price, e.g. €250–€500/month or €150/dossier]**—and who else needs to be in the room to approve that?"*

Record the **exact reaction** verbatim (including refusal, counter-price, or missing buyer authority).

---

## Part 4 — M5 Interview & Decision Scorecard (Feeds P5-01)

Log every conversation in a private tracker (never commit client names or personal data to public Git):

| Dimension | Score 0 (Disconfirming) | Score 1 (Weak / Ambiguous) | Score 2 (Strong Signal) |
| --- | --- | --- | --- |
| **Pain Recurrence** | "Rarely happens / never mattered in court" | Happens occasionally; annoying but minor | Recurring pre-filing stress on multi-exhibit FR/NL dossiers |
| **Baseline Effort** | < 15 min manual check | 15–45 min check | > 60 min associate + partner re-check per major brief |
| **AI-Draft Verification Pull** | No AI use and no plans | Experimenting privately | Active AI drafting (Alice/Nexa/Copilot/Harvey) with partner review anxiety |
| **Workflow Fit** | Demands full drafting / bundling / e-Deposit | Wants Word add-in mandatory on day 1 | Accepts web cockpit + native Word `.docx` round-trip |
| **Deployment Feasibility** | Demands impossible/unfunded certification upfront | Needs standard EU cloud + DPA | Clear, achievable path (EU cloud or firm-controlled/offline) |
| **Payment Signal** | "Only if free" / no budget | Verbal interest only | Concrete budget owner identified + willingness to sign priced conditional pilot |

### Exit Decision Rule ([P5-01](../ROADMAP.md#p5-01--exact-meaning-of-proceed--refine--reconsider))
After **5 disconfirming interviews + 2 observed workflows** (within 5 weeks of interview #1):
- **PROCEED:** ≥ 3 strong pain/effort scores + clear buyer + at least **1 written priced paid/conditional pilot commitment** → prepare bounded paid beta packet (still gated on SEC-01–16 before any real client data).
- **REFINE:** Real pain exists, but pricing, deployment mode (e.g., strictly local-only), or workflow friction (e.g., Word add-in) blocks buying → record exact minimal repair and re-test.
- **RECONSIDER:** Pain is rare, manual/existing tools are "good enough", or nobody will pay → halt further UI spend on this niche and escalate to owner decision (preserving the neutral kernel).
