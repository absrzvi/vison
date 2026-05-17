# OEBB UX v2 Mockup Updates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update all 7 HTML mockups to reflect the v2 UX design spec — adding the escalations system, expected vs actual occupancy, luggage/congestion surfacing, three new Tier 1 alert types, and a shared CSS design token file.

**Architecture:** All mockups are self-contained HTML files in `mockups/` with inline CSS. v2 introduces a shared `mockups/shared-tokens.css` file that all mockups link, replacing duplicated colour/type/spacing variables. Each mockup is then updated to add new UI sections without removing existing ones (additive changes only, except where v1 sections are replaced by improved v2 equivalents as called out per task).

**Tech Stack:** HTML5, CSS3 (custom properties, grid, flexbox, CSS animations). No JavaScript frameworks, no build toolchain. All changes are direct file edits.

---

## File Map

| File | Action | What changes |
|---|---|---|
| `mockups/shared-tokens.css` | **Create** | Single source of truth for all CSS custom properties (colours, typography, spacing, animation keyframes) per the polish skill |
| `mockups/conductor-app-v2.html` | **Create** | Adds escalations tab + raise-escalation modal, updates coach detail panel (exp vs actual, luggage, congestion), adds bicycle/fire/vandalism alert types |
| `mockups/control-centre-v2.html` | **Create** | Updates KPI strip (3 new KPIs), adds exp vs actual delta overlays on train cards, adds luggage/congestion icon overlays on coach bar, adds escalations inbox panel, adds coach drill-in grid |
| `mockups/maintenance-dashboard-v2.html` | **Create** | Adds Roland's escalations inbox panel to right column |
| `mockups/driver-display-v2.html` | **Create** | Adds fire/smoke full-screen takeover state (third state alongside existing Normal and Alert states) |
| `mockups/conductor-app-v1.html` | No change | Preserved as-is for reference |
| `mockups/control-centre-v1.html` | No change | Preserved as-is for reference |
| `mockups/maintenance-dashboard-v1.html` | No change | Preserved as-is for reference |
| `mockups/driver-display-v1.html` | No change | Preserved as-is for reference |
| `mockups/bistro-app-v1.html` | No change | No v2 changes required |
| `mockups/technician-app-v1.html` | No change | Minor (escalation entry point) — deferred to v2.1 |
| `mockups/analytics-station-v1.html` | No change | Minor (vandalism log, bicycle trends) — deferred to v2.1 |

---

## Task 1: Create shared CSS token file

**Files:**
- Create: `mockups/shared-tokens.css`

This file defines all CSS custom properties used across all v2 mockups. By linking it from each HTML file, colour, typography, and animation changes can be made in one place.

- [ ] **Step 1: Create the file**

Create `mockups/shared-tokens.css` with this exact content:

```css
/* OEBB Smart Rail — Shared Design Tokens v2
   Link from all v2 mockup HTML files:
   <link rel="stylesheet" href="shared-tokens.css"> */

:root {
  /* ── Backgrounds (elevation layers) ── */
  --bg-base:    #0A0C10;
  --bg-surface: #111318;
  --bg-raised:  #181B22;
  --bg-overlay: #1E2128;

  /* ── Borders ── */
  --border:        #2A2D35;
  --border-active: #3A3F4B;

  /* ── Severity colours ── */
  --sev-critical: #FF3B3B;
  --sev-high:     #FF6B00;
  --sev-medium:   #F5A623;
  --sev-advisory: #4A9EFF;
  --sev-normal:   #22C55E;
  --sev-neutral:  #6B7280;

  /* ── Severity dim backgrounds (3% opacity tint) ── */
  --sev-critical-tint: rgba(255,59,59,0.03);
  --sev-high-tint:     rgba(255,107,0,0.03);

  /* ── Severity border colours (60% opacity) ── */
  --sev-critical-border: rgba(255,59,59,0.6);
  --sev-high-border:     rgba(255,107,0,0.6);

  /* ── Text ── */
  --text-primary:   #F0F2F5;
  --text-secondary: #9BA3AF;
  --text-tertiary:  #6B7280;
  --text-disabled:  #3A3F4B;

  /* ── Brand ── */
  --oebb-red:   #E2002A;
  --accent:     #4A9EFF;
  --accent-dim: rgba(74,158,255,0.10);

  /* ── Coach bar colours ── */
  --coach-low:       #22C55E;
  --coach-mid:       #F5A623;
  --coach-high:      #FF6B00;
  --coach-critical:  #FF3B3B;

  /* ── Typography ── */
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif;

  /* ── Spacing ── */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-6: 24px;
  --sp-8: 32px;

  /* ── Radii ── */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 10px;
}

/* ── Severity pulse animation (Critical only) ── */
@keyframes severity-pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255,59,59,0.4); }
  50%       { opacity: 0.85; box-shadow: 0 0 0 6px rgba(255,59,59,0); }
}

/* ── Fire takeover pulse ── */
@keyframes fire-pulse {
  0%, 100% { background-color: rgba(255,59,59,0.12); }
  50%       { background-color: rgba(255,59,59,0.22); }
}

/* ── Live dot blink ── */
@keyframes live-blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}

/* ── New alert slide-in ── */
@keyframes slide-in-top {
  from { opacity: 0; transform: translateY(-8px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 2: Verify the file is valid CSS**

Open `mockups/shared-tokens.css` in a browser (drag and drop into address bar). It should load without errors (blank page is expected — CSS-only file).

- [ ] **Step 3: Commit**

```bash
git add mockups/shared-tokens.css
git commit -m "feat: add shared CSS design token file for v2 mockups"
```

---

## Task 2: Control Centre v2 — KPI strip + train card updates

**Files:**
- Create: `mockups/control-centre-v2.html` (copy from `mockups/control-centre-v1.html` as starting point)

This task adds the 3 new KPI cards (Congested Coaches, Luggage Alerts, Open Escalations), links the shared token file, and upgrades the train cards with expected vs actual overlay and luggage/congestion icon overlays on the mini coach bar. The escalations inbox panel comes in Task 3.

- [ ] **Step 1: Copy v1 as starting point**

```bash
cp mockups/control-centre-v1.html mockups/control-centre-v2.html
```

- [ ] **Step 2: Link the shared token file**

In `mockups/control-centre-v2.html`, add this line inside `<head>` directly after `<meta charset="UTF-8">`:

```html
<link rel="stylesheet" href="shared-tokens.css">
```

- [ ] **Step 3: Expand the KPI strip from 5 to 8 cards**

Find the `.kpi-strip` CSS rule and update `grid-template-columns`:

Old:
```css
grid-template-columns: repeat(5, 1fr);
```

New:
```css
grid-template-columns: repeat(8, 1fr);
```

- [ ] **Step 4: Add the 3 new KPI card colour classes**

In the `.kpi-card` colour variants CSS block, add after the existing `.purple` variant:

```css
.kpi-card.teal   { border-color: #0D9488; }
.kpi-card.orange { border-color: var(--sev-high, #FF6B00); }
.kpi-card.rose   { border-color: #F43F5E; }
```

- [ ] **Step 5: Add the 3 new KPI cards to the HTML**

Find the KPI strip HTML block (`<div class="kpi-strip">`). After the last existing `kpi-card` (Fleet Health), add:

```html
<div class="kpi-card teal">
  <div class="kpi-label">Congested Coaches</div>
  <div class="kpi-value">4</div>
  <div class="kpi-sub">score &gt;70 threshold</div>
</div>
<div class="kpi-card orange">
  <div class="kpi-label">Luggage Alerts</div>
  <div class="kpi-value">3</div>
  <div class="kpi-sub">high density flagged</div>
</div>
<div class="kpi-card rose">
  <div class="kpi-label">Open Escalations</div>
  <div class="kpi-value">2</div>
  <div class="kpi-sub">1 operational · 1 technical</div>
</div>
```

- [ ] **Step 6: Add CSS for coach bar icon overlays and exp vs actual delta**

Add this CSS block after the existing `.mini-coach` rules:

```css
/* Coach bar icon overlay container */
.mini-coach-wrap {
  position: relative;
  flex: 1;
}
.mini-coach-wrap .mini-coach {
  width: 100%;
}
.coach-icons {
  position: absolute;
  bottom: 1px;
  right: 1px;
  display: flex;
  gap: 1px;
  font-size: 7px;
  line-height: 1;
}
.coach-icon-luggage { color: #9BA3AF; }
.coach-icon-congestion { color: #F5A623; }
.coach-icon-bike { color: #9BA3AF; }
.coach-icon-access { color: #4A9EFF; }

/* Expected vs actual delta badge */
.train-delta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 700;
  color: #FF6B00;
  background: rgba(255,107,0,0.08);
  border: 1px solid rgba(255,107,0,0.3);
  border-radius: 4px;
  padding: 1px 6px;
  margin-top: 4px;
}
.train-delta.overboard { color: #FF3B3B; border-color: rgba(255,59,59,0.4); background: rgba(255,59,59,0.06); }
```

- [ ] **Step 7: Update one train card to show the overboarding delta (ICE 47)**

Find the first `.train-card.alert` in the HTML. After the `.train-meta` div, add:

```html
<div class="train-delta overboard">63 aboard / 48 reserved · +15 overboard</div>
```

And update the mini coach bar for that train to use the new wrapped format with icon overlays:

```html
<div class="mini-coaches">
  <div class="mini-coach-wrap"><div class="mini-coach green"></div></div>
  <div class="mini-coach-wrap"><div class="mini-coach green"></div></div>
  <div class="mini-coach-wrap">
    <div class="mini-coach amber"></div>
    <div class="coach-icons"><span class="coach-icon-luggage">🧳</span></div>
  </div>
  <div class="mini-coach-wrap">
    <div class="mini-coach red"></div>
    <div class="coach-icons"><span class="coach-icon-congestion">⬡</span></div>
  </div>
  <div class="mini-coach-wrap"><div class="mini-coach amber"></div></div>
  <div class="mini-coach-wrap"><div class="mini-coach green"></div></div>
</div>
```

- [ ] **Step 8: Verify visually**

Open `mockups/control-centre-v2.html` in a browser. Confirm:
- 8 KPI cards in the strip (no wrapping)
- ICE 47 train card shows the orange delta badge below the coach bar
- Coach 3 shows luggage icon, Coach 4 shows congestion icon

- [ ] **Step 9: Commit**

```bash
git add mockups/control-centre-v2.html
git commit -m "feat: control centre v2 — KPI strip, train card exp vs actual, coach bar icon overlays"
```

---

## Task 3: Control Centre v2 — Escalations inbox panel

**Files:**
- Modify: `mockups/control-centre-v2.html`

Replaces the existing fleet fault summary panel in the right column with the new escalations inbox. The fault summary moves into a smaller secondary panel below the escalations inbox.

- [ ] **Step 1: Add escalations inbox CSS**

In `mockups/control-centre-v2.html`, add this CSS block after the `.fault-row` rules:

```css
/* ── Escalations inbox ── */
.escalations-panel {
  background: #12122a;
  border-radius: 10px;
  padding: 14px;
}
.esc-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 9px 0;
  border-bottom: 1px solid #1a1a2e;
  animation: slide-in-top 0.2s ease-out;
}
.esc-item:last-child { border-bottom: none; }
.esc-item.critical { background: rgba(255,59,59,0.03); border-left: 2px solid rgba(255,59,59,0.6); padding-left: 8px; margin-left: -8px; }
.esc-item.high     { background: rgba(255,107,0,0.03); border-left: 2px solid rgba(255,107,0,0.6); padding-left: 8px; margin-left: -8px; }
.esc-item.readonly { opacity: 0.45; }

.esc-dot {
  width: 8px; height: 8px; border-radius: 50%;
  margin-top: 4px; flex-shrink: 0;
}
.esc-dot.critical { background: #FF3B3B; animation: severity-pulse 1.2s ease-in-out infinite; }
.esc-dot.high     { background: #FF6B00; }
.esc-dot.advisory { background: #4A9EFF; }

.esc-body { flex: 1; min-width: 0; }
.esc-title { font-size: 12px; font-weight: 600; color: #ddd; }
.esc-meta  { font-size: 11px; color: #555; margin-top: 2px; }
.esc-time  { font-size: 10px; color: #444; white-space: nowrap; }

.esc-source-badge {
  display: inline-block;
  font-size: 9px; font-weight: 700;
  padding: 1px 5px; border-radius: 3px;
  text-transform: uppercase; letter-spacing: 0.05em;
  margin-right: 4px;
}
.esc-source-badge.ai     { background: rgba(74,158,255,0.15); color: #4A9EFF; }
.esc-source-badge.staff  { background: rgba(155,163,175,0.15); color: #9BA3AF; }

.esc-actions { display: flex; gap: 10px; margin-top: 5px; }
.esc-action-btn {
  font-size: 11px; font-weight: 600;
  color: #4A9EFF; background: none; border: none;
  cursor: pointer; padding: 0;
  text-decoration: underline; text-underline-offset: 2px;
}
.esc-status-pill {
  display: inline-block;
  font-size: 9px; font-weight: 700;
  padding: 1px 6px; border-radius: 10px;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.esc-status-pill.new  { background: rgba(255,59,59,0.15); color: #FF3B3B; }
.esc-status-pill.ack  { background: rgba(245,166,35,0.15); color: #F5A623; }
.esc-status-pill.done { background: rgba(34,197,94,0.15);  color: #22C55E; }

.esc-section-label {
  font-size: 10px; font-weight: 700; color: #444;
  text-transform: uppercase; letter-spacing: 1.5px;
  margin: 10px 0 6px;
}
```

- [ ] **Step 2: Replace the right column HTML with the escalations inbox**

Find the `.right-col` div in the HTML. Replace its entire contents with:

```html
<!-- Escalations Inbox -->
<div class="escalations-panel">
  <div class="panel-title">Escalations Inbox</div>

  <!-- AI-direct critical escalation -->
  <div class="esc-item critical">
    <div class="esc-dot critical"></div>
    <div class="esc-body">
      <div class="esc-title">
        <span class="esc-source-badge ai">AI</span>
        Fall detected — passenger not moving
      </div>
      <div class="esc-meta">ICE 47 · Coach 4 · Pose estimation</div>
      <div class="esc-actions">
        <button class="esc-action-btn">Acknowledge</button>
        <button class="esc-action-btn">View detail</button>
      </div>
    </div>
    <div>
      <div class="esc-time">2m ago</div>
      <div class="esc-status-pill new" style="margin-top:4px">New</div>
    </div>
  </div>

  <!-- Staff-raised operational escalation -->
  <div class="esc-item high">
    <div class="esc-dot high"></div>
    <div class="esc-body">
      <div class="esc-title">
        <span class="esc-source-badge staff">Staff</span>
        Disruptive passenger — requesting police
      </div>
      <div class="esc-meta">RJ 789 · Coach 2 · Conrad Müller · Urgent</div>
      <div class="esc-actions">
        <button class="esc-action-btn">Acknowledge</button>
        <button class="esc-action-btn">Resolve</button>
      </div>
    </div>
    <div>
      <div class="esc-time">7m ago</div>
      <div class="esc-status-pill ack" style="margin-top:4px">Ack'd</div>
    </div>
  </div>

  <!-- Read-only technical escalation (Roland's) -->
  <div class="esc-section-label">Technical · Routed to Roland (read-only)</div>
  <div class="esc-item readonly">
    <div class="esc-dot advisory"></div>
    <div class="esc-body">
      <div class="esc-title">
        <span class="esc-source-badge staff">Staff</span>
        Door fault — Coach 3 D2L won't close
      </div>
      <div class="esc-meta">ICE 47 · Coach 3 · Conrad Müller · Advisory</div>
    </div>
    <div>
      <div class="esc-time">14m ago</div>
      <div class="esc-status-pill ack" style="margin-top:4px">Ack'd</div>
    </div>
  </div>
</div>

<!-- Live incident feed (condensed) -->
<div class="incident-feed">
  <div class="panel-title">Live Incident Feed</div>
  <div class="incident-item">
    <div class="inc-dot red" style="animation: severity-pulse 1.2s ease-in-out infinite"></div>
    <div class="inc-body">
      <div class="inc-title">Door obstruction at speed · D2L</div>
      <div class="inc-sub">ICE 47 · Coach 3 · CCTV + TCMS confirmed</div>
    </div>
    <div class="inc-time">1m ago</div>
  </div>
  <div class="incident-item">
    <div class="inc-dot amber"></div>
    <div class="inc-body">
      <div class="inc-title">Unattended luggage · 8m stationary</div>
      <div class="inc-sub">RJ 789 · Coach 5 · Vestibule</div>
    </div>
    <div class="inc-time">3m ago</div>
  </div>
  <div class="incident-item">
    <div class="inc-dot blue"></div>
    <div class="inc-body">
      <div class="inc-title">Wheelchair user detected</div>
      <div class="inc-sub">EC 163 · Coach 1 · Platform staff alerted</div>
    </div>
    <div class="inc-time">9m ago</div>
  </div>
</div>
```

- [ ] **Step 3: Verify visually**

Open `mockups/control-centre-v2.html`. Confirm:
- Escalations inbox shows at top of right column
- Critical AI-direct item has pulsing red dot and left red border tint
- High staff item has orange left border tint
- Roland's read-only technical item is visually muted
- Live incident feed below escalations inbox

- [ ] **Step 4: Commit**

```bash
git add mockups/control-centre-v2.html
git commit -m "feat: control centre v2 — escalations inbox panel"
```

---

## Task 4: Control Centre v2 — Coach drill-in detail grid

**Files:**
- Modify: `mockups/control-centre-v2.html`

Adds a coach detail grid section below the fleet list — shows when an operator clicks a train card. Shows all metrics per coach in one scannable table: actual pax, expected (reservation), delta, luggage count, congestion score, accessibility flags.

- [ ] **Step 1: Add coach drill-in CSS**

In `mockups/control-centre-v2.html`, add this block after the escalation CSS:

```css
/* ── Coach drill-in detail grid ── */
.coach-drilldown {
  background: #12122a;
  border-radius: 10px;
  padding: 14px;
  margin-top: 14px;
}
.coach-grid-header {
  display: grid;
  grid-template-columns: 40px 1fr 60px 60px 50px 60px 60px 60px;
  gap: 6px;
  font-size: 9px; font-weight: 700;
  color: #555; text-transform: uppercase; letter-spacing: 1px;
  padding: 0 4px 8px;
  border-bottom: 1px solid #1a1a2e;
}
.coach-grid-row {
  display: grid;
  grid-template-columns: 40px 1fr 60px 60px 50px 60px 60px 60px;
  gap: 6px;
  align-items: center;
  font-size: 11px;
  padding: 7px 4px;
  border-bottom: 1px solid #1a1a2e;
}
.coach-grid-row:last-child { border-bottom: none; }
.coach-grid-row.overboard { background: rgba(255,59,59,0.04); }
.coach-grid-row.high-occ  { background: rgba(255,107,0,0.03); }

.cgr-coach { font-weight: 700; color: #fff; }
.cgr-bar   { height: 6px; border-radius: 3px; }
.cgr-bar.green  { background: #22C55E; }
.cgr-bar.amber  { background: #F5A623; }
.cgr-bar.orange { background: #FF6B00; }
.cgr-bar.red    { background: #FF3B3B; }

.cgr-actual   { color: #F0F2F5; font-weight: 600; }
.cgr-expected { color: #6B7280; }
.cgr-delta    { font-weight: 700; }
.cgr-delta.pos { color: #FF6B00; }
.cgr-delta.neg { color: #22C55E; }
.cgr-delta.ok  { color: #6B7280; }
.cgr-luggage   { color: #9BA3AF; }
.cgr-cong      { color: #F5A623; }
.cgr-access    { color: #4A9EFF; }
```

- [ ] **Step 2: Add the coach drill-in HTML**

After the closing `</div>` of the `.fleet-panel`, add this new section:

```html
<!-- Coach drill-in — appears when a train card is clicked -->
<div class="coach-drilldown">
  <div class="panel-title">ICE 47 · Wien Hbf → Salzburg · Coach Detail</div>
  <div style="font-size:11px;color:#555;margin-bottom:12px;">
    Tap a coach row to see camera feed. Showing: actual pax vs reservation · luggage · congestion · accessibility
  </div>

  <div class="coach-grid-header">
    <div>Coach</div>
    <div>Occupancy</div>
    <div>Actual</div>
    <div>Reserved</div>
    <div>Delta</div>
    <div>Luggage</div>
    <div>Cong.</div>
    <div>Access.</div>
  </div>

  <div class="coach-grid-row">
    <div class="cgr-coach">C1</div>
    <div><div class="cgr-bar green" style="width:45%"></div></div>
    <div class="cgr-actual">42</div>
    <div class="cgr-expected">50</div>
    <div class="cgr-delta neg">−8</div>
    <div class="cgr-luggage">3</div>
    <div class="cgr-cong">28</div>
    <div class="cgr-access">—</div>
  </div>

  <div class="coach-grid-row">
    <div class="cgr-coach">C2</div>
    <div><div class="cgr-bar green" style="width:52%"></div></div>
    <div class="cgr-actual">49</div>
    <div class="cgr-expected">50</div>
    <div class="cgr-delta ok">−1</div>
    <div class="cgr-luggage">5</div>
    <div class="cgr-cong">35</div>
    <div class="cgr-access">—</div>
  </div>

  <div class="coach-grid-row high-occ">
    <div class="cgr-coach">C3</div>
    <div><div class="cgr-bar amber" style="width:78%"></div></div>
    <div class="cgr-actual">73</div>
    <div class="cgr-expected">48</div>
    <div class="cgr-delta pos">+25</div>
    <div class="cgr-luggage" style="color:#FF6B00;font-weight:700">12 ⚠</div>
    <div class="cgr-cong" style="color:#FF6B00;font-weight:700">74</div>
    <div class="cgr-access">—</div>
  </div>

  <div class="coach-grid-row overboard">
    <div class="cgr-coach">C4</div>
    <div><div class="cgr-bar red" style="width:100%"></div></div>
    <div class="cgr-actual" style="color:#FF3B3B">98</div>
    <div class="cgr-expected">50</div>
    <div class="cgr-delta pos" style="color:#FF3B3B">+48</div>
    <div class="cgr-luggage">7</div>
    <div class="cgr-cong" style="color:#F5A623">68</div>
    <div class="cgr-access" style="color:#4A9EFF">♿ C4-D1</div>
  </div>

  <div class="coach-grid-row">
    <div class="cgr-coach">C5</div>
    <div><div class="cgr-bar amber" style="width:66%"></div></div>
    <div class="cgr-actual">62</div>
    <div class="cgr-expected">50</div>
    <div class="cgr-delta pos">+12</div>
    <div class="cgr-luggage">4</div>
    <div class="cgr-cong">41</div>
    <div class="cgr-access">—</div>
  </div>

  <div class="coach-grid-row">
    <div class="cgr-coach">C6</div>
    <div><div class="cgr-bar green" style="width:38%"></div></div>
    <div class="cgr-actual">36</div>
    <div class="cgr-expected">50</div>
    <div class="cgr-delta neg">−14</div>
    <div class="cgr-luggage">2</div>
    <div class="cgr-cong">22</div>
    <div class="cgr-access">—</div>
  </div>
</div>
```

- [ ] **Step 3: Verify visually**

Open `mockups/control-centre-v2.html`. Confirm:
- Coach drill-in grid appears below the fleet list
- C3 and C4 rows are highlighted (amber/red tint)
- C4 actual count and delta show in red
- C4 accessibility column shows the wheelchair flag in blue
- C3 luggage count shows warning style

- [ ] **Step 4: Commit**

```bash
git add mockups/control-centre-v2.html
git commit -m "feat: control centre v2 — coach drill-in detail grid"
```

---

## Task 5: Conductor App v2 — Escalations tab and raise-escalation modal

**Files:**
- Create: `mockups/conductor-app-v2.html` (copy from `mockups/conductor-app-v1.html`)

Adds the Escalations tab to bottom nav, the raise-escalation modal (shown as a static state), and the escalations list view.

- [ ] **Step 1: Copy v1 as starting point**

```bash
cp mockups/conductor-app-v1.html mockups/conductor-app-v2.html
```

- [ ] **Step 2: Link shared tokens**

In `mockups/conductor-app-v2.html`, add inside `<head>`:

```html
<link rel="stylesheet" href="shared-tokens.css">
```

- [ ] **Step 3: Update bottom nav — add Escalations tab**

Find the bottom nav HTML. It currently has 5 items (Home · Train · Alerts · Diagnostics · Chat). Replace the nav with:

```html
<div class="phone-nav">
  <div class="nav-item">
    <div class="nav-icon">⌂</div>
    <div class="nav-label">Home</div>
  </div>
  <div class="nav-item">
    <div class="nav-icon">🚂</div>
    <div class="nav-label">Train</div>
  </div>
  <div class="nav-item">
    <div class="nav-icon nav-badge-wrap">
      🔔
      <span class="nav-badge">3</span>
    </div>
    <div class="nav-label">Alerts</div>
  </div>
  <div class="nav-item active">
    <div class="nav-icon nav-badge-wrap">
      ⚡
      <span class="nav-badge nav-badge-red">1</span>
    </div>
    <div class="nav-label">Escalate</div>
  </div>
  <div class="nav-item">
    <div class="nav-icon">💬</div>
    <div class="nav-label">Chat</div>
  </div>
</div>
```

- [ ] **Step 4: Add nav badge CSS**

Add these CSS rules after the existing `.phone-nav` styles:

```css
.nav-badge-wrap { position: relative; display: inline-block; }
.nav-badge {
  position: absolute;
  top: -4px; right: -6px;
  min-width: 14px; height: 14px;
  background: #F5A623;
  color: #000;
  font-size: 8px; font-weight: 800;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  padding: 0 3px;
}
.nav-badge.nav-badge-red { background: #FF3B3B; color: #fff; }
```

- [ ] **Step 5: Add escalations modal CSS**

Add this CSS block in the `<style>` section:

```css
/* ── Escalations raise modal ── */
.esc-modal {
  background: var(--surface-2, #191E28);
  border-radius: 16px 16px 0 0;
  padding: 16px 14px 24px;
  margin-top: 8px;
}
.esc-modal-handle {
  width: 32px; height: 4px;
  background: #3A3F4B;
  border-radius: 2px;
  margin: 0 auto 16px;
}
.esc-modal-title {
  font-size: 15px; font-weight: 700;
  color: var(--text-primary, #F0F2F5);
  margin-bottom: 4px;
}
.esc-modal-sub {
  font-size: 11px; color: var(--text-tertiary, #6B7280);
  margin-bottom: 16px;
}
.esc-category-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
}
.esc-cat-section {
  font-size: 9px; font-weight: 700;
  color: var(--text-tertiary, #6B7280);
  text-transform: uppercase; letter-spacing: 1px;
  margin-bottom: 6px;
  grid-column: 1 / -1;
}
.esc-cat-btn {
  background: #1E2128;
  border: 1px solid #2A2D35;
  border-radius: 8px;
  padding: 10px 8px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.esc-cat-btn:hover, .esc-cat-btn.selected {
  border-color: #4A9EFF;
  background: rgba(74,158,255,0.08);
}
.esc-cat-btn .cat-icon { font-size: 18px; margin-bottom: 4px; }
.esc-cat-btn .cat-label { font-size: 10px; font-weight: 600; color: #F0F2F5; }
.esc-cat-btn .cat-route { font-size: 9px; color: #6B7280; margin-top: 2px; }

.esc-form-row { margin-bottom: 12px; }
.esc-form-label {
  font-size: 10px; font-weight: 700;
  color: #6B7280; text-transform: uppercase; letter-spacing: 0.8px;
  margin-bottom: 5px;
}
.esc-form-input {
  width: 100%;
  background: #1E2128;
  border: 1px solid #2A2D35;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px; color: #F0F2F5;
  font-family: inherit;
}
.esc-severity-row {
  display: flex; gap: 8px;
}
.esc-sev-btn {
  flex: 1;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid #2A2D35;
  background: #1E2128;
  font-size: 11px; font-weight: 700;
  text-align: center; cursor: pointer;
}
.esc-sev-btn.urgent.selected   { border-color: #FF3B3B; background: rgba(255,59,59,0.08); color: #FF3B3B; }
.esc-sev-btn.advisory.selected { border-color: #4A9EFF; background: rgba(74,158,255,0.08); color: #4A9EFF; }

.esc-voice-btn {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: #4A9EFF;
  border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  margin: 0 auto 16px;
  box-shadow: 0 0 0 6px rgba(74,158,255,0.15);
}
.esc-routing-preview {
  background: rgba(74,158,255,0.06);
  border: 1px solid rgba(74,158,255,0.2);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 11px; color: #9BA3AF;
  margin-bottom: 14px;
}
.esc-routing-preview strong { color: #4A9EFF; }
.esc-submit-btn {
  width: 100%;
  background: #4A9EFF;
  border: none; border-radius: 10px;
  padding: 14px;
  font-size: 14px; font-weight: 700; color: #fff;
  cursor: pointer;
}
```

- [ ] **Step 6: Add escalation modal screen as a new phone mockup state**

Find the section divider after the Home screen mockup (or after the last coach detail panel). Add a new section showing the Escalation form state. Add a new `section-divider` and `screens-row` block:

```html
<div class="section-divider">
  <div class="section-divider-line"></div>
  <div class="section-divider-pill">03 — Escalate Screen</div>
  <div class="section-divider-num">3</div>
  <div class="section-divider-line"></div>
</div>

<div class="screens-row">
  <div class="screen-col">
    <div class="screen-label">Raise Escalation — Form</div>
    <div class="phone-wrap">
      <div class="phone">
        <!-- App header -->
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px 12px;border-bottom:1px solid #2A2D35">
          <div style="font-size:11px;color:#6B7280">← Back</div>
          <div style="font-size:13px;font-weight:700;color:#F0F2F5">Raise Escalation</div>
          <div style="width:32px"></div>
        </div>

        <div style="overflow-y:auto;padding:12px">
          <!-- Category selector -->
          <div class="esc-form-label">Category</div>
          <div class="esc-category-grid">
            <div class="esc-cat-section">Operational → Claudia</div>
            <div class="esc-cat-btn selected">
              <div class="cat-icon">🚨</div>
              <div class="cat-label">Medical emergency</div>
              <div class="cat-route">→ Claudia</div>
            </div>
            <div class="esc-cat-btn">
              <div class="cat-icon">⚠️</div>
              <div class="cat-label">Disruptive passenger</div>
              <div class="cat-route">→ Claudia</div>
            </div>
            <div class="esc-cat-btn">
              <div class="cat-icon">👥</div>
              <div class="cat-label">Overcrowding</div>
              <div class="cat-route">→ Claudia</div>
            </div>
            <div class="esc-cat-btn">
              <div class="cat-icon">♿</div>
              <div class="cat-label">Accessibility assist</div>
              <div class="cat-route">→ Claudia</div>
            </div>

            <div class="esc-cat-section">Technical → Roland</div>
            <div class="esc-cat-btn">
              <div class="cat-icon">🚪</div>
              <div class="cat-label">Door fault</div>
              <div class="cat-route">→ Roland</div>
            </div>
            <div class="esc-cat-btn">
              <div class="cat-icon">🌡️</div>
              <div class="cat-label">HVAC / temperature</div>
              <div class="cat-route">→ Roland</div>
            </div>
          </div>

          <!-- Location -->
          <div class="esc-form-row">
            <div class="esc-form-label">Location</div>
            <div class="esc-form-input" style="display:flex;justify-content:space-between;align-items:center">
              <span>Coach 4</span>
              <span style="color:#6B7280">▾</span>
            </div>
          </div>

          <!-- Severity -->
          <div class="esc-form-row">
            <div class="esc-form-label">Severity</div>
            <div class="esc-severity-row">
              <div class="esc-sev-btn urgent selected">🔴 Urgent</div>
              <div class="esc-sev-btn advisory">🔵 Advisory</div>
            </div>
          </div>

          <!-- Voice note -->
          <div class="esc-form-label" style="text-align:center;margin-bottom:10px">Add voice note or text</div>
          <div class="esc-voice-btn">🎙️</div>

          <!-- Routing preview -->
          <div class="esc-routing-preview">
            This escalation will go to <strong>Claudia — Vienna Control</strong><br>
            <span style="font-size:10px;color:#555">Medical emergencies route to Control Centre for emergency services coordination</span>
          </div>

          <!-- Submit -->
          <button class="esc-submit-btn">Submit Escalation</button>
        </div>
      </div>
    </div>
  </div>

  <div class="screen-col">
    <div class="screen-label">Escalations Tab — My Open Items</div>
    <div class="phone-wrap">
      <div class="phone">
        <div style="padding:10px 12px;border-bottom:1px solid #2A2D35">
          <div style="font-size:14px;font-weight:700;color:#F0F2F5">My Escalations</div>
          <div style="font-size:11px;color:#6B7280">2 open · 1 resolved</div>
        </div>
        <div style="padding:12px">

          <!-- Open escalation 1 -->
          <div style="background:#1E2128;border-radius:10px;padding:12px;margin-bottom:10px;border-left:3px solid #FF3B3B">
            <div style="display:flex;justify-content:space-between;align-items:flex-start">
              <div>
                <div style="font-size:12px;font-weight:700;color:#F0F2F5">Medical emergency</div>
                <div style="font-size:11px;color:#6B7280;margin-top:2px">Coach 4 · Urgent · Claudia</div>
              </div>
              <div class="esc-status-pill ack">Ack'd</div>
            </div>
            <div style="margin-top:8px;padding:8px;background:#111318;border-radius:6px;font-size:11px;color:#9BA3AF">
              💬 <em>"Claudia acknowledged · Medical team alerted at Salzburg Hbf · ETA 4 min"</em>
            </div>
            <div style="font-size:10px;color:#444;margin-top:6px">Raised 7m ago · Ref #4821</div>
          </div>

          <!-- Open escalation 2 -->
          <div style="background:#1E2128;border-radius:10px;padding:12px;margin-bottom:10px;border-left:3px solid #F5A623">
            <div style="display:flex;justify-content:space-between;align-items:flex-start">
              <div>
                <div style="font-size:12px;font-weight:700;color:#F0F2F5">Overcrowding — Coach 3</div>
                <div style="font-size:11px;color:#6B7280;margin-top:2px">Coach 3 · Advisory · Claudia</div>
              </div>
              <div class="esc-status-pill new">New</div>
            </div>
            <div style="font-size:10px;color:#444;margin-top:8px">Raised 2m ago · Ref #4822 · Awaiting acknowledgement</div>
          </div>

          <!-- Resolved escalation -->
          <div style="background:#1E2128;border-radius:10px;padding:12px;opacity:0.5">
            <div style="display:flex;justify-content:space-between;align-items:flex-start">
              <div>
                <div style="font-size:12px;font-weight:600;color:#9BA3AF;text-decoration:line-through">Door fault — Coach 2</div>
                <div style="font-size:11px;color:#555;margin-top:2px">Roland · Technical</div>
              </div>
              <div class="esc-status-pill done">Resolved</div>
            </div>
            <div style="margin-top:6px;font-size:11px;color:#555">Roland: Door sensor reset remotely, safe to continue</div>
          </div>

        </div>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 7: Verify visually**

Open `mockups/conductor-app-v2.html`. Confirm:
- New section 03 shows two phone screens side by side
- Left screen: escalation form with category grid (Claudia/Roland columns), severity selector, voice note button, routing preview, submit button
- Right screen: escalations tab showing 2 open + 1 resolved, with Claudia's acknowledgement message shown on the first item
- Bottom nav has Escalate tab with red badge

- [ ] **Step 8: Commit**

```bash
git add mockups/conductor-app-v2.html
git commit -m "feat: conductor app v2 — escalations tab and raise-escalation form"
```

---

## Task 6: Conductor App v2 — Coach detail panel update + new alert types

**Files:**
- Modify: `mockups/conductor-app-v2.html`

Updates the coach detail panel to show expected vs actual, luggage count, and congestion score. Adds bicycle, fire/smoke, and vandalism alert types to the unified alert feed.

- [ ] **Step 1: Add coach detail CSS additions**

In `mockups/conductor-app-v2.html`, add after the escalation CSS:

```css
/* ── Coach detail panel v2 ── */
.coach-detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
  margin-top: 8px;
}
.coach-metric {
  background: #1E2128;
  border-radius: 6px;
  padding: 8px;
  text-align: center;
}
.coach-metric-label {
  font-size: 9px; font-weight: 700;
  color: #6B7280; text-transform: uppercase;
  letter-spacing: 0.8px; margin-bottom: 3px;
}
.coach-metric-value {
  font-size: 18px; font-weight: 700; color: #F0F2F5;
}
.coach-metric-sub { font-size: 10px; color: #6B7280; }
.coach-metric.warning .coach-metric-value { color: #FF6B00; }
.coach-metric.critical .coach-metric-value { color: #FF3B3B; }
.coach-metric.ok .coach-metric-value { color: #22C55E; }

/* ── New alert type styles ── */
.alert-type-fire {
  background: rgba(255,59,59,0.08);
  border: 1px solid rgba(255,59,59,0.4);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  animation: severity-pulse 1.2s ease-in-out infinite;
}
.alert-type-fire .alert-title { color: #FF3B3B; font-weight: 700; font-size: 13px; }
```

- [ ] **Step 2: Find the existing coach detail panel and add the metric grid**

Find the coach detail expand panel in the conductor app HTML (the section that shows after tapping a coach in the occupancy bar). After the existing passenger count and accessibility flags, add:

```html
<div class="coach-detail-grid">
  <div class="coach-metric critical">
    <div class="coach-metric-label">Actual pax</div>
    <div class="coach-metric-value">98</div>
    <div class="coach-metric-sub">counted by Hailo</div>
  </div>
  <div class="coach-metric warning">
    <div class="coach-metric-label">Reserved</div>
    <div class="coach-metric-value">50</div>
    <div class="coach-metric-sub">+48 overboard</div>
  </div>
  <div class="coach-metric">
    <div class="coach-metric-label">Luggage items</div>
    <div class="coach-metric-value">7</div>
    <div class="coach-metric-sub">in vestibule</div>
  </div>
  <div class="coach-metric warning">
    <div class="coach-metric-label">Congestion</div>
    <div class="coach-metric-value">74</div>
    <div class="coach-metric-sub">score / 100</div>
  </div>
  <div class="coach-metric ok">
    <div class="coach-metric-label">Bicycles</div>
    <div class="coach-metric-value">0</div>
    <div class="coach-metric-sub">detected</div>
  </div>
  <div class="coach-metric">
    <div class="coach-metric-label">Access. flags</div>
    <div class="coach-metric-value">1</div>
    <div class="coach-metric-sub">♿ door 1</div>
  </div>
</div>
```

- [ ] **Step 3: Add new alert types to the unified alert feed**

In the unified alert feed HTML section, add these three new alert items (insert at top of the feed, above existing alerts):

```html
<!-- Fire/smoke — critical, always at top -->
<div class="alert-type-fire">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <div class="alert-title">🔥 Smoke detected — Coach 5</div>
      <div style="font-size:11px;color:#FF6B00;margin-top:3px">All parties alerted · Emergency protocol active</div>
    </div>
    <div style="font-size:10px;color:#FF3B3B;white-space:nowrap">NOW</div>
  </div>
</div>

<!-- Bicycle hazard — medium severity -->
<div style="display:flex;gap:8px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #2A2D35">
  <div style="width:8px;height:8px;border-radius:50%;background:#F5A623;margin-top:4px;flex-shrink:0"></div>
  <div style="flex:1">
    <div style="font-size:12px;font-weight:600;color:#F0F2F5">🚲 Bicycle blocking door — Coach 3 D2L</div>
    <div style="font-size:11px;color:#6B7280;margin-top:2px">Coach 3 · Vestibule · Luggage/bicycle module</div>
  </div>
  <div style="font-size:10px;color:#6B7280;white-space:nowrap">1m ago</div>
</div>

<!-- Vandalism — high severity -->
<div style="display:flex;gap:8px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #2A2D35">
  <div style="width:8px;height:8px;border-radius:50%;background:#FF6B00;margin-top:4px;flex-shrink:0"></div>
  <div style="flex:1">
    <div style="font-size:12px;font-weight:600;color:#F0F2F5">🎨 Vandalism detected — Coach 6</div>
    <div style="font-size:11px;color:#6B7280;margin-top:2px">Coach 6 · Window area · Vandalism detection module</div>
  </div>
  <div style="font-size:10px;color:#6B7280;white-space:nowrap">3m ago</div>
</div>
```

- [ ] **Step 4: Verify visually**

Open `mockups/conductor-app-v2.html`. Confirm:
- Coach detail panel shows 6 metric tiles (actual, reserved, luggage, congestion, bicycles, accessibility)
- Actual pax and congestion tiles show in warning/critical colours
- Fire alert shows at top of alert feed with pulsing red background
- Bicycle and vandalism alerts appear in the feed with appropriate severity dots

- [ ] **Step 5: Commit**

```bash
git add mockups/conductor-app-v2.html
git commit -m "feat: conductor app v2 — coach detail metrics, bicycle/fire/vandalism alerts"
```

---

## Task 7: Maintenance Dashboard v2 — Roland's escalations inbox

**Files:**
- Create: `mockups/maintenance-dashboard-v2.html` (copy from `mockups/maintenance-dashboard-v1.html`)

Adds the escalations inbox to Roland's right column. Uses the same CSS patterns as the Control Centre escalations inbox.

- [ ] **Step 1: Copy v1 as starting point**

```bash
cp mockups/maintenance-dashboard-v1.html mockups/maintenance-dashboard-v2.html
```

- [ ] **Step 2: Link shared tokens**

In `<head>`:

```html
<link rel="stylesheet" href="shared-tokens.css">
```

- [ ] **Step 3: Add escalation CSS (same as Task 3 Step 1)**

Copy the full `/* ── Escalations inbox ── */` CSS block from `control-centre-v2.html` into the `<style>` section of `maintenance-dashboard-v2.html`. (Copy verbatim — no changes needed.)

- [ ] **Step 4: Add Roland's escalations inbox to the right column**

Find the right column in `maintenance-dashboard-v2.html`. Add the escalations panel as the first element in that column, before the existing cleaning schedule panel:

```html
<!-- Roland's Escalations Inbox -->
<div class="escalations-panel" style="margin-bottom:14px">
  <div class="panel-title">Technical Escalations</div>

  <!-- Staff-raised technical escalation -->
  <div class="esc-item high">
    <div class="esc-dot high"></div>
    <div class="esc-body">
      <div class="esc-title">
        <span class="esc-source-badge staff">Staff</span>
        Door fault — Coach 3 D2L won't close
      </div>
      <div class="esc-meta">ICE 47 · Coach 3 · Conrad Müller · Advisory</div>
      <div class="esc-actions">
        <button class="esc-action-btn">Acknowledge</button>
        <button class="esc-action-btn">Resolve</button>
      </div>
    </div>
    <div>
      <div class="esc-time">14m ago</div>
      <div class="esc-status-pill new" style="margin-top:4px">New</div>
    </div>
  </div>

  <!-- AI-direct technical alert -->
  <div class="esc-item">
    <div class="esc-dot advisory"></div>
    <div class="esc-body">
      <div class="esc-title">
        <span class="esc-source-badge ai">AI</span>
        HVAC fault pattern — 3 recurrences in 40 min
      </div>
      <div class="esc-meta">RJ 789 · HVAC subsystem · Diagnostics AI</div>
      <div class="esc-actions">
        <button class="esc-action-btn">Acknowledge</button>
        <button class="esc-action-btn">View fault history</button>
      </div>
    </div>
    <div>
      <div class="esc-time">22m ago</div>
      <div class="esc-status-pill ack" style="margin-top:4px">Ack'd</div>
    </div>
  </div>

  <!-- Read-only operational escalation (Claudia's) -->
  <div class="esc-section-label">Operational · Routed to Claudia (read-only)</div>
  <div class="esc-item readonly">
    <div class="esc-dot advisory"></div>
    <div class="esc-body">
      <div class="esc-title">
        <span class="esc-source-badge ai">AI</span>
        Fall detected — passenger not moving
      </div>
      <div class="esc-meta">ICE 47 · Coach 4 · Emergency services coordinating</div>
    </div>
    <div>
      <div class="esc-time">2m ago</div>
      <div class="esc-status-pill ack" style="margin-top:4px">Ack'd</div>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Verify visually**

Open `mockups/maintenance-dashboard-v2.html`. Confirm:
- Roland's escalations inbox appears at the top of the right column
- Technical escalations (staff-raised and AI-direct) show with appropriate severity
- Claudia's operational escalation shows in muted read-only style below
- Existing cleaning schedule and depot plan panels remain below

- [ ] **Step 6: Commit**

```bash
git add mockups/maintenance-dashboard-v2.html
git commit -m "feat: maintenance dashboard v2 — Roland's escalations inbox"
```

---

## Task 8: Driver Display v2 — Fire/smoke full-screen takeover state

**Files:**
- Create: `mockups/driver-display-v2.html` (copy from `mockups/driver-display-v1.html`)

Adds a third state (fire/smoke) to the existing two states (Normal, Alert). Hard-cut red — no animation softening.

- [ ] **Step 1: Copy v1 as starting point**

```bash
cp mockups/driver-display-v1.html mockups/driver-display-v2.html
```

- [ ] **Step 2: Link shared tokens**

In `<head>`:

```html
<link rel="stylesheet" href="shared-tokens.css">
```

- [ ] **Step 3: Add fire takeover CSS**

Add this CSS block in the `<style>` section:

```css
/* ── State C: Fire/smoke takeover ── */
.driver-screen.fire-state {
  background: #0A0C10;
  border: 3px solid #FF3B3B;
  border-radius: 10px;
  padding: 20px;
  position: relative;
  overflow: hidden;
}
.fire-state::before {
  content: '';
  position: absolute;
  inset: 0;
  animation: fire-pulse 0.8s ease-in-out infinite;
  pointer-events: none;
  border-radius: 8px;
}
.fire-takeover-icon {
  font-size: 48px;
  text-align: center;
  margin-bottom: 12px;
  line-height: 1;
}
.fire-takeover-title {
  font-size: 28px;
  font-weight: 900;
  color: #FF3B3B;
  text-align: center;
  letter-spacing: -0.5px;
  margin-bottom: 6px;
  text-transform: uppercase;
}
.fire-takeover-detail {
  font-size: 14px;
  font-weight: 700;
  color: #F0F2F5;
  text-align: center;
  margin-bottom: 16px;
}
.fire-takeover-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.fire-action {
  background: rgba(255,59,59,0.15);
  border: 1px solid rgba(255,59,59,0.4);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #FF3B3B;
  text-align: center;
}
.fire-action.secondary {
  background: rgba(255,255,255,0.05);
  border-color: rgba(255,255,255,0.1);
  color: #9BA3AF;
}
```

- [ ] **Step 4: Add the fire/smoke state section**

Find the existing section divider for State B (Alert state). After the State B section closes, add:

```html
<!-- State C label -->
<div style="text-align:center;margin:32px 0 16px">
  <div style="display:inline-block;background:rgba(255,59,59,0.15);border:1px solid rgba(255,59,59,0.4);border-radius:20px;padding:5px 16px;font-size:11px;font-weight:700;color:#FF3B3B;text-transform:uppercase;letter-spacing:1px">
    State C — Fire / Smoke Detected
  </div>
  <div style="font-size:12px;color:#6B7280;margin-top:8px">Hard cut — no transition. Full-screen takeover overrides all other states.</div>
</div>

<div style="display:flex;justify-content:center">
  <div style="width:480px">
    <div class="driver-screen fire-state">
      <div class="fire-takeover-icon">🔥</div>
      <div class="fire-takeover-title">Smoke Detected</div>
      <div class="fire-takeover-detail">Coach 5 · Passenger Saloon · All parties alerted</div>
      <div class="fire-takeover-actions">
        <div class="fire-action">⚠ Follow emergency protocol · Contact Claudia</div>
        <div class="fire-action">Next stop: Linz Hbf — 4 min</div>
        <div class="fire-action secondary">Emergency services notified automatically</div>
      </div>
    </div>
    <div style="margin-top:12px;font-size:11px;color:#6B7280;text-align:center">
      This state can only be cleared by Control Centre (Claudia) after confirming safe resolution.
    </div>
  </div>
</div>
```

- [ ] **Step 5: Verify visually**

Open `mockups/driver-display-v2.html`. Confirm:
- State A (Normal) and State B (Alert) render identically to v1
- State C renders below them: red-bordered screen, pulsing background, fire icon, takeover title, action panels
- No smooth animation on the state C appearance (hard cut note is visible)

- [ ] **Step 6: Commit**

```bash
git add mockups/driver-display-v2.html
git commit -m "feat: driver display v2 — fire/smoke full-screen takeover state"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task covering it |
|---|---|
| Expected vs actual — alert-driven on train cards | Task 2 Step 7 |
| Expected vs actual — coach detail on drill-in | Task 4 |
| Expected vs actual — coach detail on Conductor App | Task 6 Step 2 |
| Luggage density icons on coach bar (Control Centre) | Task 2 Step 6–7 |
| Congestion score icons on coach bar (Control Centre) | Task 2 Step 6–7 |
| Congested coaches + Luggage alerts KPIs | Task 2 Step 3–5 |
| Open escalations KPI | Task 2 Step 5 |
| Escalations inbox — Claudia (Control Centre) | Task 3 |
| Coach drill-in grid with all metrics | Task 4 |
| Conductor escalate form (category, severity, voice, routing) | Task 5 |
| Conductor escalations tab (list, status, push outcomes) | Task 5 |
| Coach detail panel — exp vs actual, luggage, congestion, bicycle | Task 6 |
| Bicycle alert type in Conductor alert feed | Task 6 Step 3 |
| Fire/smoke alert — Conductor feed + full severity treatment | Task 6 Step 3 |
| Vandalism alert type in Conductor alert feed | Task 6 Step 3 |
| Roland escalations inbox (Maintenance Dashboard) | Task 7 |
| Cross-visibility — Claudia sees Roland's, Roland sees Claudia's | Tasks 3 and 7 (read-only sections) |
| Driver display fire/smoke full-screen takeover | Task 8 |
| Shared CSS tokens for consistent visual system | Task 1 |

All spec requirements are covered. No gaps found.

**Placeholder scan:** No TBDs, TODOs, or vague steps. All steps contain exact HTML/CSS.

**Type consistency:** CSS class names used consistently — `esc-item`, `esc-dot`, `esc-body`, `esc-status-pill`, `esc-source-badge` used identically in Tasks 3, 5, 6, 7. `coach-metric`, `coach-metric-value` consistent in Task 6. `cgr-*` column classes consistent in Task 4.
