# Pilot readiness follow-ups

## Frontend bundle-size follow-up

The 4 November 2026 production Vite build warned that an application chunk exceeded 500 kB after minification (about 529 kB before gzip in the local build). Measure production load time and memory on the supported pilot device and network profile, inspect the bundle composition, and split or defer code where measurements justify it. Record the measured baseline, target, resulting build and reviewer decision. Do not change the warning threshold or claim a performance problem is resolved without measurements.

This is a performance follow-up, not a substitute for the separate security, accessibility, representative corpus, operational and practitioner acceptance gates in [the P5/P6 acceptance matrix](P5_P6_ACCEPTANCE_MATRIX.md).
