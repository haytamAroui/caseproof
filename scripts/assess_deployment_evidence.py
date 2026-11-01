"""Report mode-specific evidence completeness, never deployment approval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.security.deployment_assessment import assess

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    args = parser.parse_args()
    record = json.loads(args.profile.read_text())
    if not isinstance(record, dict):
        raise SystemExit('assessment must be a JSON object')
    result = assess(record)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ready_for_independent_review'] else 1)
