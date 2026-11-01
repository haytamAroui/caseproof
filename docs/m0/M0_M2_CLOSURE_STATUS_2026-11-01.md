# M0–M2 closure ledger — 1 November 2026

## Closed engineering and development evidence

- Scope/rights-declared synthetic baseline, real DOCX/text-PDF/image-PDF fixture generation and blinded review packet are implemented.
- PR #159 merged as `05576ba`. All 17 workflows passed on tested code `9c587f4`.
- [Protected genuine-user acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41258188700) passed original-byte readback, four-source check/review/correction/recheck, actual artifact reopening, cold restart, fresh login, revoked denial and zero-residual cleanup.
- Development migrations `20261031234906`, `20261031235117`, `20261101004423` are installed. [Recovery](https://github.com/haytamAroui/caseproof/actions/runs/41258188830) removed the three earlier failed fixtures; catalog inspection found zero remaining fixture/ledger rows for them.
- The next increment discloses English Exhibit references as unsupported findings. They never alias to Pièce numbers or become verified inventory absences/page locations. Supported-reference verification and unsupported detection are measured separately.

## Still requires actual external evidence

| Gate | Needed evidence | Current state |
|---|---|---|
| M0 independent gold | Two distinct competent human assessments per case, verified credentials/evidence and adjudicated disagreements | Supplied review archive has blank forms; no returned assessments |
| M0 owner acceptance | Dated owner decision bound to exact reviewed corpus hash and exclusions | Not recorded |
| M1 confidentiality/security | Independent tenant/security review and approved customer operator/region/egress/retention/backup/privacy/professional-secrecy controls | Development success only; no confidential-client permission |
| M2 representative accuracy | Rights-cleared representative dossiers, reviewed gold, detection/mapping/fidelity/OCR/value/date/translation denominators and measured uncertainty | Tiny author-labelled synthetic baseline only |
| M2 coverage and scope | Measured DOCX-region handling and support boundaries, with omitted/unsupported portions disclosed | Partial coverage retained; correction supports a bounded single-run paragraph range |
| Formal M1/M2 signoff | Named acceptance owners and approved evidence records | Not recorded; #159 was owner-directed merge without independent approval |

## Commands

```bash
uv run --locked python -m scripts.m0_blind_review --out /tmp/caseproof-blind
uv run --locked python -m scripts.validate_m0_independent_reviews \
  --packet /tmp/caseproof-blind/blind_cases.json \
  --submission reviewer-a.json --submission reviewer-b.json
uv run --locked python -m scripts.evaluate_litigation_detection --output /tmp/caseproof-detection.json
```

The review checker intentionally exits nonzero for empty/incomplete/disagreeing
submissions. Passing it means ready for external credential/evidence verification,
not that independent review or M0 acceptance happened. Do not fill blank forms on
behalf of a real reviewer or replace their judgments with author-gold labels.

The synthetic measurement contains 19 labelled occurrences across 18 cases: 13
supported Stuk/Pièce occurrences and six unsupported English Exhibit occurrences.
Flagging the six unsupported references does not make them technically verified,
measure semantic accuracy, or establish population recall. Independent evaluation
must include real supported workloads and clean controls before pilot claims.
