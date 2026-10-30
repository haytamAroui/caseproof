"""Kernel network isolation smoke test for OCR subprocesses.

This test is meaningful only on Linux with user/network namespaces enabled.
It fails rather than claiming success when the runner cannot create a namespace.
"""
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "linux", reason="Linux network namespace required")
def test_ocr_network_namespace_blocks_outbound_http():
    binary = shutil.which("unshare")
    assert binary, "unshare is required for OCR isolation"
    probe = subprocess.run(
        [binary, "--user", "--map-root-user", "--net", "--",
         sys.executable, "-c",
         "import urllib.request; urllib.request.urlopen('http://example.com', timeout=3)"],
        capture_output=True, text=True, timeout=12, check=False,
    )
    assert probe.returncode != 0, "unauthorized HTTP request unexpectedly succeeded"
    assert "Operation not permitted" not in probe.stderr, (
        "sandbox creation itself failed; outbound HTTP denial has not been proven"
    )
