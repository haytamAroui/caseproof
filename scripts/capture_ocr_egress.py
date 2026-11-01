"""Synthetic packet-capture proof for the OCR network namespace only.

Requires an isolated Linux CI runner, Docker, sudo, nsenter and tcpdump.
This is not a capture or approval of hosted/hybrid/firm-controlled deployments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

PROBE = r'''
import json, socket
assert sorted(name for _, name in socket.if_nameindex()) == ['lo']
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(b'CASEPROOF_SYNTHETIC hash=fixture reference=Exhibit-A verdict=not_assessed', ('127.0.0.1', 54321))
s.close()
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('192.0.2.1', 443))
except OSError:
    denied = True
else:
    denied = False
finally:
    s.close()
assert denied, 'unexpected outbound connection'
print(json.dumps({'synthetic_outbound_attempt_denied': denied}))
'''


def run(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout.strip()


def capture(output: Path, image: str):
    output.mkdir(parents=True, exist_ok=True)
    name = 'caseproof-egress-' + uuid4().hex
    pcap = output.resolve() / 'ocr-namespace.pcap'
    if pcap.exists():
        raise FileExistsError('use a fresh capture output directory')
    process = None
    created = False
    try:
        run(['docker', 'run', '--detach', '--name', name, '--network', 'none', '--read-only',
             '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', image, 'sleep', '120'])
        created = True
        pid = run(['docker', 'inspect', '--format', '{{.State.Pid}}', name])
        if not pid.isdecimal() or int(pid) <= 1:
            raise RuntimeError('invalid test container PID')
        with (output / 'capture-diagnostics.txt').open('w') as diagnostics:
            process = subprocess.Popen(['sudo', 'nsenter', '--target', pid, '--net', '--',
                'tcpdump', '-Z', 'root', '-i', 'any', '-U', '-w', str(pcap)],
                stdout=diagnostics, stderr=diagnostics, start_new_session=True)
            for _ in range(30):
                if process.poll() is not None:
                    raise RuntimeError('packet capture did not start')
                if pcap.exists() and pcap.stat().st_size >= 24:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('packet capture readiness timeout')
            probe = json.loads(run(['sudo', 'nsenter', '--target', pid, '--net', '--', sys.executable, '-c', PROBE]))
            # Exercise the real OCR executable inside the captured namespace.
            run(['docker', 'exec', name, 'tesseract', '--version'])
            time.sleep(0.3)
            run(['sudo', 'kill', '-INT', '--', '-' + str(process.pid)])
            process.wait(timeout=10)
        loopback = run(['sudo', 'tcpdump', '-nn', '-r', str(pcap), 'net', '127.0.0.0/8'])
        outbound = run(['sudo', 'tcpdump', '-nn', '-r', str(pcap), 'not', 'net', '127.0.0.0/8', 'and', 'not', 'host', '::1'])
        if not loopback or outbound:
            raise RuntimeError('capture control missing or unexpected egress observed')
        result = {'schema': 'caseproof-ocr-egress-capture-v1', 'synthetic_only': True,
                  'scope': 'ocr_network_namespace', 'whole_deployment_approved': False,
                  'modes_approved': [], 'model_or_client_data_used': False,
                  'loopback_control_observed': True, 'non_loopback_packets': 0,
                  'pcap_sha256': hashlib.sha256(pcap.read_bytes()).hexdigest(), **probe,
                  'limits': ['Namespace probe plus OCR version command; not the whole application lifecycle',
                             'No claim about browser/Auth/API/Storage/telemetry/backups or any customer configuration']}
        (output / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        if process is not None and process.poll() is None:
            subprocess.run(['sudo', 'kill', '-KILL', '--', '-' + str(process.pid)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            process.wait(timeout=10)
        if created:
            run(['docker', 'rm', '--force', name])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', default='caseproof-ocr-worker:ci')
    args = parser.parse_args()
    print(json.dumps(capture(args.output, args.image), indent=2))
