"""Generate frontend JSON Schema from the Python response projection."""
import argparse
import json
from pathlib import Path

from application.litigation.frontend_contract import DossierView
from application.litigation.workspace_contract import MatterCatalogView

TARGET = Path(__file__).resolve().parents[1] / "frontend/src/shared/api/dossier.schema.json"
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for model, target in ((DossierView, TARGET),
                          (MatterCatalogView, TARGET.with_name("matters.schema.json"))):
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
