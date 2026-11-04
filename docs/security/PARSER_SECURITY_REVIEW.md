# P1 parser security review

| Threat | Mitigation | CI evidence |
| --- | --- | --- |
| ZIP bombs and hostile archives | Bound entry counts and expanded sizes. Reject encrypted entries, traversal, and duplicate names. Return unknown coverage when decompression fails. | [Kernel checks](https://github.com/haytamAroui/caseproof/actions/runs/41875123217) ran 1,024 deterministic mutations (256 archive and 768 XML-part mutations) with time and memory limits, alongside hostile-input regressions. |
| XML injection, entity expansion, and external references | Disable DTDs and entity expansion. Apply shared XML resource limits to package metadata, relationships, document body, and notes. Reject external relationships in the isolated parser. | [Kernel checks](https://github.com/haytamAroui/caseproof/actions/runs/41875123217) exercise hostile declarations, malformed XML, and the isolated worker. |
| Worker network egress | Run the OCR worker in Docker with networking disabled in the signed test configuration. | [Docker egress probe and signed benchmark](https://github.com/haytamAroui/caseproof/actions/runs/41875113829) verified network mode `none` and passed the probe. |
| Unauthorized access to parser-derived evidence | Apply signed matter access checks and enforce revocation when reopening evidence. | [Signed browser acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41875122925) recorded HTTP 404 after intake access was revoked, verified export denial, and confirmed cleanup. |

These runs cover the tested configurations and synthetic fixtures. The egress probe covers the Docker OCR configuration. The mutation run is a bounded smoke test.

## Independent Reviewer Sign-off

