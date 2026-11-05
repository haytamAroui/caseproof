"""Generate frontend JSON Schema from the Python response projection."""

import argparse
import json
from pathlib import Path

from application.capacity_envelope import CAPACITY_POLICY
from application.litigation.frontend_contract import DossierView
from application.litigation.viewer_contract import ViewerContext
from application.litigation.workspace_contract import (
    DraftExcerptView,
    MatterCatalogView,
    ReportCatalogView,
    ReviewLedgerView,
)
from apps.api.dossier_journey import (
    CorrectionCommitBody,
    CorrectionPreviewBody,
    DocxLocatorIdentity,
    InventoryConfirmation,
    VisualDecisionBody,
)
from apps.api.workspace_auth import SessionView
from apps.api.workspace_intake import CreatedMatter, IntakeView, OrganizationView

TARGET = Path(__file__).resolve().parents[1] / "frontend/src/shared/api/dossier.schema.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    policy_target = TARGET.with_name("capacity-policy.json")
    policy_content = json.dumps(CAPACITY_POLICY, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not policy_target.exists() or policy_target.read_text() != policy_content:
            raise SystemExit("Capacity policy drift: regenerate frontend contracts")
    else:
        policy_target.write_text(policy_content)
    for model, target in (
        (DossierView, TARGET),
        (MatterCatalogView, TARGET.with_name("matters.schema.json")),
        (SessionView, TARGET.with_name("session.schema.json")),
        (ReportCatalogView, TARGET.with_name("reports.schema.json")),
        (OrganizationView, TARGET.with_name("organizations.schema.json")),
        (CreatedMatter, TARGET.with_name("created.schema.json")),
        (IntakeView, TARGET.with_name("intake.schema.json")),
        (InventoryConfirmation, TARGET.with_name("confirmation.schema.json")),
        (ViewerContext, TARGET.with_name("viewer.schema.json")),
        (ReviewLedgerView, TARGET.with_name("review-ledger.schema.json")),
        (DraftExcerptView, TARGET.with_name("draft-excerpt.schema.json")),
        (VisualDecisionBody, TARGET.with_name("review-command.schema.json")),
        (DocxLocatorIdentity, TARGET.with_name("docx-locator-v1.schema.json")),
        (CorrectionPreviewBody, TARGET.with_name("correction-preview-v1.schema.json")),
        (CorrectionCommitBody, TARGET.with_name("correction-commit-v1.schema.json")),
    ):
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        content = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        if args.check:
            if not target.exists() or target.read_text() != content:
                raise SystemExit("Frontend schema drift: run python -m scripts.generate_frontend_contract")
        else:
            target.write_text(content)


if __name__ == "__main__":
    main()
