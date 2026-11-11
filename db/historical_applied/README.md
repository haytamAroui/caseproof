# Applied SQL receipts — audit-only

These eight files reproduce the **exact statement strings** recorded by the
`caseproof-dev` Supabase migration ledger as of 11 November 2026.

Their original reviewed-source classification was four DIVERGENT_SOURCE and
three NO_SOURCE, plus one same-version Data Rights Ledger mismatch. Every recovered statement matches its recorded SHA-256, version,
migration name, and character length, checked by `verify_migration_lineage`.

These files are **not** active migrations, not a fresh-install strategy, and
not approved for production or confidential client data. They intentionally
live outside `supabase/migrations`.

Some statements create privileged development-only functions. Do not copy these
files into executable migrations or run them without explicit security review,
ordered dependency analysis, and disposable PostgreSQL replay acceptance.
No linked database was changed by this archive.
