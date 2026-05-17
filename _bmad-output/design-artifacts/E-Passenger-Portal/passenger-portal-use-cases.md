# Passenger Portal — Use Cases
**Agent:** Saga (WDS Analyst) → Freya (UX Designer)
**Phase:** 2 → 3 handoff
**Date:** 2026-05-14
**Status:** Complete — ready for UX design

---

## Summary

The ÖBB Railnet CNA (Captive Network Assistant) portal is the mandatory WiFi splash page every passenger sees before connecting to onboard WiFi. It is served locally from the Nomad Digital R5001C, loads in under 1 second, and requires no login or app install.

The new coach guidance panel is added **below** the existing entertainment promo on the CNA splash page. It is visible before the passenger connects — maximum reach, zero friction.

---

## Personas

| Persona | Name | Primary need |
|---|---|---|
| Passenger (general) | Petra | Find a seat quickly; board the right coach |
| Passenger (accessibility) | Hanna | Confirm accessible space; know staff are ready |

---

## Use Case Index

### General Passenger (Petra)

| Code | Title | Trigger | Primary portal behaviour |
|---|---|---|---|
| UC-P01 | Glance and go — evenly distributed load | Mixed load across train | Show coach load colours only; no directional arrow |
| UC-P02 | Directed to specific coach | Clear best coach identified | Show "Gehen Sie zu Wagen N →" with directional arrow |
| UC-P03 | Train is full | All coaches >85% | Show least-worst coach; set expectation honestly |
| UC-P04 | Mid-journey load check | Passenger connects after boarding | Show current load; offer "move to quieter coach" if beneficial |
| UC-P05 | Luggage rack guidance | High luggage density in recommended coach | Steer to coach with available rack space |

### Accessibility Passenger (Hanna)

| Code | Title | Trigger | Primary portal behaviour |
|---|---|---|---|
| UC-A01 | Accessible space free — smooth boarding | Space available, Conrad alerted | Show space free + door; fire Conrad alert in background |
| UC-A02 | Accessible space occupied | Space taken by existing passenger | Show occupied state; direct to find conductor |
| UC-A03 | Multiple accessible coaches | Two PRM coaches on train | Show both with status; recommend nearest available |
| UC-A04 | Automatic Conrad alert | Portal loads with accessibility coach visible | Fire alert to conductor app without requiring passenger action |
| UC-A05 | Ramp confirmation loop | Conrad confirms ramp deployed | Portal updates to "Rampe bereit" live |

---

## Data Requirements (from Hailo-8 Passenger AI)

| Data point | Source | Required for |
|---|---|---|
| Passenger count per coach | Hailo-8 occupancy inference | UC-P01, UC-P02, UC-P03, UC-P04 |
| Coach capacity (max) | Static config per train type | Occupancy % calculation |
| Luggage density per coach vestibule | Hailo-8 luggage detection | UC-P05 |
| Accessible space occupancy (coach N) | Hailo-8 wheelchair/pushchair detection | UC-A01, UC-A02, UC-A03 |
| PRM door + coach number | Static config per train type | UC-A01, UC-A02, UC-A03, UC-A04, UC-A05 |
| Ramp deployment status | Conductor app confirmation event | UC-A05 |
| Train orientation at platform | GNSS + station config | UC-P02 directional arrow |
| Data timestamp | System clock | Freshness indicator on portal |

---

## Occupancy Thresholds (aligned with existing design tokens)

| Colour | Token | Threshold | Label (DE) |
|---|---|---|---|
| Green | `--coach-low` | 0–60% | Viel Platz |
| Amber | `--coach-mid` | 61–85% | Mäßig besetzt |
| Orange | `--coach-high` | 86–100% | Stark besetzt |
| Red | `--coach-critical` | >100% | Überfüllt |

---

## Directional Arrow Logic (UC-P02)

The portal shows a directional arrow ("→" or "←") when **all three conditions** are met:

1. One coach is clearly the least occupied (>20% less than next-best coach)
2. Train orientation data is available and fresh (<5 min old)
3. The recommended coach is not the nearest coach to the passenger's likely platform position

When conditions are not all met: show coach load diagram only, no arrow.

---

## Portal Integration Constraints

- Served by R5001C local web server — no internet dependency
- All data from Hailo-8 Passenger AI via local API (same VLAN)
- Target load time: <1 second (local network)
- Refresh cycle: 30 seconds or on page open (whichever is sooner)
- No login, no cookies, no tracking — DSGVO compliant by design
- German language only (portal language setting)
- Conrad alert (UC-A04) fires via existing conductor app push notification path
