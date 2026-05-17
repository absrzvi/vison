# Conductor App — UI Kit (Interactive Prototype)

The **ÖBB Smart Rail Conductor App** — a working React prototype of the mobile handheld used by train conductors / *Zugbegleiter*. Five day-in-the-life scenarios, navigable via the bottom tab bar (Home / Train / Alerts / Escalate / Chat) and switchable via the "Demo · Scenarios" panel in the top-right.

This kit is **wired to the ÖBB Railnet Portal Design System** — every colour, type rule, and surface comes from `../../colors_and_type.css` (operations dark mode, `obb-dark` class). All chrome icons are inline SVGs drawn from the Lucide icon set.

## How to use

1. Open `index.html` — the prototype mounts with **Scenario 1 (T−8 boarding)** on the **Home** tab.
2. Tap tabs in the bottom nav to switch screens.
3. Tap the **Demo · Scenarios** panel (top-right) to jump through the five scenarios:
   1. **T−8 boarding** — rack saturation alert, coach diagram, full alert list, diagnostics chat preview.
   2. **Vestibule alert** — 11-pax door-zone heatmap, pre-filled PA targeted at Coach 4. Tap **Send PA** to auto-advance to scenario 3.
   3. **Vestibule resolved** — auto-resolve confirmation after the PA, post-action summary card.
   4. **Occupancy imbalance** — heavy/light load split with PA + PIS-screen combined action.
   5. **Unattended bag** — camera still-frame, 7-min stationary timer, one-tap escalation to Control Centre.
4. Tap any **coach** in the diagram to switch the detail panel.
5. Tap any **alert** to dismiss with the × button.
6. In the **Escalate** tab — pick a category, the routing pill updates (Operational → Claudia / Technical → Roland). Submit pushes a new entry to the inbox sub-tab.
7. In the **Chat** tab — ask about *HVAC*, *door*, *rack*, or *smoke* and the diagnostics agent replies with a scripted response.

## What's interactive

| Surface | Interactive bits |
|---|---|
| **Coach diagram** | Tap to select; detail panel reflects selection. |
| **Alert list** | Per-alert dismiss; "Dismiss all" on the Alerts tab. Bottom-nav badge counts update live. |
| **PA panel** | Send button shows confirmation; vestibule scenario auto-advances to resolved state. |
| **Tabs** | All 5 tabs render their own scenario-aware content. |
| **Scenarios** | Switch between 5 ops scenarios from the panel; tab + state reset per scenario. |
| **Escalation form** | Category buttons, severity toggle, voice-note button, "Submit" pushes a new item to inbox. |
| **Diagnostics chat** | Keyword-matched canned replies — try "HVAC coach 3" or "smoke" or "rack". |

## Files

```
ui_kits/conductor_app/
├── index.html              ← entry point, mounts React
├── icons.js                ← inline icon set (Lucide-compatible)
├── scenarios.js            ← all scenario data (5 scenarios in one map)
├── Icon.jsx                ← <Icon name="…" size={…} color={…} />
├── Atoms.jsx               ← SLabel · StatusBar · AppHeader · AlertBanner · CoachDiagram · DetailRow · MetricGrid · RackBar · Btn
├── BottomNav.jsx           ← 5-tab bottom nav with badge support
├── PhoneFrame.jsx          ← Phone bezel with dynamic island + status bar
├── ScenarioControls.jsx    ← Collapsible demo-scenario panel (top-right)
├── HomeScreen.jsx          ← Boarding home: banner + coach diagram + alerts + chat preview
├── TrainScreen.jsx         ← Heatmap · Imbalance · Camera (switches by scenario shape)
├── AlertsScreen.jsx        ← Full alert list with bulk-dismiss
├── EscalateScreen.jsx      ← Categorised form + inbox sub-tab
├── ChatScreen.jsx          ← Diagnostics agent with canned replies
├── App.jsx                 ← Top-level state, scenario routing, all glue
├── index.original.html     ← Original Nomad mockup (kept for reference)
├── showcase.html           ← Static deck version (kept; same source as original, retokenised)
└── shared-tokens.css       ← Legacy token file (deprecated; use ../../colors_and_type.css)
```

## What's intentionally faked

- The captive Hailo-8 AI back-end — alerts/metrics are scripted per scenario.
- The Stadler alarm code lookup — diagnostics chat uses 4 canned replies.
- The PA + PIS hardware integration — sending is just a UI confirmation.
- The Control-Centre handoff — escalations land in a local inbox, not a real Claudia queue.

## How to extend to other Smart Rail products

Same recipe — drop the design tokens, copy whatever atoms you need:

```html
<link rel="stylesheet" href="../../colors_and_type.css">
<body class="obb-dark">
  <!-- conductor / driver / technician / bistro / control-centre -->
</body>
```

Reusable atoms: `AppHeader`, `AlertBanner`, `CoachDiagram`, `DetailRow`, `MetricGrid`, `RackBar`, `Btn`, `Icon`, `BottomNav`, `PhoneFrame`.

## Caveats — flag any of these

- **All copy is in English.** For a real Austrian/DACH deployment, translate to DE (Sie-form per Railnet voice rules).
- **Five scenarios only.** Roland's escalation acknowledgement loop, multi-train comparison, settings, profile, history etc. are all out of scope for this slice.
- **Icons** are a curated subset of Lucide inline at `icons.js` (~29 icons). Add to the map to use new ones.
- **The smoke/fire detection flow is concept-only.** Don't ship this without round-trip integration with the actual fire-detection bus.
