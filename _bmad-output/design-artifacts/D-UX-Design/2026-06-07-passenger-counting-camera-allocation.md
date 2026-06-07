# Passenger-Counting Camera Allocation — 8 Cameras / 6-Car KISS

**Agent:** Freya | **Phase:** WDS-4 (UX Design) | **Date:** 2026-06-07
**Status:** Draft for bench validation
**Related:** [Hailo bench test case](../../../docs/superpowers/specs/2026-06-07-hailo-camera-allocation-bench-case.md) · GA drawing 200.102 d · ADR-9 (onboard WS)

---

## Decision

Allocate the 8-camera budget across a 6-car Stadler KISS as a **hybrid flow + occupancy** scheme:

| # | Cameras | Role | Detector mode | Target FPS |
|---|---------|------|---------------|------------|
| 1 | **6 × door-line counters** (one per car) | Net flow: boardings − alightings at the highest-traffic vestibule of each car | Threshold tripwire / line-cross counting | 5–8 fps |
| 2 | **2 × saloon overheads** | Absolute zone occupancy to re-zero cumulative flow drift | Head-detection per zone | ~10 fps |

Saloon overheads placed in:
- **W400 accessibility car** — slow/dwelling door crossings (wheelchair, pram, bike) defeat tripwire counting; absolute count is more reliable here.
- **One end car** — largest boarding surge → largest cumulative drift → periodic absolute re-zero.

## Why this split

Driven by three confirmed constraints:

| Constraint (confirmed 2026-06-07) | Consequence |
|---|---|
| **Hybrid goal** (flow + absolute occupancy) | 6 flow streams primary, 2 absolute streams for drift correction |
| **Shared VLAN 5 CCTV** (not dedicated installs) | Placement constrained to existing FOV; calibrate against APC rather than ideal top-down geometry |
| **All 8 streams concurrent on one Hailo-8** | Per-stream FPS is scarce → favour low-FPS door tripwires over high-FPS saloon tracking |

Door-line counting is more accurate **per camera** than saloon head-detection and tolerates low FPS — the right trade when one Hailo-8 time-slices 8 streams.

## Ground-truth reconciliation

Where a door-line camera and a **VLAN 8 APC** door sensor watch the same threshold, the APC count is treated as ground truth and used to **continuously calibrate camera drift**. This overlap is free accuracy — no extra hardware.

## Open dependencies (block buildability)

1. **FOV reality check.** Shared CCTV means some VLAN 5 cameras lack a usable door-crossing angle. The per-car door-counter assignment is only valid for cars where an existing camera actually frames a threshold. **Needs:** GA drawing 200.102 d (higher-res door-position crop) cross-referenced with the CCTV mount list.
2. **Hailo FPS ceiling.** 8 concurrent streams on one Hailo-8 with the YOLOX detector — the achievable per-stream FPS must be measured. Load to validate: 6 × door @5–8 fps + 2 × saloon @~10 fps. **Owned by** the bench plan (see related test case).

## Self-evaluation against goal

- [x] Uses exactly 8 cameras across 6 cars
- [x] Serves the hybrid (flow + occupancy) goal, flow primary
- [x] Works within shared-CCTV placement constraint
- [x] Sized for single-Hailo-8 concurrent inference (low-FPS bias)
- [x] Defines APC reconciliation for accuracy
- [ ] FOV per-car validity — pending GA crop + CCTV mount list
- [ ] FPS ceiling — pending bench measurement
