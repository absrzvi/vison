# Railnet Passenger Portal — UI Kit (Interactive Prototype)

An interactive React recreation of the **ÖBB Railnet captive WiFi portal v2** — the WLAN splash page every passenger sees on a railjet, redesigned with a live **coach occupancy guidance panel** so passengers can find space *before* committing to a door.

This is the second variant of the Railnet captive portal. The first kit (`ui_kits/railnet_portal/`) models the existing three-screen flow (welcome carousel → T&C → connected). This kit models the proposed redesign: a single‑page captive portal with the brand promo on top, the new coach panel in the middle, and the existing terms + Verbinden button at the bottom.

Open `index.html` in this folder. The phone renders on the left; a state-switcher panel on the right cycles through the ten portal states from the design spec.

## What's modelled

The portal handles **ten distinct states** spanning both personas:

### Petra — general passenger (Persona 9)

| State | Use case | Behaviour |
|---|---|---|
| **Gemischte Auslastung** | UC-P01 | Mixed load. Colours only, no recommendation. |
| **Empfehlung** | UC-P02 | One coach >20 % less full → green guidance box, directional arrow, recommended coach pulses on the diagram. |
| **Zug stark besetzt** | UC-P03 | All coaches >85 % → amber warning, least-worst coach named. |
| **Während der Fahrt** | UC-P04 | Mid-journey. "HIER" badge shows current coach; info box steers to a quieter wagon. |
| **Gepäck-Hinweis** | UC-P05 | Recommended coach is *not* the absolutely emptiest, but the one with rack space — neighbours show 🧳. |

### Hanna — accessibility passenger (Persona 10)

| State | Use case | Behaviour |
|---|---|---|
| **Rollstuhlplatz frei** | UC-A01 | Blue accessibility panel; ramp pill spins "wird vorbereitet …"; quietly notes that the conductor has been notified. After 4.5 s, the panel auto-transitions to *Rampe bereit* (UC-A05 confirmation loop). |
| **Rollstuhlplatz belegt** | UC-A02 | Amber panel; "Bitte Schaffner kontaktieren". |
| **Rampe bereit ✓** | UC-A05 | Green ramp-confirmed pill replaces the loading state. |

### Fallback states

| State | Behaviour |
|---|---|
| **Daten veraltet** | Diagram desaturates; guidance & access panels hidden; "Wird aktualisiert …" spinner. |
| **Keine Daten** | Diagram hidden; graceful Wi-Fi-off message with platform-signage fallback. |

## Wired to the design system

All visual properties come from `../../colors_and_type.css`:

- ÖBB house red, neutrals, type ramp (Open Sans)
- Spacing scale, radii, shadows
- The **operational severity scale** (`#22C55E / #F5A623 / #FF6B00 / #FF3B3B`) — shared with the Smart Rail Conductor App so passengers and crew see the same colour for "Wagen 4 ist stark besetzt"

The single asset import is `<img src="../../assets/logos/OeBB_railnet.png">` for the header lockup, and `Filme-und-Serien_red.svg` for the entertainment promo block.

## Files

```
ui_kits/railnet_passenger/
├── index.html                  ← entry point, mounts React
├── icons.js                    ← inline Lucide-compatible icon set
├── scenarios.js                ← 10 state definitions
├── Icon.jsx                    ← <Icon name="…" size={…} color={…} />
├── CoachDiagram.jsx            ← 8-coach diagram + freshness pill + orientation labels
├── GuidanceBox.jsx             ← recommendation / warning / info card
├── AccessibilityPanel.jsx      ← PRM status + ramp confirmation loop
├── CoachGuidancePanel.jsx      ← the full "Zugauslastung" section
├── Hero.jsx                    ← entertainment promo (Filme & Serien)
├── PortalHeader.jsx            ← ÖBB lockup + language picker
├── TermsBlock.jsx              ← T&C checkbox + Verbinden flow
├── PhoneShell.jsx              ← iPhone bezel + CNA system chrome
├── PassengerPortal.jsx         ← composes the whole captive page
├── StateControls.jsx           ← scenario switcher (right rail)
└── App.jsx                     ← top-level state + UC-A05 auto-transition
```

## What's intentionally faked

- The local R5001C REST API — coach data is hardcoded per scenario in `scenarios.js`.
- The Hailo-8 confidence/refresh — there is no real 30 s polling.
- The Conrad app handshake for UC-A05 — the ramp confirmation is simulated with a 4.5 s `setTimeout`.
- The OS-level captive popup chrome — drawn as a static "WLAN-Anmeldung · railnet.oebb.at" bar at the top.

## Source documents

- **Spec:** `uploads/2026-05-14-passenger-portal-design.md` — full panel design + 8 states.
- **Persona — Petra (general):** `uploads/persona-passenger-general.md`
- **Persona — Hanna (accessibility):** `uploads/persona-passenger-accessibility.md`
- **Earlier HTML mockup:** `mockups/passenger-portal-v1.html` (Nomad)

## Caveats

- **Two additional persona-driven scenarios** (UC-P04 mid-journey, UC-P05 luggage steer) are wired but not in the original 8 states — flag if they should be removed.
- **All copy is German** as the spec requires. The language picker shows EN/IT/FR slots disabled.
- **The recommended-coach pulse** is a design addition; the spec only required colour + arrow text. Tell me if it's too loud — easy to drop.
- **The "HIER" badge** (current-coach indicator on UC-P04) assumes the portal knows which coach the passenger is in. The spec doesn't specify how this is derived — pin to MAC-address-via-AP-localisation as a placeholder.
