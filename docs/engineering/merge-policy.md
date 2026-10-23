# Pull request merge policy — solo maintainer

Status: Adopted working policy (23 October 2026). This document records the intended repository workflow; **GitHub branch protection and rulesets are configured in GitHub Settings, not by this file**.

## Required before merge

1. Target `main`; the PR head is current and the merge has no conflicts.
2. Every required GitHub Actions check is **completed successfully** on the current PR head, including `architecture` and `Disposable PostgreSQL concurrency and audit regression`.
3. Review the changed code and the CI result, and resolve substantive findings. Do not claim a formal GitHub approval if none was recorded.
4. Squash merge using the verified head SHA. Never merge when checks are queued, running, cancelled or failing; never use an administrative bypass to skip these gates.
5. If checks fail, inspect job logs, fix the underlying problem, and require fresh successful checks on the new head before merging.

## Review policy

An independent approving reviewer is **not mandatory while this is a solo-maintainer repository**. GitHub disallows approving your own pull request. A self-review or AI-assisted review may identify problems, but it is not a substitute for a formal independent GitHub approval and must never be described as one.

If a branch rule requires an independent approval, respect the rule and obtain a different authorized reviewer or deliberately change the repository's rule through GitHub Settings; do not bypass it.

## Settings to verify

Repository **Settings → Rules → Rulesets** (or **Settings → Branches → Branch protection rules**): for `main`, require status checks `architecture` and `Disposable PostgreSQL concurrency and audit regression`; do not require approving pull request reviews for the solo-maintainer phase. Keep pull requests required and prevent force-push/deletion. Confirm the actual check names and rules against GitHub's current UI.

## Revisit

Require independent approval when additional maintainers join, when deployment/security risk warrants it, or before handling production customer data. Keep CI mandatory in all cases.
