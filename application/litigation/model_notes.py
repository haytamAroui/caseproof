"""Optional generative annotations, separate from canonical verification results."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from application.litigation.content_release import ContentRelease


@dataclass(frozen=True, slots=True)
class ModelNote:
    kind: Literal['note', 'review_request']
    text: str
    case_id: str
    brief_id: str
    snapshot_hash: str
    provider: str
    model: str
    model_version: str
    destination: str
    label: str = 'Generative annotation — not a verification result or reviewer decision'
    schema: str = 'caseproof-model-note-v1'


def make_model_note(*, report: dict[str, Any], output: dict[str, Any], provider: str,
                    model: str, model_version: str, destination: str,
                    release: ContentRelease | None, bearer: str, now: datetime) -> ModelNote:
    """Return a separate immutable object; never merge model fields into a report.

    Provider/version/destination are trusted host configuration, not model keys.
    Authorization for persistence would still require current matter permissions.
    This pure boundary does not call a model or persist anything.
    """
    if set(output) != {'kind', 'text'} or output['kind'] not in ('note', 'review_request'):
        raise ValueError('only separately labelled notes or review requests are permitted')
    if type(output['text']) is not str or not 1 <= len(output['text'].strip()) <= 4000:
        raise ValueError('bounded annotation text required')
    if any(type(value) is not str or not 1 <= len(value) <= 128
           for value in (provider, model, model_version, destination)):
        raise ValueError('trusted provider and version provenance required')
    case, brief, snapshot = (report.get(key) for key in ('case_id', 'brief_id', 'snapshot_hash'))
    if not isinstance(case, str) or not isinstance(brief, str) or not isinstance(snapshot, str):
        raise ValueError('frozen report binding required')
    if not case or not brief or not re.fullmatch('[0-9a-f]{64}', snapshot):
        raise ValueError('frozen snapshot hash required')
    if release is None or not release.permits(bearer=bearer, case_id=case, brief_id=brief,
            snapshot_hash=snapshot, destination=destination, now=now):
        raise ValueError('annotation destination release not authorized')
    return ModelNote(output['kind'], output['text'], case, brief, snapshot,
                     provider, model, model_version, destination)
