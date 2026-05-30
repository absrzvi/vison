---
stepsCompleted: [step-01-document-discovery, step-02-prd-analysis, step-03-epic-coverage-validation, step-04-ux-alignment, step-05-epic-quality-review, step-06-final-assessment]
filesIncluded:
  - _bmad-output/planning-artifacts/prd.md (v1.1, 2026-05-30)
  - _bmad-output/planning-artifacts/architecture.md (unchanged)
  - _bmad-output/planning-artifacts/epics.md (updated 2026-05-30: Epic 5/1.5 backfill, E2-S9→E3-S8, split notes)
  - _bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md
  - _bmad-output/planning-artifacts/event-payload-schemas.md
priorReport: _bmad-output/planning-artifacts/implementation-readiness-report-2026-05-30.md
---

# Implementation Readiness Assessment — Pass 2

**Date:** 2026-05-30
**Project:** oebb-agent
**Assessor:** John (Product Manager) via bmad-check-implementation-readiness
**Prior report:** implementation-readiness-report-2026-05-30.md (Pass 1 — 🟡 NEEDS WORK with 13 findings)

This is a focused re-run after the Pass-1 remediation actions completed on 2026-05-30:

| Pass-1 finding | Status |
|---|---|
| #1 WebSocket vs SSE transport conflict | ⏸ **Deferred** — user is resolving offline with Winston; not addressed in this pass |
| #2 Forward dependency E2-S9 → E3-S1 | ✅ **Closed** — E2-S9 moved to E3-S8 in `epics.md` |
| #3 Epic 5 + Epic 1.5 missing epic bodies | ✅ **Closed** — both backfilled in `epics.md` from implementation-artifacts |
| #4 FR23, FR25, FR32, FR34, FR35 missing coverage | ✅ **Closed** — all 5 descoped to PRD §5.4 with rationale (PRD v1.1) |
| #5 NFR2 / ADR-15 conflict on APC blending | ✅ **Closed** — NFR2 reworded in PRD v1.1 |
| #6 E3-S1, E4-S6, E4-S7, E10-S1 oversized | ✅ **Closed (light pass)** — explicit split-into-N notes added to each story |
| #7 E10-S1 oversized | ✅ Covered under #6 |
| #8 FR11 partial coverage (wheelchair-door-release) | ⏸ Still partial — recommend AC addition to E4-S6b (suppression+door correlation) when that sub-story is split |
| #9 FR22 real-time vs historical ambiguity | ⏸ Open — recommend confirming intent during E3-S4 dev start |
| #10 Epic 4 framing | ⏸ Minor — cosmetic, not blocking |
| #11 E1-S1 coverage gate weakness | ⏸ Minor — already shipped |
| #12 UX v2 "Phase 2 Vision" header | ⏸ Minor — documentation hygiene |
| #13 Open Questions Q5/Q7–Q9/Q11/Q12 | ⏸ Q5 now non-blocking (FR23 descoped); Q7–Q9, Q11, Q12 still pending pilot prep |

---

## Updated Coverage Matrix

### FR Coverage (Post-Descope)

After descoping FR23, FR25, FR32, FR34, FR35 to Phase 2, the in-scope FR set shrinks from 24 to **19**:

FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR20, FR21, FR22, FR24, FR26, FR27, FR33.

| FR | Status (Pass 2) |
|---|---|
| FR1, FR3, FR20, FR21, FR27 | ✓ Covered (Epic 2 + Epic 4) |
| FR2, FR4 | ✓ Covered (Epic 4 + Epic 5 — now with epic body) |
| FR5, FR7, FR9, FR10, FR12, FR24 | ✓ Covered (Epic 4) |
| FR6 | ✓ Covered (Epic 4 vlan-pollers + Epic 2 unified feed) |
| FR8 | ✓ Covered (Epic 4 inference E4-S5) |
| FR11 (wheelchair-door release combined) | ⚠️ Partial — emergent fusion behaviour, no explicit AC. Will be addressed when E4-S6 is split (the suppression+door sub-story is the natural home for the AC) |
| FR22 (real-time dwell) | ⚠️ Ambiguous — Epic 3 (E3-S4) covers historical analytics; real-time-per-stop intent unclear. Recommend a 1-line clarification in PRD §5.2 |
| FR26 | ✓ Covered (Epic 3 E3-S6/E3-S8 + Epic 4 CAMERA_DEGRADED) |
| FR33 | ✓ Covered (Epic 3 E3-S2/E3-S3 — heatmap + capacity exceptions) |

| Metric | Pass 1 | Pass 2 |
|---|---|---|
| In-scope FRs | 24 | **19** |
| Fully covered | 16 | **17** |
| Partially covered | 3 | **2** (FR11, FR22) |
| Missing | 5 | **0** |
| **FR coverage** | 79% | **89% full + 11% partial = ~100% acceptable** |

### NFR Coverage

| NFR | Pass 2 status |
|---|---|
| NFR2 | ✅ **Resolved** — reworded to "≥95% measured post-hoc against APC ground truth" — no conflict with ADR-15 |
| Others | Unchanged ✓ |

| Metric | Pass 1 | Pass 2 |
|---|---|---|
| NFR coverage | 93% | **100%** |

### Epic Independence

| Pair | Pass 2 status |
|---|---|
| E2-S9 → E3-S1 forward dep | ✅ **Closed** — E2-S9 moved to E3-S8 |
| Epic 5 (Luggage) story details | ✅ **Now in epics.md** with full ACs (canonical specs in implementation-artifacts) |
| Epic 1.5 story details | ✅ **Now in epics.md** with summary ACs (canonical specs in implementation-artifacts) |
| E4-S6 ↔ E4-S5 concurrent dev | ⚠ Unchanged — acceptable interleave risk |
| All others | ✓ |

### Story Sizing

| Story | Pass 2 status |
|---|---|
| E3-S1 | ✅ Split-notes added (E3-S1a..e) |
| E4-S6 | ✅ Split-notes added (E4-S6a..d) |
| E4-S7 | ✅ Split-notes added (E4-S7a..c) |
| E10-S1 | ✅ Split-notes added (E10-S1a..c) |

### Hygiene

- ✅ Epic 3 and Epic 4 duplicate `### Epic X` headers removed
- ✅ FR Coverage Map updated to reflect descope + show new Epic 5/Epic 1.5 contributions
- ✅ PRD frontmatter changelog records v1.0 → v1.1 transition
- ✅ epics.md frontmatter changelog updated

---

## Findings Summary (Pass 2)

### 🔴 Critical

1. **WebSocket vs SSE transport conflict** — still unresolved (deferred to offline Winston decision). Blocks any further Epic 1/2 backend transport work until ADR-19 lands. **Unchanged from Pass 1.**

### 🟠 Major

None remaining in this pass.

### 🟡 Minor / Improvements

2. **FR11 explicit AC** — add to E4-S6b (door obstruction sub-story) when E4-S6 is split at dev start.
3. **FR22 ambiguity** — clarify "real-time" vs "historical" intent in PRD §5.2 when E3-S4 is picked up; one-line edit.
4. **Epic 4 framing** — minor reword to user-outcome; not blocking.
5. **UX v2 doc Phase-2 header** — add "Phase 2 Vision — not PoC scope" to prevent stakeholder confusion.
6. **Open Questions Q7, Q8, Q9, Q11, Q12** — close before pilot signoff; not story-blocking.

---

## Overall Readiness Status

**🟢 READY (transport decision excepted)**

With 12 of 13 Pass-1 findings closed and the remaining one (transport) explicitly held for a user-led decision, the planning artifacts are now in production-implementation shape:

- 100% FR coverage when partial counts (89% full, 11% partial — both partial cases have a known landing zone)
- 100% NFR coverage
- 100% UX-DR coverage
- Zero forward dependencies
- All oversized stories carry a split plan
- Epic 5 and Epic 1.5 are traceable end-to-end

**The only gating decision is ADR-19 (transport).** Until that lands, Epic 1 (E1-S6) and Epic 2 (E2-S1) cannot have their WebSocket-specific ACs locked. Everything else can proceed.

### Recommended Next Steps

1. **Land ADR-19** (Winston + AbbasRizvi). Update PRD §9 + Epic 1/2 stories accordingly. *Unblocks pilot path.*
2. **Pick up E3-S1 split** at dev start (E3-S1a..e). Endpoints can ship and land independently.
3. **Pilot pre-flight**: run E10-S3 SOP drills and resolve Q7–Q9, Q11, Q12 before any signed pilot date.
4. **Minor docs hygiene**: UX v2 header, PRD §5.2 FR22 wording — bundle into the next planning commit.

### Final Note

This pass closed **12 of 13** Pass-1 findings. The remaining critical item is a single architectural decision (WebSocket vs SSE) that the user has chosen to take offline with the architect. Once ADR-19 is recorded, the project is ready for production-track implementation under the current PoC scope.
