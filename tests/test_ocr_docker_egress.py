"""Proof of denied outbound HTTP from a Docker --network none worker.

The probe uses only Python stdlib; missing libraries cannot cause success.
The CI runner separately asserts that the container has network mode 'none'.
"""
import errno
import socket
import urllib.error
import urllib.request


def test_outbound_http_is_denied_by_network_boundary():
    try:
        urllib.request.urlopen(
            urllib.request.Request("http://93.184.215.14/", headers={"Host": "example.com"}),
            timeout=3,
        )
    except urllib.error.URLError as exc:
        reason = exc.reason
        assert isinstance(reason, OSError), f"unexpected URL failure: {exc}"
        assert reason.errno in {
            errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EPERM, errno.EACCES,
        }, f"not a network isolation denial: {reason}"
    except OSError as exc:
        assert exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EPERM, errno.EACCES}
    else:
        raise AssertionError("worker unexpectedly reached external HTTP")
