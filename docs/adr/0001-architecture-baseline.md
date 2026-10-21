# ADR 0001-architecture-baseline

**Status:** accepted as initial design baseline, subject to empirical and legal validation.

## Decision
Adopt hexagonal architecture, DDD-inspired bounded modules and a modular monolith. Separate worker process is an operational component, not microservice architecture. Reject premature distributed services; reconsider when measured domain ownership or scaling requires it.

## Revisit criteria
A demonstrated business, correctness, reliability, privacy or cost requirement that the chosen architecture cannot satisfy.
