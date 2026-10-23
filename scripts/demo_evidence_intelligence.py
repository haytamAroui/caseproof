"""Offline synthetic finance/construction demonstration, no external provider calls."""

import json

from application.extraction.journal import MemoryJournal
from application.extraction.pipeline import EvidenceIntelligence, project_to_kernel
from domains.construction.extraction_rules import ConstructionEvidencePolicy
from domains.finance.extraction_rules import FinanceEvidencePolicy
from scripts.extraction_fixtures import ScriptedProvider, request


def main() -> None:
    for construction in (False, True):
        req = request(construction=construction)
        policy = ConstructionEvidencePolicy() if construction else FinanceEvidencePolicy()
        report = EvidenceIntelligence(ScriptedProvider(), MemoryJournal(), policy).run(req)
        projection = project_to_kernel(req, report)
        print(
            json.dumps(
                {
                    "synthetic_only": True,
                    "domain": policy.namespace,
                    "report": json.loads(report.to_json()),
                    "kernel_blockers": projection.blockers,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
