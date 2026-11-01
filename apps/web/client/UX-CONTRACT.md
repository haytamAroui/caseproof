# Frontend interaction and ownership contract

Authority: root CONSTITUTION.md C01/C03/C05/C07/C14/C19; ADR 0011, ADR 0022 canonical reports, ADR 0025 sensitive metadata. Business behavior stays in Python services. The client is not an authorization authority. Locale en-BE for foundation acceptance; NL/FR product copy remains an M3 task.

| Capability | Canonical owner  | Source of truth                             | Allowed variants   | Verification                    |
| ---------- | ---------------- | ------------------------------------------- | ------------------ | ------------------------------- |
| Form       | app/OpenReport   | Native labels, noValidate and inline errors | Open frozen report | Playwright route/contract cases |
| Scrollbar  | app/theme.css    | DESIGN.md global visible baseline           | Geometry only      | Narrow browser test             |
| Toast      | shared/ui/Notice | Inline status and alert                     | Status/error       | axe and browser tests           |

A host session is an injected credential source, never proof of permissions. API enforces every access. Current composition does not implement a login flow. 401/403 clear private UI and query caches. Retried reads are explicit; no mutations are implemented. Future writes need stable operation IDs and explicit uncertain-outcome resolution, not optimistic approval.

Load → validate frozen report → select reference → display independent dimensions and coverage. Missing/invalid data produces an error, never default success. Zero references is not complete verification. Page viewer remains unconnected; no download is treated as human inspection. No persistent drafts, service worker or analytics. No claim of manual screen-reader or real signed-browser acceptance from fixture tests.
