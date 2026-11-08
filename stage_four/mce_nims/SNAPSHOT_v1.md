# Literature Snapshot v1

**Date:** 7 November 2026  
**Source:** NIMS La(Fe,Si)₁₃ dataset (doi:10.48505/nims.4909)

## Counts
- Records: 1,113 (from 221 papers)
- Points: 1,539 (1,386 ΔsT + 153 ΔTad)
- Composition keys: 660 distinct
- Lab samples with exact match: 7 (→ 180 records)

## Verification
All four checks passed: import idempotency, sample linking, consistency
report (0 collisions), bracket-composition audit (1 expected pre-alloy entry).
See `snapshot_v1_report.tex` for full details and terminal output.

## Decision
Train on NIMS only. Adding MCEdatabase + Kelly & Cole + Court & Cole
showed no improvement in LOFO CV (pre-registered criterion, ~4 Nov 2026).