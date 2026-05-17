# Scenario 04 — Claudia Runs Her Morning Fleet Occupancy Review

**Persona:** Control Centre Claudia (Secondary)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Daily analytics view — Claudia reviews yesterday's occupancy patterns across the fleet each morning, identifies chronic mismatches, and flags services for capacity adjustment.

## Entry Point
Claudia arrives at her workstation at 07:45. Her Control Centre dashboard is already open. She opens the occupancy analytics panel — a daily habit, takes 5 minutes.

## Mental State
**Trigger:** New day, new data. Claudia wants to know if anything from yesterday's services needs attention before today's peak.
**Hope:** That the overnight data is clean, patterns are visible, and anything requiring action is already surfaced as an exception — she shouldn't have to hunt.
**Worry:** That the data is incomplete, stale, or buried in a table she has to manually interpret — wasting her first 30 minutes on data wrangling instead of decisions.

## Sunshine Path

1. Claudia opens the occupancy analytics panel — default view shows yesterday's fleet-wide occupancy summary: average load by route, peak times, and a red/amber/green exception list of services that exceeded capacity thresholds
2. Three services are flagged red in yesterday's data — all Friday evening intercity routes. One of them has a Conrad escalation attached (from Scenario 03).
3. Claudia clicks the escalated service — she sees Conrad's note, the 7-day trend, and the occupancy data. She marks it for capacity review and assigns it to the fleet planning queue.
4. She reviews the other two flagged services — no escalations, but the trend data shows both have been amber-to-red for 3 consecutive weeks on the same time slot.
5. She adds both to the capacity review queue with a note: "Recommend additional rolling stock or consist change for peak Friday services."
6. Daily review complete in 7 minutes. Claudia closes the panel and returns to live monitoring.

## Success Goals
**Claudia:** Identified 3 capacity issues in under 10 minutes with evidence already attached. Zero manual data extraction.
**Business (Nomad Digital):** Analytics layer delivers fleet-level value beyond individual train monitoring — expands the commercial story from "conductor tool" to "fleet intelligence platform."

## Trigger Map Connections
- ✅ Make defensible capacity decisions — trend data makes the case, not gut feel
- ✅ Spot developing situations before incidents — 3-week trend visible, not just yesterday
- ❌ Fear acting on stale/inaccurate data — data is timestamped and sourced from live inference
- ❌ Frustration with active monitoring — exceptions surfaced automatically, Claudia only reviews flagged items

## Design Notes
- Default view must surface exceptions, not raw data — Claudia should not need to scan a table
- Exception threshold must be configurable — ÖBB may have different standards for different route types
- Conrad escalations must be visually linked to the relevant service in Claudia's view — the connection between onboard observation and landside data must be explicit
- Export capability required — Claudia needs to put this into a management report without manual copying
