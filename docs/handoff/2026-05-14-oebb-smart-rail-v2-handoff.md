# OEBB Smart Rail — Developer Handoff Spec v2
**Date:** 2026-05-14  
**Design spec:** `_bmad-output/design-artifacts/D-UX-Design/2026-05-14-oebb-ux-design-v2.md`  
**Polish skill:** `.claude/skills/railway-control-centre-polish/SKILL.md`  
**Mockups:** `mockups/` (v2 files)  
**Tech context:** Web dashboards (React + CSS-in-JS or Tailwind), mobile apps (React Native or PWA), HTML mockups in `mockups/` are the visual reference

---

## Design Tokens

All tokens are defined in `mockups/shared-tokens.css`. Map these to your design system variables.

### Colour tokens

| Token | Value | Usage |
|---|---|---|
| `--bg-base` | `#0A0C10` | Page/app background |
| `--bg-surface` | `#111318` | Cards, panels |
| `--bg-raised` | `#181B22` | Nested content, drill-in panels |
| `--bg-overlay` | `#1E2128` | Modals, popovers, form inputs |
| `--border` | `#2A2D35` | Dividers, card borders |
| `--border-active` | `#3A3F4B` | Focused / selected element borders |
| `--sev-critical` | `#FF3B3B` | Critical severity — fire, fall, door at speed |
| `--sev-high` | `#FF6B00` | High severity — unattended luggage, disruptive passenger |
| `--sev-medium` | `#F5A623` | Medium — overcrowding, HVAC watch |
| `--sev-advisory` | `#4A9EFF` | Advisory / informational, also used for interactive accent |
| `--sev-normal` | `#22C55E` | Normal / all-clear |
| `--sev-neutral` | `#6B7280` | Resolved, inactive, historical |
| `--sev-critical-tint` | `rgba(255,59,59,0.03)` | Card background tint for critical items |
| `--sev-high-tint` | `rgba(255,107,0,0.03)` | Card background tint for high items |
| `--sev-critical-border` | `rgba(255,59,59,0.6)` | Left border on critical cards |
| `--sev-high-border` | `rgba(255,107,0,0.6)` | Left border on high cards |
| `--text-primary` | `#F0F2F5` | Body text, titles |
| `--text-secondary` | `#9BA3AF` | Metadata, subtitles |
| `--text-tertiary` | `#6B7280` | Labels, timestamps, placeholder text |
| `--text-disabled` | `#3A3F4B` | Disabled states |
| `--oebb-red` | `#E2002A` | Brand colour — logo, top-level product label only |
| `--accent` | `#4A9EFF` | Interactive elements — buttons, links, active states |
| `--accent-dim` | `rgba(74,158,255,0.10)` | Selected/hover background for accent elements |
| `--coach-low` | `#22C55E` | Coach bar 0–60% occupied |
| `--coach-mid` | `#F5A623` | Coach bar 61–85% |
| `--coach-high` | `#FF6B00` | Coach bar 86–100% |
| `--coach-critical` | `#FF3B3B` | Coach bar >100% (overboarding) |

### Spacing tokens

| Token | Value | Usage |
|---|---|---|
| `--sp-1` | `4px` | Icon padding, tight inline gaps |
| `--sp-2` | `8px` | Within-card internal spacing |
| `--sp-3` | `12px` | Between card sections |
| `--sp-4` | `16px` | Card padding, between related groups |
| `--sp-6` | `24px` | Between panels |
| `--sp-8` | `32px` | Between major layout sections |

### Typography

Single typeface throughout: **Inter** (fallback: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`).

| Role | Size | Weight | Letter-spacing | Usage |
|---|---|---|---|---|
| KPI number | `32px` | `700` | `-0.5px` | Large dashboard numbers |
| KPI label | `11px` | `500` | `+0.8px` uppercase | Category label above KPI number |
| Card title | `14px` | `600` | `0` | Train card title, panel heading |
| Alert title | `13px` | `600` | `0` | Alert/escalation item title |
| Body | `13px` | `400` | `0` | General body text |
| Metadata | `11px` | `400` | `0` | Sub-detail, coach/location info |
| Micro label | `10px` | `700` | `+0.5px` uppercase | Badge text, pill text, coach labels |
| Timestamp | `10px` | `400` | `0` | Right-aligned timestamps |

### Border radii

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | `4px` | Pills, badges, delta badges |
| `--radius-md` | `6px` | Cards, small panels |
| `--radius-lg` | `10px` | Main panels, modal containers |

### Animations

All defined in `shared-tokens.css`:

| Name | Usage | Duration | Easing |
|---|---|---|---|
| `severity-pulse` | Critical severity dot + card border | `1.2s` | `ease-in-out, infinite` |
| `fire-pulse` | Fire/smoke screen background | `0.8s` | `ease-in-out, infinite` |
| `live-blink` | Live data indicator dot | `1.5s` | `ease-in-out, infinite` |
| `slide-in-top` | New alert arriving in feed | `0.2s` | `ease-out` |

General motion rules:
- Micro interactions (hover, focus colour change): `120ms ease`
- State transitions (card border, status pill): `200ms ease`
- Panel slide-in (drill-in detail): `translateX(32px) → translateX(0)` + opacity, `250ms ease-out`
- Fire/smoke State C: **hard cut — no animation**
- Never animate layout shifts — only `opacity`, `transform`, `color`

---

## Component Specs

### Severity dot

Used on every alert, escalation, and fault item. Always the first visual element.

```
● 8px circle (10px on mobile)
  filled: severity colour
  Critical: animation: severity-pulse 1.2s ease-in-out infinite
  High–Advisory: static
  margin-top: 4px (aligns to first text line)
  flex-shrink: 0
```

**States:** Critical (pulsing), High (static full), Medium (static 85% opacity), Advisory (static 70% opacity), Resolved (neutral, 40%)

---

### Train card (Control Centre fleet list)

See mockup: `mockups/control-centre-v2.html`

**Normal state:**
```
background: --bg-surface
border: 1px solid --border
border-left: 4px solid (severity colour — green/amber/orange/red)
border-radius: --radius-md
padding: 12px 16px
margin-bottom: 8px
cursor: pointer
```

**Hover:** `background: --bg-raised`

**Selected/active:** `background: --bg-overlay`, `border: 1px solid --accent`

**Alert state (critical/high):**
- `border-left-color`: severity colour
- `background`: severity tint (`--sev-critical-tint` or `--sev-high-tint`)
- Card border: `1px solid` at 60% severity colour opacity

**Structure (top to bottom):**
1. Row: `[Train ID + route]` — `[Severity badge]`
2. Mini coach bar (see below)
3. Top alert text — `11px --text-tertiary`
4. *(conditional)* Expected vs actual delta badge — only when actual > reserved + threshold

**Expected vs actual delta badge:**
```
display: inline-flex
font-size: 10px, font-weight: 700
color: --sev-high (#FF6B00) for overboarding warning
color: --sev-critical (#FF3B3B) + critical tint when severely over
background: rgba(255,107,0,0.08)
border: 1px solid rgba(255,107,0,0.3)
border-radius: --radius-sm
padding: 1px 6px
margin-top: 4px
```
Content format: `"63 aboard / 48 reserved · +15 overboard"`

Threshold for showing: configurable, default `+15 passengers over reservation count`. Below threshold = hidden. At or above = shown.

---

### Mini coach bar

Used in train cards (compact) and conductor app occupancy bar (larger on mobile).

```
display: flex
gap: 3px
```

Each coach block:
```
.mini-coach-wrap
  position: relative
  flex: 1

.mini-coach
  width: 100%
  height: 8px (desktop compact) / 20px (desktop detail) / 36px (mobile)
  border-radius: 3px
  background: coach bar colour (see tokens)
```

**Fill colour by occupancy:**
- 0–60%: `--coach-low` (#22C55E)
- 61–85%: `--coach-mid` (#F5A623)
- 86–100%: `--coach-high` (#FF6B00)
- >100%: `--coach-critical` (#FF3B3B) + pulsing border

**Icon overlays** (appear at threshold):
```
.coach-icons
  position: absolute
  bottom: 1px, right: 1px
  font-size: 7px
  display: flex, gap: 1px
```
- Luggage density high: 🧳 `color: --text-secondary`
- Congestion score high: ⬡ `color: --sev-medium`
- Bicycle detected: 🚲 `color: --text-secondary`
- Accessibility flag: ♿ `color: --accent`

Max 4 icons per coach block. Empty state: no icons shown.

---

### Coach drill-in grid (Control Centre)

See mockup: `mockups/control-centre-v2.html` — section below main dashboard.

8-column grid layout:
```
grid-template-columns: 40px 1fr 60px 60px 50px 60px 60px 60px
```

Columns: Coach | Occupancy bar | Actual | Reserved | Delta | Luggage | Congestion | Accessibility

**Row states:**
- Normal: `background: transparent`
- `.high-occ` (86–100%): `background: rgba(255,107,0,0.03)`
- `.overboard` (>100%): `background: rgba(255,59,59,0.04)`

**Delta cell colour:**
- Positive (over reserved): `--sev-high` (#FF6B00) — class `.cgr-delta.pos`
- Severely over: `--sev-critical` (#FF3B3B) — override inline on overboard rows
- Negative (under reserved): `--sev-normal` (#22C55E) — class `.cgr-delta.neg`
- Near zero: `--text-tertiary` — class `.cgr-delta.ok`

**Occupancy bar in grid:**
```
height: 6px
border-radius: 3px
width: proportional to occupancy %
```
Colours: same as coach bar — green/amber/orange/red.

**Empty state (no drill-in selected):** Panel hidden. Appears on train card click.

---

### Escalation item

Used in: Control Centre escalations inbox, Maintenance Dashboard escalations inbox, Conductor App escalations tab.

```
display: flex
gap: 10px
align-items: flex-start
padding: 9px 0
border-bottom: 1px solid #1a1a2e
```

**Severity treatments:**
```css
.esc-item.critical {
  background: --sev-critical-tint;
  border-left: 2px solid --sev-critical-border;
  padding-left: 8px;
  margin-left: -8px;
  animation: slide-in-top 0.2s ease-out; /* on arrival */
}
.esc-item.high {
  background: --sev-high-tint;
  border-left: 2px solid --sev-high-border;
  padding-left: 8px;
  margin-left: -8px;
}
.esc-item.readonly { opacity: 0.45; } /* Cross-party read-only items */
```

**Structure:**
```
[severity dot] [body: title + meta + actions] [timestamp + status pill]
```

**Source badge** (appears before title):
- AI-direct: `background: rgba(74,158,255,0.15)`, `color: --accent`, text "AI"
- Staff-raised: `background: rgba(155,163,175,0.15)`, `color: --text-secondary`, text "Staff"
- `font-size: 9px`, `font-weight: 700`, `border-radius: 3px`, `padding: 1px 5px`, `text-transform: uppercase`

**Status pills:**
```
New:      background rgba(255,59,59,0.15)  color --sev-critical
Ack'd:    background rgba(245,166,35,0.15) color --sev-medium
Resolved: background rgba(34,197,94,0.15)  color --sev-normal
font-size: 9px, font-weight: 700, border-radius: 10px, padding: 1px 6px, uppercase
```

**Action buttons:** Text-only links, `color: --accent`, `font-size: 11px`, `font-weight: 600`, underline. Never button chrome (no border, no background). Read-only items have NO action buttons.

**Acknowledged state:** Item opacity reduces to 70% over 300ms ease.

**Resolved state:** Item opacity 40%, title gets `text-decoration: line-through`.

**New item arriving:** `slide-in-top` animation, 200ms ease-out.

---

### Raise escalation form (Conductor App)

See mockup: `mockups/conductor-app-v2.html` — Section 03, left phone.

Full-screen modal with drag handle. Opens from 3 entry points:
1. Escalations tab → blank form
2. "Escalate" in active alert banner → pre-filled from alert
3. Long-press any alert item → "Escalate this"

**Form fields:**
1. **Category grid** — 2-column grid of tap targets (`min-height: 44px`). Two groups: Operational (→ Claudia) and Technical (→ Roland). Each cell has icon (18px), label (10px 600), route label (9px tertiary). Selected state: `border-color: --accent`, `background: --accent-dim`.
2. **Location** — dropdown, pre-filled from alert context, editable. Input height: 48px.
3. **Severity** — two-button toggle: Urgent (red) / Advisory (blue). Button height: 44px min.
4. **Voice note / text toggle** — voice button: 56×56px circle, `background: --accent`, 🎙️ icon 22px, `box-shadow: 0 0 0 6px rgba(74,158,255,0.15)`. Records up to 60s.
5. **Photo attachment** — optional, icon button.
6. **Routing preview** — read-only card showing destination (Claudia/Roland) + rationale. `background: rgba(74,158,255,0.06)`, `border: 1px solid rgba(74,158,255,0.2)`.
7. **Submit button** — full width, `background: --accent`, 14px 700, `border-radius: 10px`, `height: 50px`.

**AI pre-selection:** When raised from an alert, category auto-selected. Show "AI suggested" label in tertiary text next to selection. Tapping any other category overrides without confirmation.

**Routing logic:** Operational categories → Claudia. Technical categories → Roland. Routing preview updates instantly on category change.

**Success state:** Modal closes, confirmation toast appears: `"Escalated to [Name] · Ref #XXXX"`. Toast duration: 3s. `background: --bg-raised`, `border: 1px solid --sev-normal`, `color: --text-primary`.

**Empty/error states:**
- Category not selected + submit tapped: category section pulses with `--sev-medium` border, error text "Please select a category" at 11px in `--sev-medium`
- No internet: submit shows spinner then "Sending failed — will retry when connected" toast

---

### Coach detail metric tiles (Conductor App)

See mockup: `mockups/conductor-app-v2.html` — coach detail panel.

3-column grid of metric tiles:
```
grid-template-columns: 1fr 1fr 1fr
gap: 6px
```

Each tile:
```
background: --bg-overlay
border-radius: --radius-md
padding: 8px
text-align: center
```

**Tile structure:** label (9px 700 uppercase tertiary) → value (18px 700) → sub-label (10px tertiary)

**Tile value colour states:**
- `.critical` → `--sev-critical` (#FF3B3B)
- `.warning` → `--sev-high` (#FF6B00)
- `.ok` → `--sev-normal` (#22C55E)
- Default → `--text-primary`

**The 6 tiles in order:**
| Tile | Class | Value example | Sub-label |
|---|---|---|---|
| Actual pax | `.critical` when >capacity | `98` | "counted by Hailo" |
| Reserved | `.warning` when overboarded | `50` | "+48 overboard" or "−8 under" |
| Luggage items | default or `.warning` | `7` | "in vestibule" |
| Congestion | default or `.warning` | `74` | "score / 100" |
| Bicycles | `.ok` when 0, `.warning` when >0 | `0` | "detected" |
| Access. flags | default | `1` | "♿ door 1" or "—" |

**Empty state:** Tiles show `—` when data not yet received from train.

**Loading state:** Tile value shows skeleton placeholder (animated shimmer, same dimensions as value text).

---

### Fire/smoke alert (all interfaces)

**In Conductor App alert feed:**
```
.alert-type-fire
  background: rgba(255,59,59,0.08)
  border: 1px solid rgba(255,59,59,0.4)
  border-radius: 8px
  padding: 10px
  animation: severity-pulse 1.2s ease-in-out infinite
```
Title: `color: --sev-critical`, `font-weight: 700`, `font-size: 13px`
Subtitle: `color: --text-secondary` (neutral — not coloured)
Timestamp: "NOW" in `--sev-critical`

**In Control Centre escalations inbox:** Appears as AI-direct escalation at top of inbox with critical dot + left border treatment (same as any critical esc-item).

**In Driver Display — State C:**
Hard cut. No transition. Full-screen takeover:
```
background: --bg-base (#0A0C10)
border: 3px solid --sev-critical
border-radius: --radius-lg
animation on ::before pseudo: fire-pulse 0.8s ease-in-out infinite
```
Content: 🔥 icon (48px) → "SMOKE DETECTED" title (28px 900 uppercase `--sev-critical`) → location detail (14px 700 `--text-primary`) → 3 action panels → clearance note.

Action panel styles:
- Primary: `background: rgba(255,59,59,0.15)`, `border: 1px solid rgba(255,59,59,0.4)`, `color: --sev-critical`
- Secondary: `background: rgba(255,255,255,0.05)`, `border: 1px solid rgba(255,255,255,0.1)`, `color: --text-secondary`

**State C can only be cleared by Control Centre.** Implement a server-side clear signal — the driver display cannot self-clear this state.

---

### New alert types — Bicycle and Vandalism

**Bicycle alert** — Medium severity:
- Severity dot: `--sev-medium` (#F5A623)
- Title: "🚲 Bicycle blocking door — [Coach] [Door]"
- Source: "Luggage/bicycle module"

**Vandalism alert** — High severity:
- Severity dot: `--sev-high` (#FF6B00)
- Title: "🎨 Vandalism detected — [Coach]"
- Source: "Vandalism detection module"

Both follow standard alert item layout. No special card treatment (no left border tint) — severity dot colour is sufficient signal.

---

## Interface-by-Interface Specs

### Interface 5: Control Centre Dashboard

**Layout:** 3-column CSS grid
```
grid-template-columns: 1fr 320px
grid-template-rows: auto auto
gap: 14px
```
KPI strip: `grid-column: 1 / -1`

**KPI strip — 8 cards:**
```
grid-template-columns: repeat(8, 1fr)
gap: 10px
```
Card top border colours:
- Active Trains: `--accent` (blue)
- Avg Occupancy: `--sev-normal` (green)
- Active Incidents: `--sev-critical` (red)
- Overcrowded Coaches: `--sev-medium` (amber)
- Fleet Health: `#a855f7` (purple)
- Congested Coaches: `#0D9488` (teal)
- Luggage Alerts: `--sev-high` (orange)
- Open Escalations: `#F43F5E` (rose)

Sub-line (e.g. "2 critical") only shown when non-zero. Severity dot precedes the count.

**Right column:**
- Escalations inbox — primary, full height
- Live incident feed — secondary, below escalations
- No fleet fault summary in v2 (moved to Maintenance Dashboard)

**Responsive:** 1920×1080 target. Below 1440px: right column narrows to `280px`. Below 1200px: collapse to single column stacked layout. KPI strip wraps to 2 rows at `<1200px`.

**Empty states:**
- No active escalations: "No open escalations" in tertiary text, centered in panel
- No active incidents: "All clear" with `--sev-normal` dot
- Train list empty: "No active trains" skeleton

**Loading state:** Skeleton cards for train list items. KPI values show `—` until first data received. Live indicator dot stops animating and turns neutral.

---

### Interface 1: Conductor App

**Device:** Mobile handheld. Minimum target: 375px wide.

**Bottom nav:** 5 items. Min tap target: `44×44px`. Always labelled (icon + text). Active item: `--accent` colour icon + label.

**Badge spec:**
```
position: absolute, top: -4px, right: -6px
min-width: 14px, height: 14px
font-size: 8px, font-weight: 800
border-radius: 10px
Amber badge (alerts): background #F5A623, color #000
Red badge (escalations): background --sev-critical, color #fff
```

**Active alert banner:** Full width, `min-height: 64px`. Left border: 3px solid severity colour. Pulsing for Critical/High. Long-press (500ms) triggers escalation pre-fill.

**Escalations tab — badge:** Shows count of New (unacknowledged) escalations routed to operator. Clears when all acknowledged.

**Voice note button:** 56×56px circle. `box-shadow: 0 0 0 6px rgba(74,158,255,0.15)`. While recording: border pulses red, shows waveform animation. Tap to stop. Max 60s — shows countdown timer at 10s remaining.

**Push notification format (from Claudia/Roland):**
```
Title: "[Name] [action]" e.g. "Claudia acknowledged"
Body: outcome text e.g. "Medical team alerted at Salzburg Hbf · ETA 4 min"
Badge: clears escalation badge count when tapped
Deep-link: opens to that escalation's detail view
```

**Accessibility (mobile):**
- All interactive elements `min 44×44px`
- Bottom nav always visible (not hidden on scroll)
- Active alert banner not dismissible while alert is live

---

### Interface 6: Maintenance Dashboard (Roland)

**Escalations inbox placement:** First element in right column, before AI-triggered cleaning schedule and depot plan panels.

**Read-only cross-party items:**
- Shown with `opacity: 0.45`
- Section label above: "Operational · Routed to Claudia (read-only)"
- No action buttons
- Purpose: Roland has situational awareness of Claudia's active escalations; he cannot action them

**Resolution flow:**
- Resolve button → opens overlay form: outcome text input (required, 200 char max) + action tag multi-select (Depot notified / Safe to continue / Emergency procedure initiated / other)
- Submit → push notification to Conrad: `"[Roland's name] resolved · [outcome text]"`
- Item transitions to resolved state (opacity 40%, strikethrough, status pill → green "Resolved")

---

### Interface 4: Driver Display

**State C — hard cut rule:** No fade, no transition. When fire/smoke event arrives via server push, the display switches immediately. The driver must not see a smooth fade that could be confused with normal state changes.

**State priority:** State C overrides State A and B completely. No door status, no fault indicator visible during State C.

**Clear condition:** Only clearable by Control Centre operator (Claudia) via server-side signal. Driver display cannot self-clear. Show "Cannot clear from here" if driver attempts interaction.

**Screen states summary:**

| State | Trigger | Layout |
|---|---|---|
| A — Normal | All clear | Door strip (green), minimal |
| B — Active alerts | Door obstruction / fault above threshold / platform flag | Door strip + critical fault + platform advisory |
| C — Fire/Smoke | AI fire detection event | Full-screen red takeover, no other content |

---

## Escalation Routing Logic

```
Category = Operational  →  Claudia (Control Centre)
Category = Technical    →  Roland (Maintenance)

AI-direct alerts (bypass staff):
  - Fall/slip detected (person not moving)
  - Fire/smoke detected        → Claudia + Roland + Driver Display + Conrad simultaneously
  - Door obstruction at speed >0 (CCTV + TCMS confirmed)
  - Train health score < critical threshold

Cross-visibility (read-only):
  - Claudia sees Roland's technical escalations (muted, no actions)
  - Roland sees Claudia's operational escalations (muted, no actions)
```

**Ref number format:** Sequential integer, prefixed (e.g. `#4821`). Persisted server-side, included in all push notifications.

**Status lifecycle:** `New → Acknowledged → Resolved`

| Transition | Triggered by | Side effect |
|---|---|---|
| New → Acknowledged | Claudia/Roland taps "Acknowledge" | Push to Conrad: "[Name] acknowledged" |
| Acknowledged → Resolved | Claudia/Roland submits resolution form | Push to Conrad: "[Name] resolved · [outcome]" |

---

## Edge Cases

### Data gaps
- **Hailo offline for a coach:** Coach tile values show `—`, coach bar shows grey (`--text-disabled`), tooltip/sub-label: "No data"
- **Reservation system offline (VLAN 6 down):** Expected column shows `—`, delta badge hidden, no overboarding alerts generated
- **APC offline (VLAN 8 down):** Actual pax from camera only (lower confidence). Show `~` prefix on count: `~63`

### Long text
- Train IDs: max 8 chars — no truncation needed
- Alert titles: max 60 chars — single line, `text-overflow: ellipsis` beyond
- Escalation form free text: max 200 chars — counter shown at 160 chars remaining
- Resolution outcome text: max 200 chars — same counter behaviour
- Staff name display: max 24 chars — truncate with ellipsis

### Network / connectivity
- Conductor App loses connectivity: banner at top: "Offline — escalations will send when reconnected". Voice note and form data buffered locally. Alert feed shows last-known state with "Last updated Xm ago" label.
- Control Centre data stale (>30s without update): live indicator dot turns `--sev-neutral`, label changes from "LIVE" to "STALE · Xm ago"

### Overloaded states
- More than 10 open escalations in Claudia's inbox: show top 10 by severity, "+ X more" button at bottom
- More than 20 items in incident feed: paginate, show most recent 20, "Load earlier" link
- All 6 coaches overboarding simultaneously: entire train card illuminated critical, moved to absolute top of fleet list regardless of other sort criteria

### Empty states
| Screen | Empty state |
|---|---|
| Control Centre — no escalations | "No open escalations" centered in tertiary text |
| Control Centre — no incidents | "All clear ✓" with `--sev-normal` dot |
| Conductor — no alerts | "No active alerts" with green check |
| Conductor — no escalations | "No open escalations · Tap + to raise one" |
| Coach drill-in — no data | Row values show `—`, bar shows grey |

---

## Accessibility Notes

### Colour + severity
- **Never use colour alone** to communicate severity. Every severity indicator pairs: coloured dot + text description. Screen reader must announce the severity level.
- ARIA role for severity dot: `role="img" aria-label="Critical"` / `"High"` / `"Medium"` / `"Advisory"`

### Focus order (Control Centre)
1. Top nav / header
2. KPI strip (left to right)
3. Fleet train list (top card first)
4. Escalations inbox (top item first)
5. Incident feed

### Focus order (Conductor App)
1. App header
2. Active alert banner (if present)
3. Coach occupancy bar
4. Alert feed items (top to bottom)
5. Bottom nav

### ARIA labels required
| Element | `aria-label` |
|---|---|
| Severity dot | `"Severity: [Critical/High/Medium/Advisory]"` |
| Coach bar coach block | `"Coach [N]: [X]% occupied"` |
| Icon overlay (luggage) | `"High luggage density"` |
| Icon overlay (congestion) | `"High congestion score"` |
| Escalation source badge | `"Raised by [AI system / Staff name]"` |
| Status pill | `"Status: [New/Acknowledged/Resolved]"` |
| Voice note button | `"Record voice note"` (while idle) / `"Stop recording"` (while recording) |
| Live indicator | `"Live data — last updated [X] seconds ago"` |

### Keyboard interactions (Control Centre web)
| Key | Action |
|---|---|
| `Tab` | Move focus through interactive elements |
| `Enter` / `Space` | Activate button / open drill-in |
| `Escape` | Close drill-in panel / close modal |
| `Arrow keys` | Navigate within train list |

### Screen reader announcements
- New escalation arriving: announce `"New [Critical/High] escalation: [title] on [train]"`
- Fire/smoke State C: announce immediately `"Emergency: Smoke detected on [train], Coach [N]"`
- Escalation status change: announce `"Escalation [ref] [acknowledged/resolved] by [name]"`

---

## Implementation Notes

### Data freshness
- Fleet train data: push via WebSocket (not polling). Target: <5s latency from train event to Control Centre display.
- Escalations: push via WebSocket. Optimistic UI: show immediately on submit, mark with "Sending…" indicator, confirm or roll back on server response.
- Coach-level metrics: update every 10–30s. Timestamps shown on drill-in panel.

### Mobile performance
- Coach bar renders as CSS only (no canvas, no SVG) — fast paint on low-end handhelds.
- Icon overlays use emoji — no asset loading required.
- Alert feed is a virtualised list (only visible items rendered) when count exceeds 50.

### Fire/smoke State C — implementation requirement
Server must push a dedicated `fire_smoke_detected` event type that the client handles separately from regular alerts. This event triggers the hard-cut State C transition. Do not re-use the alert feed mechanism for this — it must be deterministic and immediate.

### Escalation persistence
Escalations must persist across app restarts and reconnections. Store locally (IndexedDB on web, AsyncStorage on mobile) and sync on reconnect. A conductor who raised an escalation offline must see it in their list when they come back online, with its latest status from the server.
