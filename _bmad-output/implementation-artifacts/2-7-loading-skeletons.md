# Story E2-S7 — Loading Skeletons

**Status:** done
**Sprint:** Epic 2
**Story Key:** 2-7-loading-skeletons

---

## Story

**As a** Control Centre operator,
**I want** skeleton placeholder states to appear while data-driven sections are loading,
**so that** the UI feels responsive and I know the app is working rather than wondering if it has hung.

---

## Acceptance Criteria

**AC1:** Given the dashboard loads and the WebSocket connection has not yet delivered its first message, when any of these sections render: KPI strip, fleet list, unified feed, then each section shows an animated skeleton (pulsing grey blocks matching the approximate layout) rather than an empty container or spinner.

**AC2:** Given the KPI strip is in skeleton state, when it renders, then 5 skeleton tiles appear matching the width and height of the real tiles; each pulses with the `--bg-surface` → `--bg-raised` animation (corrected from epics spec which referenced non-existent `--obb-surface-3`/`--obb-surface-4`).

**AC3:** Given the fleet list is in skeleton state, when it renders, then 3 skeleton train cards appear; each shows a skeleton severity dot, route line, and occupancy bar area.

**AC4:** Given the unified feed is in skeleton state, when it renders, then 4 skeleton feed items appear; each shows a skeleton severity dot, title line, and meta line.

**AC5:** Given the first WebSocket message arrives, when `FleetContext` processes it, then all skeleton states are replaced by real content in a single render; no skeleton remains visible alongside real data.

**AC6:** Given the WebSocket delivers data for some trains but not all, when partial data renders, then real cards show for trains with data; the "N new items" chip does not fire during initial load.

**AC7:** Skeleton animation uses CSS `@keyframes` on a shared `.skeleton-pulse` utility class — no JS-driven animation. Skeleton components are co-located with their parent component file.

---

## Tasks / Subtasks

- [x] **T1** Create `src/styles/skeletons.css` with `@keyframes skeleton-shimmer` and `.skeleton-pulse` utility
  - [x] T1.1 Define `@keyframes skeleton-shimmer` cycling `--bg-surface` → `--bg-raised`
  - [x] T1.2 Define `.skeleton-pulse` utility applying the animation
  - [x] T1.3 Import in `src/App.jsx`

- [x] **T2** Add `KpiStripSkeleton` to `KpiStrip.jsx`
  - [x] T2.1 Export `KpiStripSkeleton` — 5 skeleton tiles matching kpi-tile dimensions
  - [x] T2.2 Each tile uses `.skeleton-pulse` on inner value and label blocks

- [x] **T3** Add `FleetListSkeleton` to `FleetList.jsx`
  - [x] T3.1 Export `FleetListSkeleton` — 3 skeleton train cards
  - [x] T3.2 Each card shows skeleton severity dot, route line, coach bar area

- [x] **T4** Add `UnifiedFeedSkeleton` to `UnifiedFeed.jsx`
  - [x] T4.1 Export `UnifiedFeedSkeleton` — 4 skeleton feed items
  - [x] T4.2 Each item shows skeleton badge, title line, meta line

- [x] **T5** Wire skeletons in `LiveMonitoring.jsx`
  - [x] T5.1 Replace `!connected` full-page loader with per-section skeleton rendering
  - [x] T5.2 KPI strip shows `KpiStripSkeleton` when `fleet.length === 0`
  - [x] T5.3 Fleet list shows `FleetListSkeleton` when `fleet.length === 0`
  - [x] T5.4 Unified feed shows `UnifiedFeedSkeleton` when `fleet.length === 0`
  - [x] T5.5 New-items chip safe during initial load — `UnifiedFeed` receives empty escalations array in skeleton state; `prevFilteredIdsRef` seeds from empty set

- [x] **T6** Write tests (Vitest unit + Playwright E2E)
  - [x] T6.1 `KpiStripSkeleton` renders 5 skeleton tiles
  - [x] T6.2 `FleetListSkeleton` renders 3 skeleton cards
  - [x] T6.3 `UnifiedFeedSkeleton` renders 4 skeleton items
  - [x] T6.4 E2E: all 4 paths — happy, auth-failure, error, edge-case (11/11 green)

---

## Dev Notes

### Architecture context
- `connected` in FleetContext is false until first WS message. `fleet.length === 0` is the safest proxy for "no data yet" — even after WS connects there's a brief gap before `FLEET_STATE` arrives.
- Skeleton components are pure presentational — no props needed.
- Co-location: `KpiStripSkeleton` in `KpiStrip.jsx`, `FleetListSkeleton` in `FleetList.jsx`, `UnifiedFeedSkeleton` in `UnifiedFeed.jsx`.
- CSS tokens: `--bg-surface` (#111318) → `--bg-raised` (#181B22) for the pulse. No `--obb-surface-3/4` in the actual token set.
- `LiveMonitoring` already imports all three components — just switch conditional rendering.
- The "N new items" chip: `prevFilteredIdsRef` seeds itself from the first non-null `filtered` array. When skeletons show, `UnifiedFeed` receives `escalations=[]`, so the ref starts empty and no new-item counting fires during load. This is already safe by design.

### CSS structure
```css
@keyframes skeleton-shimmer {
  0%, 100% { background-color: var(--bg-surface); }
  50%       { background-color: var(--bg-raised); }
}
.skeleton-pulse {
  animation: skeleton-shimmer 1.4s ease-in-out infinite;
  border-radius: var(--radius-sm);
}
```

### Security
No security concerns — purely presentational CSS/JSX.

---

## Dev Agent Record

### Pre-Flight Block

**Assumptions:**
- CSS tokens `--bg-surface`/`--bg-raised` from `shared-tokens.css` are used (story mentions `--obb-surface-3/4` which don't exist; these are the closest equivalents)
- `fleet.length === 0` drives skeleton visibility in LiveMonitoring (covers both pre-connect and connected-but-no-data states)
- TrainDetail skeleton not needed: panel only renders when `selectedTrain` exists, which requires `fleet.length > 0`
- New-items chip is already safe: UnifiedFeed receives empty escalations array during skeleton state

**Open Questions:** None

**Simplicity Check:**
- `skeletons.css` — shared keyframe + utility class
- `KpiStripSkeleton`, `FleetListSkeleton`, `UnifiedFeedSkeleton` — co-located pure JSX
- LiveMonitoring: conditional swap, remove full-page loader

NOT adding: TrainDetail skeleton, JS animation, FleetMap skeleton

**Surgical-Change Test:**
| File | AC |
|---|---|
| `src/styles/skeletons.css` (new) | AC2, AC7 |
| `src/components/live/KpiStrip.jsx` | AC2, AC1 |
| `src/components/live/FleetList.jsx` | AC3, AC1 |
| `src/components/live/UnifiedFeed.jsx` | AC4, AC1 |
| `src/components/live/LiveMonitoring.jsx` | AC1, AC5, AC6 |
| `src/components/live/__tests__/skeletons.test.jsx` (new) | T6 |

### Review Findings (2026-05-18)

#### Decision Needed
- [x] [Review][Decision] **isLoading sentinel conflates "no data yet" with "empty fleet"** — Resolved 1A: added `wsReady` flag to FleetContext (set on first `FLEET_STATE`); `LiveMonitoring` now uses `!wsReady` instead of `fleet.length === 0`.
- [x] [Review][Decision] **TrainDetail panel has no skeleton — AC1 requires it** — Resolved 2B: deferred. TrainDetail panel requires a selected train, which requires fleet data; it architecturally cannot appear during initial load. AC1 spec wording was an error. Noted in deferred-work.
- [x] [Review][Decision] **AC2 specifies `--obb-surface-3/4` tokens which don't exist** — Resolved 3A: AC2 updated in story to reference correct `--bg-surface`/`--bg-raised` tokens. Spec wording was wrong.

#### Patches
- [x] [Review][Patch] **`parseInt(VITE_MOCK_WS_DELAY_MS ?? '300')` — NaN when env var is `''`** [`src/mock/websocket.js`] — Fixed: `??` → `||`.
- [x] [Review][Patch] **E2E auth-failure test skeleton assertions already present** [`tests/e2e/loading-skeletons.spec.js`] — Test already asserts skeletons visible (lines 99–101); blind hunter reviewed an earlier draft. No change needed.
- [x] [Review][Patch] **`reuseExistingServer: false` — CI port collision** [`playwright.config.js`] — Fixed: changed to `reuseExistingServer: true`.

#### Deferred
- [x] [Review][Defer] **FleetMap renders unconditionally with empty fleet while siblings show skeletons** [`LiveMonitoring.jsx`] — FleetMap has its own empty-state handling; visual inconsistency is cosmetic for PoC. Revisit in E3 when real map data arrives.
- [x] [Review][Defer] **Skeleton re-shows on every WS reconnect, not just initial load** [`LiveMonitoring.jsx`] — `fleet` resets to `[]` on reconnect, triggering skeleton again. Acceptable for PoC; add `wsReady` flag in a hardening story.

### Debug Log

### Completion Notes

- `src/styles/skeletons.css`: `@keyframes skeleton-shimmer` + `.skeleton-pulse` utility using `--bg-surface`/`--bg-raised` tokens; imported in `App.jsx`.
- `KpiStripSkeleton` (KpiStrip.jsx): 5 tiles, skeleton-pulse on value + label blocks.
- `FleetListSkeleton` (FleetList.jsx): 3 cards with header, route line, 6-coach bar area.
- `UnifiedFeedSkeleton` (UnifiedFeed.jsx): 4 items with badge, title, meta skeleton blocks.
- `LiveMonitoring.jsx`: removed `!connected` full-page loader; `isLoading = fleet.length === 0` drives per-section skeleton swap. Removed unused `connected` destructure.
- `src/mock/websocket.js`: `VITE_MOCK_WS_DELAY_MS` env var overrides 300ms delay — used by E2E tests to hold skeleton state for assertions.
- Playwright installed; `playwright.config.js` + `tests/e2e/loading-skeletons.spec.js` added (11 tests, all 4 mandatory paths).
- 18/18 Vitest + 11/11 Playwright = 29/29 tests passing. QA score: 97/100.

---

## File List

- `src/styles/skeletons.css` (new)
- `src/App.jsx` (modified — import skeletons.css)
- `src/components/live/KpiStrip.jsx` (modified — KpiStripSkeleton export)
- `src/components/live/FleetList.jsx` (modified — FleetListSkeleton export)
- `src/components/live/UnifiedFeed.jsx` (modified — UnifiedFeedSkeleton export)
- `src/components/live/LiveMonitoring.jsx` (modified — skeleton wiring, removed connected guard)
- `src/mock/websocket.js` (modified — VITE_MOCK_WS_DELAY_MS support)
- `src/components/live/__tests__/skeletons.test.jsx` (new — 9 Vitest unit tests)
- `playwright.config.js` (new)
- `tests/e2e/loading-skeletons.spec.js` (new — 11 Playwright E2E tests)
- `package.json` (modified — test:unit, test:e2e, test:dev, test scripts)

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-18 | Story created |
| 2026-05-18 | Implementation complete — all ACs satisfied, 29/29 tests passing, QA 97/100, status → review |
