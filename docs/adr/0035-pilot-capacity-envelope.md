# ADR 0035 — Versioned development envelope and measurement before pilot expansion

**Status:** proposed engineering implementation, 5 November 2026.
**Decision:** retain the already-enforced narrow four-source development
envelope; centralize existing caps and generate frontend policy from Python.
Do not silently upgrade to 150/200 pages, 100 OCR pages or 50 MB per source.

The current signed journey supports only the bounded registered development
contract. An earlier 150-page *discovery* measurement and 200-page *text-only*
page-worker benchmark cannot together prove a 150-page end-to-end envelope.

**Policy authority:** \`application/capacity_envelope.py\`. The generated
\`frontend/src/shared/api/capacity-policy.json\` is derived, not edited by hand;
\`scripts.generate_frontend_contract --check\` detects drift. Back-end intake
validates all originals before registration or immutable write, including
role/type/sha/size and parser restrictions. The frontend pre-checks the same
byte/count limits but cannot authorize any write.

**Export:** enforce explicit JSON/Markdown limits before attempting DOCX
generation; fail closed on over-size DOCX or reopen error before saving a
signed release. Preserve existing historical byte/HMAC/authorization checks.

**Processing:** existing page-worker leases, recovery and cancellation remain
single authority; no competing worker state machine is introduced. Tests
must prove denied/stale/cancelled paths, not just a successful subprocess.

**Measurement:** reproducible synthetic, text/scan mixed NL/FR local OCR,
real signed F3–F6 journey timings and separate worker metrics. Each log
records scope, environment, version, timing and bounded peak RSS but no
exhibit content or credentials. Re-measure candidate larger envelopes before
approving a new profile; policy changes require signed negative and recovery
acceptance plus a dated product/security decision.

**Unresolved:** Full-envelope scan throughput, cumulative memory, browser
navigation at load, visual scheduling policy, optional OCR-unavailability
budget, operational recovery targets and representative lawyer acceptance.
T20–T29 are NOT closed by this narrow engineering baseline.
