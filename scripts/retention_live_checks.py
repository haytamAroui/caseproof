"""Signed retention assertions against the exact ephemeral four-file matter."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

from scripts.m5_benchmark_live_acceptance import crop, direct
from scripts.purge_deleted_matters import purge
from scripts.soft_delete_matter import rpc
from scripts.verify_dev_live_review_roundtrip import _request


def check_retention(owner, sessions, key, case, base, doc, version, box, registered):
    admin = os.environ['CASEPROOF_DEV_AUTH_ADMIN_KEY']
    admin_token = admin if admin.startswith('eyJ') else None
    run = os.environ['CASEPROOF_P3_RUN_ID']
    # Unassigned same-organization and foreign actors cannot erase the matter.
    for role in ('ungranted', 'foreign'):
        status, _ = direct(sessions[role], key, '/rest/v1/rpc/caseproof_soft_delete_matter',
                           'POST', {'p_case': case})
        if status not in (401, 403, 404):
            raise RuntimeError('unauthorized soft deletion succeeded')
    env = dict(os.environ, CASEPROOF_OWNER_JWT=owner)
    result = subprocess.run([sys.executable, '-m', 'scripts.soft_delete_matter', '--matter-id', case],
                            env=env, capture_output=True, text=True, timeout=45)
    if result.returncode or result.stdout.strip() != 'MATTER_SOFT_DELETED':
        raise RuntimeError('signed soft-delete CLI failed')
    for route in ('/discovery', '/export'):
        status, _ = _request(owner, 'GET', base + route)
        if status not in (403, 404):
            raise RuntimeError('soft-deleted verification still available')
    status, _ = crop(owner, case, doc, version, box)
    if status not in (403, 404):
        raise RuntimeError('soft-deleted crop still available')
    status, raw = direct(owner, key, '/rest/v1/rpc/caseproof_signed_ocr_geometry',
                         'POST', {'p_version': version, 'p_page': 1})
    if status == 200 and raw.strip() != b'[]':
        raise RuntimeError('soft-deleted OCR geometry still available')
    org = os.environ['CASEPROOF_P3_ORG_ID']
    for source in registered:
        path = '/'.join((org, case, source['document_id'], source['version_id'], source['sha256']))
        status, _ = direct(owner, key, '/storage/v1/object/authenticated/caseproof-originals-dev/' + path)
        if status not in (400, 401, 403, 404):
            raise RuntimeError('soft-deleted original still downloadable')
    print('RETENTION_SIGNED_OWNER_CROP_GEOMETRY_ORIGINAL_EXPORT_DENIED', flush=True)
    try:
        purge(case, admin)
    except RuntimeError:
        pass
    else:
        raise RuntimeError('grace period bypassed')
    if rpc(admin, admin_token, 'caseproof_retention_test',
           {'p_run': run, 'p_case': case, 'p_action': 'age'}) is not True:
        raise RuntimeError('exact ephemeral aging failed')
    first = purge(case, admin)
    if purge(case, admin) != first:
        raise RuntimeError('purge retry changed receipt')
    verified = rpc(admin, admin_token, 'caseproof_retention_test',
                   {'p_run': run, 'p_case': case, 'p_action': 'verify'})
    digest = hashlib.sha256(case.encode()).hexdigest()
    if not isinstance(verified, dict) or verified.get('residual_rows') != 0:
        raise RuntimeError('residual matter data')
    receipt = verified.get('receipt')
    if not isinstance(receipt, dict) or set(receipt) != {
        'matter_digest', 'deleted_at', 'purged_at', 'erased_audit_events',
    } or receipt['matter_digest'] != digest or receipt['erased_audit_events'] < 1:
        raise RuntimeError('minimal erasure receipt missing or contains unexpected fields')
    print('RETENTION_STORAGE_DB_PURGE_RETRY_AND_MINIMAL_AUDIT_PASSED', flush=True)
