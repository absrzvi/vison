# Passenger Portal — UX Design Spec
**Agent:** Freya (WDS UX Designer)
**Phase:** 4 — UX Design
**Date:** 2026-05-14
**Input:** `B-Trigger-Mapping/persona-passenger-general.md` · `B-Trigger-Mapping/persona-passenger-accessibility.md` · `E-Passenger-Portal/passenger-portal-use-cases.md`
**Mockup:** `mockups/passenger-portal-v1.html`
**Status:** Complete

---

## Overview

The coach guidance panel is a new section added **below the existing entertainment promo** on the ÖBB Railnet CNA (Captive Network Assistant) portal. It appears pre-login, requires no interaction to load, and is served locally from the Nomad Digital R5001C (< 1 second load time).

It surfaces live coach occupancy to two passenger types:
- **Petra** — general traveller seeking a seat, working within a 90-second boarding window
- **Hanna** — accessibility passenger needing confirmed PRM door + ramp status before committing to a platform position

---

## Design Principles (this panel)

1. **3-second rule** — the critical information (which coach to board) must be readable in 3 seconds without scrolling. Petra is moving, not reading.
2. **Honest over optimistic** — if the train is full, say so. A wrong promise destroys trust in the system permanently.
3. **Progressive disclosure** — coach diagram first (scannable), accessibility detail second (only shown when relevant), data freshness last (supporting detail).
4. **German only** — all labels, status words, and instructions in German. No mixed-language content.
5. **Passive by default** — the panel fires Conrad's alert for Hanna automatically. She does not need to tap anything to get assistance.
6. **Consistent with existing system tokens** — uses the same `--coach-low/mid/high/critical` colour tokens and occupancy thresholds as all other interfaces.

---

## Layout: CNA Portal Page (full scroll)

```
┌─────────────────────────────────┐
│  ÖBB railnet logo               │  ← existing header (unchanged)
├─────────────────────────────────┤
│                                 │
│  [Entertainment promo hero]     │  ← existing (unchanged)
│  Wlan Verbinden  [red button]   │
│                                 │
├─────────────────────────────────┤
│  ╔═══════════════════════════╗  │
│  ║  COACH GUIDANCE PANEL    ║  │  ← NEW (below promo)
│  ╚═══════════════════════════╝  │
├─────────────────────────────────┤
│  [VERBINDEN / GDPR section]     │  ← existing (unchanged, below panel)
└─────────────────────────────────┘
```

---

## Coach Guidance Panel — Anatomy

### Panel header
```
Zugauslastung  •  Wagen 1–8        [🕐 Vor 12 Sek.]
```
- Label: "Zugauslastung" (Train occupancy) — 11px, 600 weight, uppercase, `--text-secondary`
- Train coach range: "Wagen 1–8" — 11px, `--text-tertiary`
- Freshness pill: right-aligned, "Vor X Sek." — 10px, `--text-tertiary`. Turns amber if >60s old.

### Coach diagram (always shown)

Horizontal row of coach blocks. Each block:
- Width: equal-flex, gap 4px
- Height: 36px (touch-friendly, readable at a glance)
- Border-radius: 4px
- Fill colour: occupancy threshold (green / amber / orange / red)
- Label: "W1", "W2" … centred, 10px 700 white
- Icon overlays (bottom-right, 8px): 🧳 if luggage density high, ♿ if PRM coach

**Colour thresholds** (consistent with all existing interfaces):
| Fill | Threshold | German label |
|---|---|---|
| `#22C55E` (green) | 0–60% | Viel Platz |
| `#F5A623` (amber) | 61–85% | Mäßig besetzt |
| `#FF6B00` (orange) | 86–100% | Stark besetzt |
| `#FF3B3B` (red) | >100% | Überfüllt |

### Guidance instruction (conditional)

Shown **only when** one coach is >20% less occupied than next-best AND train orientation data is available.

```
┌────────────────────────────────────────┐
│  → Gehen Sie zu Wagen 6               │
│     Viel Platz · Gepäckfach frei      │
└────────────────────────────────────────┘
```
- Container: `background: rgba(34,197,94,0.08)`, `border: 1px solid rgba(34,197,94,0.25)`, `border-radius: 8px`, `padding: 10px 12px`
- Arrow: "→" or "←" — 16px, `--sev-normal` green — direction reflects train orientation
- Primary line: "Gehen Sie zu Wagen N" — 15px, 700, `--text-primary`
- Sub-line: status word + optional luggage note — 12px, `--text-secondary`

When direction data unavailable OR load is evenly distributed: instruction block hidden. Coach diagram colours alone carry the message.

**Full train occupied state** (all coaches >85%):
```
┌────────────────────────────────────────┐
│  ⚠ Zug stark besetzt                  │
│     Wagen 3 am wenigsten voll         │
└────────────────────────────────────────┘
```
- Container: `background: rgba(245,166,35,0.08)`, `border: 1px solid rgba(245,166,35,0.3)`
- Icon: ⚠ in `--sev-medium`
- Sets honest expectation; still directs to least-worst coach

### Accessibility panel (conditional)

Shown **only when** Hailo detects a wheelchair user or pushchair passenger has opened the portal, OR the boarding station has a PRM-flagged service.

**Space available:**
```
┌────────────────────────────────────────┐
│  ♿  Rollstuhlplatz frei               │
│     Wagen 2 · Tür 1                   │
│     Rampe wird vorbereitet …          │
└────────────────────────────────────────┘
```
- Container: `background: rgba(74,158,255,0.08)`, `border: 1px solid rgba(74,158,255,0.25)`, `border-radius: 8px`
- Icon: ♿ 18px, `--accent` blue
- Primary: "Rollstuhlplatz frei" — 14px, 700, `--text-primary`
- Detail: "Wagen N · Tür N" — 12px, `--text-secondary`
- Status: "Rampe wird vorbereitet …" — 12px italic, `--text-tertiary`. Updates to "Rampe bereit ✓" in green when Conrad confirms.

**Space occupied:**
```
┌────────────────────────────────────────┐
│  ♿  Rollstuhlplatz belegt             │
│     Bitte Schaffner kontaktieren      │
└────────────────────────────────────────┘
```
- Container: `background: rgba(245,166,35,0.08)`, `border: 1px solid rgba(245,166,35,0.3)`
- No door or ramp information shown — there is nothing to guide Hanna to
- Directs to find Conrad

**Ramp confirmed state** (live update after Conrad confirms):
```
│  ♿  Rollstuhlplatz frei               │
│     Wagen 2 · Tür 1                   │
│     ✓ Rampe bereit                    │  ← updates live
```
- "Rampe bereit" in `--sev-normal` green, non-italic

---

## States & Variants

### State 1 — Normal (mixed load, no clear best coach)
- Coach diagram shown with green/amber/orange blocks
- No instruction block
- No accessibility panel (if no PRM detection)
- Minimal, glanceable

### State 2 — Clear recommendation (one coach significantly less full)
- Coach diagram shown
- Instruction block shown with directional arrow + coach number
- Sub-line: load status word + luggage note if applicable

### State 3 — Train full (all coaches >85%)
- Coach diagram all orange/red
- Warning block: "Zug stark besetzt — Wagen N am wenigsten voll"
- No arrow (train is full; directing to one coach still helps but no optimism implied)

### State 4 — Accessibility (Hanna, space available)
- Coach diagram shown (PRM coach has ♿ overlay)
- Accessibility panel shown: space free + door + ramp status
- Conrad alert fires in background on page load

### State 5 — Accessibility (Hanna, space occupied)
- Coach diagram shown (PRM coach has ♿ overlay, filled red/orange)
- Accessibility panel shown: occupied state, contact conductor message

### State 6 — Stale data (>60s since last update)
- Freshness pill turns amber: "Daten veraltet"
- Coach diagram shown but slightly desaturated (opacity 0.7)
- No instruction block shown — do not direct passengers on stale data
- Retry indicator: "Wird aktualisiert …" in tertiary text

### State 7 — No data (Hailo offline / no connection to local API)
- Coach diagram hidden entirely
- Message: "Auslastungsdaten nicht verfügbar"
- Panel collapses gracefully — does not break the portal page
- Entertainment promo and VERBINDEN button unaffected

---

## Interaction Model

The panel is **read-only for general passengers**. No taps required.

**Scroll behaviour:** Panel is below the promo. On a standard phone screen (~667px) the top of the panel may be just visible or require a small scroll. The panel must be tall enough to show the coach diagram fully without scrolling within the panel itself.

**Auto-refresh:** Every 30 seconds the panel re-fetches from local API and updates in place. No full page reload. Coach blocks transition colour smoothly (`200ms ease`). Freshness pill updates to "Vor 0 Sek." then counts up.

**Conrad alert (background, no passenger action):** On page load, if Hailo data indicates an accessibility passenger is present, a POST is made to the conductor app notification endpoint. This is silent — no UI indication to the passenger that this has happened. Rationale: Hanna should not feel she is "activating" a process; it should just work.

---

## Typography & Colour (portal context)

The portal uses ÖBB's existing white-background style (not the dark theme used in staff interfaces). The guidance panel adapts:

| Element | Style |
|---|---|
| Panel background | `#FFFFFF` with `border: 1px solid #E5E7EB`, `border-radius: 10px` |
| Panel padding | `16px` |
| Section label | 11px, 600, uppercase, `#6B7280` |
| Coach label (W1…) | 10px, 700, white, centred in block |
| Instruction primary | 15px, 700, `#111318` |
| Instruction sub | 12px, 400, `#6B7280` |
| Accessibility primary | 14px, 700, `#111318` |
| Freshness label | 10px, 400, `#9BA3AF` → `#F5A623` when stale |
| Guidance arrow | 16px, `#22C55E` |

Font: **Inter** (same as all interfaces). Fallback: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`.

---

## Accessibility (WCAG)

- Coach blocks: `aria-label="Wagen N: [Viel Platz / Mäßig besetzt / Stark besetzt / Überfüllt]"`
- Instruction block: `role="status"` so screen readers announce updates
- Accessibility panel: `role="alert"` — announced immediately when space status changes
- Colour never used alone: every state has a text label alongside colour
- Minimum touch target on any interactive element: 44×44px (the VERBINDEN button is the only interactive element in this panel's vicinity)

---

## Technical Integration Notes

| Requirement | Detail |
|---|---|
| Data source | Local REST API on R5001C, same VLAN as portal server |
| Endpoint | `GET /api/v1/coach-load` → JSON: coach array with occupancy %, luggage flag, PRM status |
| Refresh | Client-side `setInterval(30000)` + fetch on page load |
| Conrad alert | `POST /api/v1/accessibility-alert` on page load when PRM data present |
| Train orientation | `GET /api/v1/train-orientation` → `{ direction: "forward" | "reverse" | null }` |
| Load time | All assets served locally; target <800ms total render |
| Fallback | If API returns error or timeout >2s: hide coach diagram, show "nicht verfügbar" message |
| DSGVO | No personal data transmitted; no cookies; no analytics; all processing stays onboard |
