# OEBB Smart Rail — Developer Handoff Spec v3
**Date:** 2026-05-14
**Previous handoff:** `docs/handoff/2026-05-14-oebb-smart-rail-v2-handoff.md`
**Design spec:** `docs/superpowers/specs/2026-05-14-passenger-portal-design.md`
**Mockup:** `mockups/passenger-portal-v1.html`
**Tech context:** CNA portal is a locally-served HTML page from the Nomad Digital R5001C. No framework required — vanilla HTML/CSS/JS. Existing portal uses ÖBB white-background brand style (not the dark staff-interface theme).

---

## What Changed in v3

This handoff adds the **passenger-facing coach guidance panel** to the ÖBB Railnet CNA (Captive Network Assistant) portal. Everything in v2 remains unchanged. v3 is purely additive.

| Component | Status |
|---|---|
| v2 staff interfaces (all 7) | Unchanged — see v2 handoff |
| Passenger persona — Petra (general) | ✅ New — trigger map + 5 use cases |
| Passenger persona — Hanna (accessibility) | ✅ New — trigger map + 5 use cases |
| CNA portal coach guidance panel | ✅ New — UX spec + 8-state mockup |

---

## New Personas

### Persona 9 — Petra (Passenger, General Traveller)
**File:** `_bmad-output/design-artifacts/B-Trigger-Mapping/persona-passenger-general.md`

| Attribute | Detail |
|---|---|
| Device | Smartphone (iOS or Android) |
| Language | German |
| Core tension | 90-second boarding window; wrong coach = standing for 2 hours |
| Primary driving force (15/15) | Know where space is available before committing to a door |
| Entry point | CNA portal auto-opens when phone connects to Railnet WiFi |

**Use cases:** UC-P01 – UC-P05 (see use cases file)

### Persona 10 — Hanna (Passenger, Accessibility Need)
**File:** `_bmad-output/design-artifacts/B-Trigger-Mapping/persona-passenger-accessibility.md`

| Attribute | Detail |
|---|---|
| Device | Smartphone (iOS or Android) |
| Language | German |
| Core tension | PRM space may be occupied; ramp may not be deployed; staff may not know she is coming |
| Primary driving forces (15/15 each) | Confirm accessible space available before walking to that door · Know exact door + ramp status |
| Entry point | CNA portal; Conrad alert fires automatically in background on portal load |

**Use cases:** UC-A01 – UC-A05 (see use cases file)

---

## New Interface: CNA Portal Coach Guidance Panel

**Full UX spec:** `_bmad-output/design-artifacts/E-Passenger-Portal/passenger-portal-ux-design.md`
**Use cases:** `_bmad-output/design-artifacts/E-Passenger-Portal/passenger-portal-use-cases.md`
**Mockup:** `mockups/passenger-portal-v1.html` — 8 interactive states

### Placement
Added **below** the existing entertainment promo, **above** the GDPR/VERBINDEN section. The existing promo, header, and connect flow are **unchanged**.

```
[ÖBB railnet header]          ← unchanged
[Entertainment promo hero]    ← unchanged
[WLAN Verbinden button]       ← unchanged
───────────────────────────── ← red top-border divider
[COACH GUIDANCE PANEL]        ← NEW
───────────────────────────── 
[GDPR / VERBINDEN section]    ← unchanged
```

### Panel anatomy

**Header row:**
```
ZUGAUSLASTUNG  •  Wagen 1–8          🟢 Vor 8 Sek.
```
- Left: `font-size: 11px; font-weight: 700; text-transform: uppercase; color: #6B7280`
- Right: freshness pill — `font-size: 10px; color: #9BA3AF` → `color: #F5A623` when stale (>60s)
- Live dot: `5px` circle, `#22C55E`, `animation: liveblink 1.5s infinite`

**Coach diagram (always shown when data available):**
```
display: flex; gap: 4px;
```
Each coach block:
```
flex: 1
height: 36px
border-radius: 4px
background: occupancy colour (see thresholds)
```
Coach label: `font-size: 10px; font-weight: 700; color: #fff; text-align: center`
Icon overlays (bottom-right, 8px): 🧳 if luggage density high · ♿ if PRM coach

**Occupancy colour thresholds** (consistent with all v2 interfaces):
| Token | Value | Range | German label |
|---|---|---|---|
| `--coach-low` | `#22C55E` | 0–60% | Viel Platz |
| `--coach-mid` | `#F5A623` | 61–85% | Mäßig besetzt |
| `--coach-high` | `#FF6B00` | 86–100% | Stark besetzt |
| `--coach-critical` | `#FF3B3B` | >100% | Überfüllt |

**Guidance instruction box (conditional):**

Shown only when: one coach is >20% less occupied than next-best AND train orientation data is available AND fresh.

```css
/* Recommendation */
background: rgba(34,197,94,0.08);
border: 1px solid rgba(34,197,94,0.3);
border-radius: 8px;
padding: 10px 12px;
```
- Arrow: `font-size: 18px; color: #22C55E` — direction reflects train orientation
- Primary: `"Gehen Sie zu Wagen N"` — `font-size: 15px; font-weight: 700; color: #111318`
- Sub: load word + luggage note — `font-size: 12px; color: #6B7280`

```css
/* Train full warning */
background: rgba(245,166,35,0.08);
border: 1px solid rgba(245,166,35,0.3);
```
- Content: `"Zug stark besetzt"` + `"Wagen N am wenigsten voll"`

**Accessibility panel (conditional):**

Shown when Hailo detects PRM passenger or boarding station has PRM-flagged service.

```css
/* Space available */
background: rgba(74,158,255,0.07);
border: 1px solid rgba(74,158,255,0.3);
border-radius: 8px;
padding: 10px 12px;
```
- Primary: `"Rollstuhlplatz frei"` — `font-size: 14px; font-weight: 700`
- Detail: `"Wagen N · Tür N"` — `font-size: 12px; color: #6B7280`
- Ramp status: `"Rampe wird vorbereitet …"` italic `#9BA3AF` → `"✓ Rampe bereit"` `#22C55E` non-italic when Conrad confirms

```css
/* Space occupied */
background: rgba(245,166,35,0.07);
border: 1px solid rgba(245,166,35,0.3);
```
- Content: `"Rollstuhlplatz belegt"` + `"Bitte Schaffner kontaktieren"`

---

## 8 Portal States

| # | Name | Trigger | Coach diagram | Guidance box | Accessibility panel |
|---|---|---|---|---|---|
| 1 | Gemischte Auslastung | Mixed load, no clear best | ✅ full colour | Hidden | Hidden |
| 2 | Empfehlung | One coach >20% less full | ✅ full colour | ✅ Green + arrow | Hidden |
| 3 | Zug voll | All coaches >85% | ✅ orange/red | ✅ Amber warning | Hidden |
| 4 | Barrierefreiheit frei | PRM space available | ✅ with ♿ overlay | Hidden | ✅ Blue / free |
| 5 | Barrierefreiheit belegt | PRM space taken | ✅ with ♿ overlay | Hidden | ✅ Amber / occupied |
| 6 | Rampe bereit | Conrad confirms ramp | ✅ with ♿ overlay | Hidden | ✅ Updated live |
| 7 | Daten veraltet | >60s since last update | ✅ opacity 0.6 | Hidden (no stale recommendations) | Hidden |
| 8 | Keine Daten | Hailo offline / API error | Hidden | Hidden | "nicht verfügbar" message |

---

## Directional Arrow Logic

Arrow (`→` or `←`) shown only when **all three** conditions are met:
1. One coach is >20% less occupied than the next-best coach
2. `GET /api/v1/train-orientation` returns `"forward"` or `"reverse"` (not `null`) and data is <5 min old
3. The recommended coach is not the coach nearest to the passenger's likely boarding position

If any condition fails: show coach colours only, no arrow. Degrade gracefully.

---

## Auto-refresh Behaviour

- On page load: fetch immediately
- Every 30 seconds: re-fetch and update in place (no full page reload)
- Coach block colour transitions: `200ms ease`
- Freshness pill counts up from "Vor 0 Sek." after each successful fetch
- On fetch failure: increment stale counter; at >60s show stale state (State 7)
- On consecutive failures (>2s timeout × 3): show State 8 (no data)

---

## Conrad Alert (Accessibility — Background, Silent)

**Trigger:** CNA portal loads AND accessibility panel is displayed (PRM data present)
**Action:** `POST /api/v1/accessibility-alert`
**Payload:**
```json
{
  "coach": "2",
  "door": "1",
  "type": "pushchair_wheelchair",
  "portal_opened_at": "ISO8601 timestamp"
}
```
**No UI indication to the passenger** — this fires silently. Hanna should not feel she is "activating" a process.

**Ramp confirmation loop:** When Conrad confirms ramp deployed in conductor app, the portal polls `GET /api/v1/coach-load` which returns updated `ramp_ready: true` on the PRM coach entry. Portal updates accessibility panel live.

---

## API Contracts (new endpoints required)

### GET /api/v1/coach-load
```json
{
  "train_id": "RJ123",
  "updated_at": "2026-05-14T12:14:52Z",
  "coaches": [
    {
      "id": 1,
      "label": "W1",
      "occupancy_pct": 45,
      "luggage_density_high": false,
      "prm": false,
      "prm_space_free": null,
      "prm_door": null,
      "ramp_ready": null
    },
    {
      "id": 2,
      "label": "W2",
      "occupancy_pct": 38,
      "luggage_density_high": false,
      "prm": true,
      "prm_space_free": true,
      "prm_door": 1,
      "ramp_ready": false
    }
  ]
}
```

### GET /api/v1/train-orientation
```json
{
  "direction": "forward",
  "updated_at": "2026-05-14T12:10:00Z"
}
```
`direction`: `"forward"` | `"reverse"` | `null` (unknown)

### POST /api/v1/accessibility-alert
Request:
```json
{
  "coach": "2",
  "door": "1",
  "type": "pushchair_wheelchair",
  "portal_opened_at": "2026-05-14T12:15:03Z"
}
```
Response: `204 No Content`

All endpoints served locally on R5001C. Same VLAN as portal server. No internet dependency.

---

## Portal Typography & Colour

The portal uses ÖBB **white-background** style — not the dark `#0A0C10` theme used in staff interfaces.

| Element | Spec |
|---|---|
| Font | Inter · fallback: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` |
| Panel background | `#FFFFFF` · `border: 1px solid #E5E7EB` · `border-radius: 10px` |
| Panel top accent | `border-top: 3px solid #E2002A` (ÖBB brand red) |
| Section label | `11px 700 uppercase #6B7280` |
| Instruction primary | `15px 700 #111318` |
| Instruction sub | `12px 400 #6B7280` |
| Accessibility primary | `14px 700 #111318` |
| Freshness normal | `10px 400 #9BA3AF` |
| Freshness stale | `10px 400 #F5A623` |
| Guidance arrow | `18px 700 #22C55E` |

---

## Accessibility (WCAG)

- Coach blocks: `aria-label="Wagen N: [Viel Platz / Mäßig besetzt / Stark besetzt / Überfüllt]"`
- Guidance instruction container: `role="status"` — screen readers announce updates
- Accessibility panel: `role="alert"` — announced immediately when space status changes
- Colour never used alone — every state has a text label alongside colour
- No interactive elements in the guidance panel — read-only

---

## DSGVO / Privacy

- No personal data collected or transmitted
- No cookies set by the guidance panel
- No analytics or tracking
- All occupancy processing runs onboard (Hailo-8) — only aggregated counts transmitted
- Raw video never leaves the train
- Portal is stateless — no session, no user identifier

---

## Edge Cases

| Scenario | Behaviour |
|---|---|
| API returns empty coaches array | Show "nicht verfügbar" message (State 8) |
| Train orientation `null` | Show coach colours only, no directional arrow |
| All coaches exactly equal occupancy | No recommendation box — colours only |
| PRM coach exists but `prm_space_free: null` | Show accessibility icon on coach, omit space status text |
| Conrad alert POST fails | Silent failure — log to local error log, do not show error to passenger |
| Portal loads in <1s but API hasn't responded | Show skeleton coach blocks (grey), replace on API response |
| Passenger opens portal mid-journey (after boarding) | Same panel, same states — mid-journey load is still useful for repositioning |

---

## Unchanged from v2

Everything in `docs/handoff/2026-05-14-oebb-smart-rail-v2-handoff.md` remains current:
- All design tokens (`--bg-base`, severity colours, spacing, typography)
- All 7 staff interface specs (Conductor, Technician, Bistro, Driver, Control Centre, Maintenance, Analytics/Station)
- Component specs (severity dot, train card, mini coach bar, escalation item, etc.)
- Escalation routing logic
- Fire/smoke State C rules
- Accessibility notes (staff interfaces)
- Implementation notes (WebSocket, mobile performance, escalation persistence)
