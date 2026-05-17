# Product Brief — OEBB Smart Rail Passenger Intelligence

**Project:** OEBB Smart Rail
**Date:** 2026-05-14
**Stage:** Phase 1 — Product Brief (WDS)
**Prepared by:** Saga (WDS Analyst)
**Status:** Draft — confirmed with Abbas Rizvi

---

## Vision

**Nomad Digital becomes the intelligence layer of European rail** — transforming a connectivity hardware install into a continuously delivered AI service that makes every ÖBB train smarter, safer, and more commercially valuable with each journey.

The Hailo-8 M.2 is not the product. The product is the *insight* it enables: real-time knowledge of what is happening in every coach, surfaced to the right person, at the right moment, on the right device. Nomad Digital's unique position — owning the VLAN routing on these trains — means no competitor can replicate this without replacing the network infrastructure first.

---

## Business Context

**Company:** Nomad Digital (vendor/operator)
**Client:** ÖBB (Austrian Federal Railways)
**Domain:** Rail operations — onboard passenger intelligence
**Delivery model:** Fully managed AI Insights-as-a-Service, operated by Nomad Digital
**Commercial model:** Per-train monthly subscription (SaaS)
**Pilot timeline:** 3 months

This engagement began as a hardware request (Hailo-8 M.2 install on the R5001C CCU). Nomad Digital's strategic response is to reframe it as the foundation of an ongoing service relationship — one that grows in value as more data is captured, more models are refined, and more operators are onboarded.

---

## The Problem

ÖBB train staff currently manage passenger flow, congestion, and safety incidents through direct observation — walking the train, visual checks, radio communication. This is:

- **Slow** — a conductor walking a 10-coach train takes 3–5 minutes; overcrowding incidents resolve faster than that
- **Incomplete** — no single person has simultaneous visibility across all coaches
- **Reactive** — unattended luggage, door obstructions, and accessibility needs are discovered only after they become problems
- **Unscalable** — landside operations (control centre, fleet management) have no real-time data on individual train occupancy

The status quo wins by default. No direct AI competitor is currently pitching equivalent services on this fleet.

---

## The Solution

A single Hailo-8 M.2 AI accelerator on SYS2 of the Nomad Digital R5001C CCU, running the **Passenger Intelligence Service** — a fully managed, privacy-by-design AI service that delivers:

| Capability | What it does |
|---|---|
| **Live occupancy** | Real-time passenger headcount per coach |
| **Luggage detection** | Luggage item count + unattended bag alerts (configurable timer) |
| **Congestion mapping** | Colour-coded train diagram (green/amber/red by threshold) |
| **Door safety** | Obstruction detection alerts at doors |
| **Accessibility detection** | Wheelchair user / pushchair detection, PRM door correlation |
| **Maintenance suppression** | Alert suppression during depot maintenance mode |

All inference runs onboard. Raw video never leaves the train. Only structured, anonymised results are transmitted to the cloud.

---

## Target Users

### Primary — Conductor / Train Manager
The most important user. The Conductor needs a unified, prioritised view of everything happening on the train — right now, on a mobile handheld. They are safety-responsible, time-pressured, and frequently interrupted. They cannot afford to miss a high-priority alert because it was buried.

### Secondary — Control Centre Operator
Fleet-wide visibility. The Control Centre needs real-time occupancy data across multiple trains to make capacity decisions, manage service disruptions, and coordinate with platform staff. They operate on web dashboards and need breadth, not depth.

### Secondary — Fleet Maintenance Manager
Occupancy trends for planning. Not real-time operational use — needs historical patterns for fleet deployment decisions, not live alerts.

### Supporting — Bistro / Café Staff
Coach load for catering. Lightweight use — needs to know which coaches are busy to allocate catering resources. Simple, low-frequency data need.

### Supporting — Driver
Read-only summary on cab-mounted display. Safety requirement: no interaction, no distraction. Receives highest-severity alerts passively.

### Supporting — Capacity Planner
Web reports for long-range planning. Consumes aggregated occupancy analytics for network-level decisions. Lowest urgency of all six roles.

---

## Scope

### In Scope
- Passenger AI service (occupancy, luggage, congestion, door safety, accessibility)
- 6 role-specific interfaces (Conductor app, Bistro app, Driver display, Control Centre dashboard, Fleet Maintenance dashboard, Capacity Planner reports)
- Edge inference on Hailo-8 M.2 (SYS2, R5001C CCU)
- Cloud sync via SYS1 (structured results only, no raw video)
- 3-month pilot deployment

### Out of Scope
- Diagnostics AI (SNMP/TCMS fault ingestion) — handled separately via Nomad's Nomie backend
- Natural language diagnostics chat — Nomie integration, separate engagement
- Platform Staff interface — removed from this engagement
- Technician app — diagnostics-only, out of scope

---

## Success Criteria

### Operational (ÖBB)
- Conductors reduce time spent walking the train to manually assess occupancy
- Fewer delayed departures caused by undetected door obstructions
- Accessibility incidents (PRM door, ramp deployment) handled proactively, not reactively
- Control Centre gains real-time occupancy visibility across pilot fleet

### Technical (Nomad Digital)
- Inference accuracy meets agreed threshold for occupancy count (target: ≥95% accuracy)
- Alert false-positive rate below agreed threshold (target: <5%)
- System uptime ≥99.5% across pilot period
- Raw video confirmed to never leave train (privacy compliance)

### Commercial (Nomad Digital)
- ÖBB signs renewal / expansion contract at end of 3-month pilot
- Pilot creates replicable blueprint for deployment on other European rail operators
- Per-train monthly subscription model validated as commercially viable

---

## Competitive Landscape

No direct AI competitor is currently offering equivalent services on this ÖBB fleet. The competitive context is **status quo** — manual observation by staff. Nomad Digital's advantage is:

1. **Infrastructure position** — VLAN ownership gives data access no new entrant can match without replacing the network
2. **Multi-source fusion** — Camera, APC, PIS, bistro telemetry, energy metering all accessible; competitors would have camera only
3. **Existing trust** — Nomad Digital is already the connectivity provider; this extends a relationship, not initiates one

The risk to this position is **inaction** — if Nomad Digital does not build this service, ÖBB may eventually procure a standalone AI solution from a competitor who gains a foothold on the fleet.

---

## Technical Constraints

| Constraint | Detail |
|---|---|
| **Edge hardware** | Single Hailo-8 M.2 (M-key 2242/2280, PCIe Gen 3 x4) on ADLINK cPCI-A3H20 blade |
| **Host OS** | Debian 12 + Docker (SYS2) |
| **Runtime** | HailoRT — supported on Debian 12 |
| **Privacy** | Raw video never leaves train — inference only |
| **Cloud sync** | Structured results only via SYS1 connectivity |
| **Operating temp** | Hailo-8 rated -40°C to 85°C — rail-compliant |
| **Pilot timeline** | 3 months |
| **Diagnostics AI** | Out of scope — handled via Nomie backend separately |

---

## Strategic Opportunity

The 3-month ÖBB pilot is not just a product test — it is a **blueprint exercise**. If Nomad Digital can demonstrate a repeatable, privacy-compliant, per-train SaaS model on ÖBB, the same architecture deploys on any operator where they hold network infrastructure. The moat is not the AI model; the moat is the data position. Every new operator onboarded makes the service more defensible.

The Product Brief for the ÖBB pilot should therefore be written with two audiences in mind: ÖBB (who need operational proof), and future operators (who need commercial proof that this works at scale).
