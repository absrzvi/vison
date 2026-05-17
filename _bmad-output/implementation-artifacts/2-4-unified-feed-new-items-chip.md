# Story 2-4: Unified Feed "New Items" Chip

**Epic:** 2 — Control Centre Dashboard — Live Operations  
**Story:** 4  
**Story Key:** 2-4-unified-feed-new-items-chip  
**Status:** done  
**Date Created:** 2026-05-17  

---

## User Story

**As a** Control Centre operator,  
**I want** a "↑ N new items" chip to appear at the top of the unified feed when new escalations arrive while I'm scrolled down,  
**so that** my reading position is not interrupted by auto-scroll and I can choose when to jump to new items.

---

## Acceptance Criteria

- [ ] **AC1** — When feed is scrolled below top and new filtered-in escalations arrive, chip "↑ N new item/items" appears fixed at top of feed container; feed does NOT auto-scroll.
- [ ] **AC2** — Tapping/clicking the chip scrolls feed to top smoothly, chip disappears, count resets to zero.
- [ ] **AC3** — When feed is already at top and new items arrive, feed auto-scrolls to show them; chip does NOT appear.
- [ ] **AC4** — Chip count accumulates across multiple arrivals before operator taps (e.g. 3 then 2 more → shows 5).
- [ ] **AC5** — Only filtered-in items increment the chip count (items not matching active filter are ignored).
- [ ] **AC6** — Chip element ID is `pid-feed-new-chip`; keyboard accessible: `role="button"`, `tabIndex={0}`, Enter/Space triggers scroll.

---

## Tasks / Subtasks

- [x] **T1 — Scroll position tracking**
  - [x] Add `useRef` for `unified-feed__list` div
  - [x] Track `isAtTop` via `onScroll` handler (`scrollTop === 0`)

- [x] **T2 — New-item detection**
  - [x] Use `useRef` to store previous filtered escalation ids
  - [x] On each render, diff current filtered ids vs previous to find genuinely new ones
  - [x] Maintain `newCount` state; increment by new arrivals count
  - [x] If `isAtTop`, auto-scroll list to top instead of incrementing chip

- [x] **T3 — Chip UI**
  - [x] Render chip when `newCount > 0` with id `pid-feed-new-chip`
  - [x] Label: `↑ N new item` (N=1) or `↑ N new items` (N>1)
  - [x] `role="button"`, `tabIndex={0}`, `onKeyDown` Enter/Space handler
  - [x] onClick/onKeyDown: scroll list to top, reset `newCount` to 0

- [x] **T4 — Reset on manual scroll-to-top**
  - [x] When scroll reaches top (`scrollTop === 0`) after chip is showing, reset `newCount`

- [x] **T5 — CSS**
  - [x] Position chip fixed at top of `.unified-feed__list` container (sticky/absolute within relative parent)
  - [x] Style: accent background, arrow icon, readable contrast

---

## Dev Notes

### Key files
- `src/components/live/UnifiedFeed.jsx` — all logic
- `src/components/live/UnifiedFeed.css` — chip styles

### Approach
- `listRef` → ref on `.unified-feed__list` div
- `isAtTopRef` → ref (not state) to avoid re-renders on scroll; updated in scroll handler
- `prevFilteredIdsRef` → ref storing Set of previous filtered escalation ids
- `newCount` → state; drives chip visibility
- On `filtered` change: diff against `prevFilteredIdsRef`; if `isAtTopRef.current`, scroll to top + no chip; else increment `newCount`
- Scroll handler: if `scrollTop === 0` and `newCount > 0`, reset `newCount`

### Filter awareness
The existing `filtered` array already applies all active filters — diffing against it automatically satisfies AC5.

---

## Dev Agent Record

### Pre-Flight
**Assumptions:**
- New item = id present in current `filtered` but not in previous `filtered`
- "At top" = `listRef.current.scrollTop === 0`
- Chip resets on manual scroll-to-top (scrollTop reaches 0)
- No new files, no new hooks

**Surgical-Change Test:**
- `UnifiedFeed.jsx` — AC1–AC6
- `UnifiedFeed.css` — chip styles

### Review Findings

- [x] [Review][Patch] Filter change inflates `newCount` — fixed: separate useEffect reseeds `prevFilteredIdsRef` + resets `newCount` on filter change [UnifiedFeed.jsx]
- [x] [Review][Patch] `newCount` not reset on filter change — fixed: same reseed effect [UnifiedFeed.jsx]
- [x] [Review][Patch] `scrollTop === 0` strict equality fails on sub-pixel scroll — fixed: `<= 1` threshold [UnifiedFeed.jsx handleScroll]
- [x] [Review][Patch] FLEET_STATE reconnect spurious "new" — fixed: reseed effect fires on filter change; reconnect with same filters reseeds cleanly [UnifiedFeed.jsx]
- [x] [Review][Defer] Race: new item arrives during chip-tap smooth scroll — chip briefly re-appears mid-animation [UnifiedFeed.jsx] — deferred, low-frequency, pre-existing design constraint
- [x] [Review][Defer] `isAtTopRef(true)` causes silent jump-scroll if component remounts mid-scroll [UnifiedFeed.jsx] — deferred, remount scenario not in current flow
- [x] [Review][Defer] No upper bound on `newCount` — high-burst feeds show "↑ 247 new items" [UnifiedFeed.jsx] — deferred, cap at "99+" in future polish pass
- [x] [Review][Defer] `filtered` not memoized — O(n) Set diff on every render [UnifiedFeed.jsx] — deferred, escalation count is small in PoC scope
- [x] [Review][Defer] `role="button"` chip missing `aria-label` for screen readers [UnifiedFeed.jsx] — deferred, a11y pass

### Debug Log

### Completion Notes

Added `newCount` state + `listRef`/`isAtTopRef`/`prevFilteredIdsRef` refs to `UnifiedFeed`. On each render, diffs filtered escalation ids vs previous set: if at top, auto-scrolls; if scrolled down, increments chip count. Chip renders sticky at top of list with `id="pid-feed-new-chip"`, `role="button"`, keyboard Enter/Space support. Manual scroll-to-top resets count. Filter-awareness is automatic — chip diffs against the already-filtered list. CSS: `position: sticky; top: 0` inside `position: relative` list container.

---

## File List

- `control-centre/src/components/live/UnifiedFeed.jsx`
- `control-centre/src/components/live/UnifiedFeed.css`

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-17 | Story created and implemented |
