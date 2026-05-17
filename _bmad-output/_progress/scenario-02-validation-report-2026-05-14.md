---
date: 2026-05-14
auditor: Sally (WDS UX Designer — Validation Mode)
scope: Scenario 02 — Conrad Clears a Vestibule Bottleneck (1 document)
stepsCompleted: [1,2,3,4,5,6,7,8,9,10]
---

# Validation Report — Scenario 02 Specs

**Scope:** `D-UX-Design/scenario-02-specs/` — 1 document
**Date:** 2026-05-14
**Auditor:** Sally / Freya (WDS UX Designer)
**Adapted for:** Single-document alert state spec (extends Scenario 01 base state)

---

## Documents Audited

| # | File | States covered |
|---|------|---------------|
| 01 | `01-conductor-app-vestibule-congestion.md` | Congestion Alert Active · PA Sent / Monitoring · Auto-Resolved |

---

## Check 1 — Page Metadata

Validates: scenario context, interface, state, base state, date, status.

| Doc | Scenario | Interface | State | Base state | Date | Status |
|-----|----------|-----------|-------|-----------|------|--------|
| 01 | ✅ Scenario 02 | ✅ Conductor App (handheld) | ✅ Alert Active — Vestibule Congestion | ✅ `scenario-01-specs/01-conductor-app-home-screen.md` | ✅ 2026-05-14 | ✅ Draft |

**Status: ✅ PASS**

---

## Check 2 — State Flow Overview

Validates: entry/exit triggers defined, predecessor/successor states named, state diagram present.

| Doc | State diagram | Entry trigger | Exit trigger | Prev/Next named |
|-----|--------------|--------------|-------------|----------------|
| 01 | ✅ ASCII | ✅ Threshold + stop-exclusion passed | ✅ Sensor clears below threshold | ✅ Normal (en-route) named as predecessor |

**Issue found:**
⚠️ The state flow table lists "Normal" as the predecessor state but uses the generic label "Normal (en-route)" — the spec says the base state is `scenario-01-specs/01-conductor-app-home-screen.md`. The state table should reference the OBJECT ID `ca-header` / home screen by name, or explicitly state "Home Screen Normal (base state) — see Scenario 01 spec." Minor consistency gap.

**Issue found:**
⚠️ The "PA Sent — Monitoring" state appears in the state flow diagram but does NOT appear in the state table below it. The diagram shows it as a distinct state (after Conrad sends PA), but the table only lists "Normal," "Congestion Alert Active," and "Auto-resolved." The PA Sent state is described in the detail section but omitted from the formal state table.

**Status: ⚠️ NEEDS MINOR FIX** — PA Sent state missing from state flow table; base state naming inconsistency.

---

## Check 3 — Purpose & Story

Validates: clear Purpose statement and narrative connecting to Conrad's operational context.

| Doc | Purpose statement | Narrative | Trigger map connection |
|-----|------------------|-----------|-----------------------|
| 01 | ✅ "vestibule congestion alert mid-journey... resolve the bottleneck without walking to the coach first" | ✅ Implied — heatmap + PA workflow | ✅ Conrad's core concern: remote awareness without physical presence |

**Note:** No explicit "The Story" narrative section in this spec (unlike Scenario 01 and 10 docs). Purpose statement is clear and actionable. The design rationale sections carry the narrative. Minor structural variance from the Scenario 10 pattern but acceptable — the purpose is unambiguous.

**Status: ✅ PASS**

---

## Check 4 — Object ID Completeness

Validates: every UI element introduced has a unique OBJECT ID, IDs follow consistent naming convention.

| OBJECT ID | Type | Notes |
|-----------|------|-------|
| `ca-congestion-detail` | New | Full-screen detail panel |
| `ca-congestion-heatmap` | New | Inference-derived density overlay |
| `ca-congestion-actions` | New | Action strip within detail panel |
| `ca-congestion-pa-modal` | New | PA pre-fill modal |

**Elements without OBJECT IDs:**
- Alert banner (congestion variant) — uses base `ca-alert-banner` from Scenario 01 ✅ correct (variant, not new element)
- Context line (auto-generated interpretation) — inline text within `ca-congestion-detail`, not a distinct component ✅ acceptable
- "PA sent — [HH:MM:SS]" status line — inline state within `ca-congestion-detail` ✅ acceptable

**Naming convention check:**
- All `ca-` prefixed ✅
- No duplicates with Scenario 01 IDs ✅
- Consistent with naming pattern (`ca-[scenario]-[element]`) ✅

**Status: ✅ PASS**

---

## Check 5 — Section Order & Structure

Validates: standard WDS section sequence maintained.

| Doc | Purpose | State Flow | State desc | Interaction Rules | Rationale | Accessibility | Decisions | Related |
|-----|---------|-----------|-----------|------------------|-----------|--------------|-----------|---------|
| 01 | ✅ | ✅ | ✅ (alert banner + 4 layout sections) | ✅ (5 rules) | ✅ (3 items) | ✅ | ✅ | ✅ |

**Status: ✅ PASS**

---

## Check 6 — Object Registry

Validates: all introduced OBJECT IDs are referenced consistently; no orphan IDs.

| OBJECT ID | Defined? | Referenced in Rules/Accessibility? |
|-----------|----------|------------------------------------|
| `ca-congestion-detail` | ✅ | ✅ State Flow, alert banner tap action |
| `ca-congestion-heatmap` | ✅ | ✅ Interaction Rule 5 (vestibule zone only), Accessibility |
| `ca-congestion-actions` | ✅ | ✅ Layout section, auto-resolve behaviour |
| `ca-congestion-pa-modal` | ✅ | ✅ Action strip PA action |

**Issue found:**
⚠️ `ca-congestion-actions` defines "No action — Monitor" as logging "Monitored — no PA sent" but this resolution code is not in the auto-resolve logging section. The logging section only defines `RESOLVED_PA` and `RESOLVED_AUTO`. If Conrad selects "Monitor — no action" and congestion then clears automatically, the log should record `RESOLVED_AUTO` (congestion cleared without PA) — this is probably correct, but the mapping between "Monitor" choice and resolution code is not explicit.

**Status: ⚠️ NEEDS MINOR FIX** — Clarify that "Monitor — no action" + subsequent auto-resolve logs as `RESOLVED_AUTO`.

---

## Check 7 — Design System Separation

Validates: no raw hex codes or CSS values; colour references use tokens.

**Doc 01 scan:**
- `--color-warning-amber` ✅ token
- `--color-occupancy-green`, `--color-occupancy-amber`, `--color-occupancy-red` ✅ tokens
- 44px PA modal text area height ⚠️ — pixel value
- 56px Send button height ⚠️ — pixel value
- 30%, 70% zone density thresholds — functional thresholds, not styling ✅ acceptable
- 15-second heatmap update cycle — system spec ✅ acceptable

**Assessment:** Pixel values are touch target constraints. Colour references use tokens throughout.

**Status: ✅ PASS**

---

## Check 8 — SEO Compliance

**Not applicable.** Native handheld app. Skipped.

---

## Check 9 — Cross-Spec Consistency

Validates: shared concepts consistent with Scenario 01 base state and other scenarios.

| Concept | Scenario 01 base | Scenario 02 | Consistency |
|---------|-----------------|-------------|-------------|
| `ca-alert-banner` usage | Defined with severity colour variants | Congestion variant: `--color-warning-amber` + pulsing | ✅ Consistent with banner spec (amber = action required, pulsing) |
| `ca-alert-feed-item` | Defined | Referenced (alert fires to feed) | ✅ Feed item implied by alert system |
| Hailo-8 15s inference cycle | 15s en-route / 8s boarding | 15s heatmap update | ✅ Consistent |
| Auto-resolve pattern | Not yet defined in Scenario 01 | First instance defined here | ✅ Establishes pattern for subsequent scenarios |
| Stop-exclusion logic | Not applicable (Scenario 01 is monitoring only) | 3 min pre-stop suppression | ✅ New constraint introduced correctly |
| Touch targets | 44px minimum | 44px PA modal / 56px send button | ✅ Consistent with Scenario 01 minimum; elevated for urgent action |

**Cross-scenario check:**
- Auto-resolve pattern introduced here is referenced correctly in Scenarios 02b, 02c, 02d, 06 ✅
- Terminus suppression (5 min) introduced here — consistent with Scenario 02b (10 min imbalance suppression) ✅ (different alert types may have different suppressions — acceptable)
- `RESOLVED_PA` / `RESOLVED_AUTO` codes introduced here — not explicitly referenced in later specs but pattern is consistent ✅

**Status: ✅ PASS**

---

## Check 10 — Final Validation & Scenario Coverage

Validates: all UI states from Scenario 02 storyboard covered in spec.

Cross-referencing against Scenario 02 storyboard — Conrad receives vestibule congestion alert, views heatmap, sends PA, congestion clears.

| Storyboard need | Spec doc | Covered? |
|----------------|----------|---------|
| Alert appears for vestibule congestion | 01 | ✅ `ca-alert-banner` congestion variant |
| Conrad can see which zone is congested | 01 | ✅ `ca-congestion-heatmap` — spatial view |
| Conrad can see time to next stop | 01 | ✅ Header sub-detail + context line |
| Conrad can send PA announcement | 01 | ✅ `ca-congestion-pa-modal` pre-fill |
| Alert clears when congestion resolves | 01 | ✅ Auto-resolve on sensor clear |
| No alert when passengers pre-position for stop | 01 | ✅ 3-min stop-exclusion rule |
| No alert at journey end | 01 | ✅ 5-min terminus suppression |

**All storyboard states covered. ✅**

**Edge case check:**

| Edge case | Specced? |
|-----------|---------|
| Conrad sends PA, congestion doesn't clear in 5 min | ✅ Rule 4 — alert stays active; sensor determines resolution |
| Congestion alert fires mid-PA-modal (new alert) | ⚠️ Not addressed — if a second coach gets congestion while Conrad is composing the PA for coach 4, does `ca-alert-banner` update to show the new (possibly higher priority) alert? The "+N more" badge from Scenario 01 handles this in the feed, but the interaction while modal is open is undefined |
| Train delayed — scheduled stop ±3 min window shifts | ⚠️ The 3-min stop-exclusion is keyed on "scheduled stop" — if the train is delayed, the actual stop may be later, but the exclusion window fires at the scheduled time. This could suppress a legitimate alert. HAFAS real-time data or TCMS stop proximity would be more accurate than schedule. Not critical but worth noting |

**Status: ⚠️ TWO MINOR GAPS** — Second alert during modal; delay vs schedule in stop-exclusion logic.

---

## Summary

### Issues — Resolution Log

| Priority | Issue | Doc | Resolution |
|----------|-------|-----|------------|
| 🟡 Medium | PA Sent state missing from state flow table | 01 | ✅ **Resolved** — "PA Sent — Monitoring" row added to state table: Entry = Conrad sends PA; Exit = vestibule sensor clears (alert auto-resolves regardless of PA status) |
| 🟡 Medium | New alert during PA modal not addressed | 01 | ✅ **Resolved** — Interaction Rule added: if a new alert fires while `ca-congestion-pa-modal` is open, `ca-alert-banner` updates (badge increments); modal stays open; Conrad completes or cancels current PA first |
| 🟢 Low | "Monitor" action to resolution code mapping unclear | 01 | ✅ **Resolved** — `ca-congestion-actions` spec clarified: "Monitor — no action" + subsequent auto-clear → logs `RESOLVED_AUTO`; "PA sent" + subsequent auto-clear → logs `RESOLVED_PA` |
| 🟢 Low | Base state reference inconsistency in state table | 01 | ✅ **Resolved** — Predecessor state labelled "Home Screen Normal — `scenario-01-specs/01-conductor-app-home-screen.md`" |
| 🟢 Low | Delay vs schedule in stop-exclusion logic | 01 | ✅ **Resolved** — Open Question added: confirm whether stop-exclusion window uses HAFAS schedule time or TCMS proximity signal. TCMS preferred; schedule fallback acceptable. |

### Overall Status — Post-Fix

| Check | Result |
|-------|--------|
| 1 — Metadata | ✅ PASS |
| 2 — State Flow | ✅ PASS |
| 3 — Purpose & Story | ✅ PASS |
| 4 — Object ID Completeness | ✅ PASS |
| 5 — Section Order | ✅ PASS |
| 6 — Object Registry | ✅ PASS |
| 7 — Design System Separation | ✅ PASS |
| 8 — SEO | N/A |
| 9 — Cross-Spec Consistency | ✅ PASS |
| 10 — Scenario Coverage | ✅ PASS |

**Overall: ✅ READY FOR HANDOFF**

---

## Quality Audit

**Status:** ✅ READY FOR HANDOFF
**Audit Date:** 2026-05-14
**Audited By:** Sally (WDS UX Designer — Validation Mode)

**Compliance:**
- ✅ Metadata complete and correct
- ✅ State Flow (all states including PA Sent now in table; triggers defined)
- ✅ Purpose & Story (purpose clear; narrative embedded in rationale)
- ✅ Object ID Completeness (4 new IDs; `ca-` prefix consistent; no duplicates)
- ✅ Section Order (standard sequence maintained)
- ✅ Object Registry (all IDs referenced; resolution code mapping clarified)
- ✅ Design System Separation (tokens used; pixel values are touch target constraints)
- ✅ Cross-Spec Consistency (auto-resolve pattern established correctly; thresholds consistent)
- ✅ Scenario Coverage (all storyboard states covered; edge cases addressed)

**External dependencies still open (not spec gaps):**
- ⏳ Hailo-8 vestibule zone segmentation accuracy on R5001C (ML team)
- ⏳ Congestion threshold metric — count vs density % (Nomad Digital product)
- ⏳ Stop-exclusion: TCMS proximity vs HAFAS schedule (systems integration)

---

*Generated by Sally (WDS UX Designer — Validation Mode) · 2026-05-14*
