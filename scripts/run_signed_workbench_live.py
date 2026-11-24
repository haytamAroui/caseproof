"""Point d'entrée du workbench signé sur les adaptateurs LIVE (jamais par défaut).

Exige CASEPROOF_SUPABASE_PUBLISHABLE_KEY (clé publishable, jamais service) et
refuse de démarrer tant qu'un port du workbench n'a pas d'adaptateur live :
mélanger des backends live et disposable sur un même dossier serait une
incohérence de source de vérité, donc fail-closed. Aucune exécution contre le
projet live n'est autorisée sans décision propriétaire explicite ; ce script
ne crée ni compte, ni clé, ni donnée.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    from apps.api.signed_live_composition import assemble_live_workbench

    try:
        ports = assemble_live_workbench(os.environ)
    except ValueError as exc:
        print(f"CONFIGURATION: {exc}", file=sys.stderr)
        return 2
    if ports.missing:
        print(
            "BOOT REFUSÉ (fail-closed) : ports sans adaptateur live : "
            + ", ".join(ports.missing)
            + ". Aucun mélange live/disposable sur un même dossier.",
            file=sys.stderr,
        )
        return 3
    print("Tous les ports live sont assemblés ; démarrage du workbench.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
