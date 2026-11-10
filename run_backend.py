"""Run the CaseProof loopback development API on http://127.0.0.1:8000.

Injects a no-op stub for the Unix-only `resource` module (used only for
process sandbox rlimits in pdf_ocr.py) so the app can import on Windows.
No customer data, no production deployment, no admin DSN.
"""
import sys
import types

_resource_stub = types.ModuleType("resource")
_resource_stub.RLIMIT_AS = 1
_resource_stub.RLIMIT_CPU = 2
_resource_stub.RLIMIT_FSIZE = 3


class _ResourceError(OSError):
    pass


_resource_stub.error = _ResourceError


def _getrlimit(r):
    return (0, 0)


def _setrlimit(r, limits):
    return None


_resource_stub.getrlimit = _getrlimit
_resource_stub.setrlimit = _setrlimit
sys.modules["resource"] = _resource_stub

import uvicorn
from apps.api.dev_live_entry import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
