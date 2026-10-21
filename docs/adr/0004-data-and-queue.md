# ADR 0004-data-and-queue

**Status:** accepted as initial design baseline, subject to empirical and legal validation.

## Decision
Dedicated tenant-scoped Postgres and private EU storage; use database transactional job/lease/outbox for durable processing initially. Enforce idempotency, retries, audit, checkpoints and finite worker jobs. Redis/Celery are future choices only with empirical throughput evidence.

## Revisit criteria
A demonstrated business, correctness, reliability, privacy or cost requirement that the chosen architecture cannot satisfy.
