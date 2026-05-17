# Scenario 02d — Conrad Investigates an Unattended Bag

**Persona:** Conductor Conrad (Primary)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Unattended bag detection — Hailo-8 camera inference detects a stationary bag or item in a vestibule or seat area after surrounding passengers have moved away, and alerts Conrad after a configurable timer elapses. Conrad can review the camera feed, assess severity, and escalate or dismiss.

## Entry Point
Conrad is mid-journey, seated in the conductor area completing admin. His handheld shows a new alert — different tone from the occupancy alerts.

## Mental State
**Trigger:** Alert reads: "Unattended item — Coach 6 vestibule. Stationary 7 min. Area now empty. Review required."
**Hope:** That it's a forgotten bag and the owner is still on the train — a 30-second PA message will resolve it.
**Worry:** That it is something more serious, and that he'll have to make a judgment call in public with passengers watching. He doesn't want to cause a panic, but he can't ignore it.

## Sunshine Path

1. Conrad taps the alert — a camera still-frame of the coach 6 vestibule loads, showing a medium-sized dark backpack on the floor near the door. The surrounding seats are empty. Timestamp: 7 minutes stationary.
2. He reviews the context panel: the bag appeared in frame 8 minutes ago when the area was occupied; the last passenger left the vestibule area 7 minutes ago. No person has returned.
3. Conrad assesses: it looks like a forgotten bag — standard shape, no unusual features visible. He selects "PA — owner request" and the app pre-fills: "Attention passengers — has anyone left a bag in coach 6 near the doors? Please return to collect it immediately."
4. He sends the PA and walks toward coach 6 — 45 seconds away.
5. By the time he arrives, a passenger is already returning: "Sorry, I left it when I went to the bistro." Conrad confirms visually, logs "Resolved — owner identified" and closes the alert.
6. If no owner had come forward within 2 minutes of his arrival, Conrad's next screen would show escalation options: "Notify Control Centre" or "Initiate security protocol" — but this time it doesn't come to that.

## Edge Case — Escalation Path

If Conrad reviews the camera still and is not comfortable with what he sees (unusual shape, unusual location, no plausible owner context), he can escalate immediately:
- "Escalate to Control Centre" — sends the still-frame, timestamp, and coach location to Claudia's dashboard with a single tap
- Claudia receives a priority alert and can loop in ÖBB security coordination
- Conrad does not need to verbally describe the scene — the image and metadata are transmitted automatically

## Success Goals
**Conrad:** Responded to the alert without causing unnecessary alarm. Resolved a routine case in under 3 minutes. Knew exactly how to escalate if needed.
**Business (Nomad Digital):** Security-adjacent feature handled with clear escalation path. Alert demonstrated: specific, actionable, low false-positive rate (configurable timer prevents alerts for bags set down briefly).

## Trigger Map Connections
- ✅ Fear missing safety-critical incident — directly addressed
- ✅ Act before problems escalate — Conrad reaches the location before the situation worsens
- ✅ Feel in control and equipped — escalation path is always one tap away
- ✅ Claudia escalation pathway exercised (connects to Scenario 03)

## Design Notes
- Timer before alert fires must be configurable per operator: 5 minutes is the suggested default for vestibule areas; seat areas may warrant a longer timer (passengers leave belongings at seats while visiting bistro)
- Camera still-frame must load within 3 seconds of tapping the alert — delay will force Conrad to walk blind to the location first
- Still-frame only (no live video): simpler infrastructure, lower privacy risk, sufficient for triage. Live video only on explicit escalation if ÖBB security requires it
- Alert severity must be visually distinct from occupancy/congestion alerts — different colour (e.g. blue vs. amber) and a different notification tone to communicate "review required" vs. "action now"
- PA pre-fill must be generic enough not to cause alarm in coach 6 while Conrad assesses — avoid words like "suspicious" or "security"
- Escalation to Claudia must transmit the image automatically — Conrad cannot be expected to describe what he sees while standing in a public vestibule
- ⚠️ Privacy consideration: camera feed access by Conrad must be scoped to the alert event. Conrad should not have free browsing access to live camera feeds across all coaches — this requires an access control decision from ÖBB and Nomad Digital
