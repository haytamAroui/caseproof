"""Prove denied outbound HTTP at the container network boundary."""
import errno
import os
import socket

import pytest


@pytest.mark.skipif(
    os.getenv("CASEPROOF_EGRESS_PROBE") != "1",
    reason="Executed by the required isolated Docker probe workflow",
)
def test_outbound_http_is_denied_by_network_boundary():
    # Numeric public IPv4 address avoids DNS and proxy configuration.
    try:
        with socket.create_connection(("93.184.215.14", 80), timeout=3) as sock:
            sock.sendall(b"GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n")
            raise AssertionError("outbound TCP/HTTP unexpectedly connected")
    except OSError as exc:
        assert exc.errno in {
            errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EPERM, errno.EACCES,
        }, f"not a proven network-isolation denial: {exc}"
