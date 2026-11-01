# CaseProof frontend design foundation

## Overview

Product register: a litigation reviewer inspects a reference against preserved evidence. The reading surface dominates; separate dimension cells are the signature. This real client replaces temporary screens incrementally; it does not inherit finance workflows. Root DESIGN.md remains historical context; this client owns its runtime tokens.

## Colors

The canonical owner is src/app/theme.css. --accent #103a4b, --ink #172d38, --muted #435e6b, --surface #ffffff, --line #c7d4db, --danger #9a2727, --focus #126a9b. Canvas #f4f7f9. Danger always includes text. No overall-verdict color or badge.

## Typography

Local system sans for controls and text; local monospace for hashes and technical provenance. Body 16px, metadata 12px, headings 20–38px. No remote fonts.

## Layout

Header, content, footer. Review queue alongside inspection, stacked below 760px. Document scroll remains natural; queue owns bounded internal scrolling. Native buttons and details; 44px controls; visible focus and skip link. No decorative motion.

## Elevation & Depth

Dividers and surfaces, no decorative shadows.

## Shapes

6px controls and dimension cells. Source inspection remains a reading surface.

## Components

shared/ui owns button, notice and state-value display. Native label/input and details are deliberate platform-owned controls. No select, date picker or destructive dialog in this slice. Scrollbar baseline applies to all surfaces, with forced-colors fallback.

## Do's and Don'ts

Escape source strings through React. Preserve unknown/unsupported states. API owns results. Read-only foundation must visibly disclose missing page/review adapters. Reused third-party source requires attribution and interaction tests. No design-library copy is included in this slice.
