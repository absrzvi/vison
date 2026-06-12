# Micro-spec: "Model details" section — EscalationDetail drawer

**Date:** 2026-06-12 · **Agent:** Freya · **Phase:** WDS-4 (UX Design) · **Story:** 10-1 (AC20)

Resolves the open design decision deferred in story 10-1: placement and presentation of `confidence_score` + `model_versions` in the alert detail drawer.

## Decision

Collapsed disclosure section, placed **directly below the still frame** (below the description when no still frame exists), above the error toast / resolve form. Provenance is verification support — it lives with the evidence, never near the action footer.

## Spec

- **Render condition:** `confidence_basis === "model" || "fused"` only. Sensor-basis alerts render nothing.
- **Collapsed row:** caption `Model details` + chevron (`▸`/`▾`). Meta-label styling: `--obb-text-on-dark-3`, `--font-size-sm`. Full-width clickable, `aria-expanded`, Enter-key toggle (same interaction pattern as the still-frame expand).
- **Expanded body:** background `--obb-surface-2`, padding matching `.esc-detail__meta-bar`.
  - Line 1: `Confidence` · score as percentage with one decimal (`82.0%`) in `--font-mono`, basis appended as plain text `(model)` / `(fused)`.
  - Lines 2+: `model_versions` two-column key/value list — keys `--obb-text-on-dark-3`, values `--font-mono` `--obb-text-on-dark-2`. No truncation of hashes.
- **No severity colour** in this section — colour stays reserved for the severity system.
- Expanded/collapsed state resets when the selected escalation changes (existing `prevEscId` reset block).

## Consistency note

The still-frame chip currently shows `{confidence}% conf` from mock data. Once real `confidence_score` flows, the chip and this section MUST read the same field. Wire both to `confidence_score`.
