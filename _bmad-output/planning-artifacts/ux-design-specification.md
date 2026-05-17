---
stepsCompleted: [1, 2]
inputDocuments:
  - _bmad-output/design-artifacts/A-Product-Brief/product-brief.md
  - _bmad-output/design-artifacts/B-Trigger-Map/00-trigger-map.md
  - _bmad-output/design-artifacts/B-Trigger-Map/02-Conductor-Conrad.md
  - _bmad-output/design-artifacts/C-UX-Scenarios/00-scenarios-index.md
  - _bmad-output/design-artifacts/C-UX-Scenarios/06-passenger-accessibility-guidance.md
  - _bmad-output/design-artifacts/D-UX-Design/2026-05-14-oebb-ux-design-v2.md
  - _bmad-output/design-artifacts/D-UX-Design/scenario-10-specs/01-conductor-app-pre-arrival-dashboard.md
  - _bmad-output/_progress/scenario-10-validation-report-2026-05-14.md
  - project-context.md
activeScenario: "06 — Passenger with Pushchair Finds Accessible Space"
---

# UX Design Specification — OEBB Smart Rail
# Scenario 06 Conceptual Specifications

**Author:** AbbasRizvi
**Date:** 2026-05-14

---

## Executive Summary

### Project Vision

OEBB Smart Rail delivers real-time AI-powered situational awareness to onboard and landside rail staff, while surfacing actionable passenger guidance through platform screens and a mobile portal. Scenario 06 extends this to the highest-stakes passenger interaction: accessibility-dependent boarding, where the system must coordinate detection, staff alerting, and passenger communication within the window of a station stop.

### Target Users (Scenario 06)

- **Primary:** Passenger with a pushchair or wheelchair — anxious, time-pressured, needs the right door and a deployed ramp before they commit to a location
- **Primary onboard:** Conductor Conrad — needs enough lead time to walk to the correct coach before the passenger arrives
- **Secondary:** Passenger Portal (the information surface the passenger uses)

### Key Design Challenges

1. **Confidence uncertainty** — Hailo-8 inference accuracy for wheelchair/pushchair is unconfirmed. The UI must handle "probably an accessible passenger" vs "confirmed" without false assurance
2. **Lead-time logic** — The alert must reach Conrad with enough time to walk to the coach. The trigger source (portal open? platform camera? HAFAS reservation?) is unspecified
3. **Occupied space path** — If the accessible space is already taken by another wheelchair user, the portal must surface this before the passenger commits to that door
4. **Ramp deployment close-the-loop** — Conrad taps "ramp deployed" → alert resolves; but what if he never taps? Timeout logic and fallback escalation are unspecced
5. **Persistent accessibility indicator** — Portal must reflect accessible space status throughout the journey, not just at boarding

### Design Opportunities

- **Proactive → reactive shift**: Conrad arrives at the door before the passenger, not after — transforms accessibility from a reactive scramble into a planned service
- **Portal as accessibility companion**: Journey-long ramp/space status turns the portal from a boarding tool into an ongoing accessibility aid
- **Escalation pathway**: If accessible space is occupied, early redirection prevents platform-side confrontation — high ÖBB compliance value

---

<!-- Scenario 06 spec content will be appended as individual spec files in scenario-06-specs/ -->
