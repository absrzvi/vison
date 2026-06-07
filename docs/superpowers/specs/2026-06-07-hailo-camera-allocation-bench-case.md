# Bench Test Case — 8-Camera Passenger-Counting Load on One Hailo-8

**Date:** 2026-06-07 | **Agent:** Claude (harness/config) | **Hardware:** Hailo-8 M.2 on R5001C SYS2 (ordered 2026-06-05)
**Related:** [Camera allocation design artifact](../../../_bmad-output/design-artifacts/D-UX-Design/2026-06-07-passenger-counting-camera-allocation.md)
**Detector:** YOLOX (selected 2026-06-05; not yolov8m — AGPL)

---

## Purpose

Validate that a single Hailo-8 can run the hybrid passenger-counting allocation (6 door-line + 2 saloon streams) concurrently at the FPS each role requires, and measure the achievable per-stream ceiling.

## Configuration under test

| Stream group | Count | Mode | Target FPS | Acceptance |
|---|---|---|---|---|
| Door-line counters | 6 | Line-cross / tripwire | 5–8 fps | Sustains ≥5 fps per stream, all 6 concurrent |
| Saloon overheads | 2 | Head detection per zone | ~10 fps | Sustains ≥8 fps per stream, both concurrent |

**Total concurrent load:** 8 streams on one Hailo-8.

## Test procedure

1. Run all 8 streams concurrently with continuous door cameras (per 2026-06-05 decision; gating deferred to Phase 2).
2. Hold for a representative dwell+transit cycle (boarding surge → transit → alighting).
3. Record per-stream sustained FPS, Hailo utilisation, and dropped-frame rate.
4. Validate counting accuracy of door-line streams against **VLAN 8 APC** ground truth at shared thresholds.

## Pass criteria

- [ ] All 8 streams sustain their target FPS concurrently without frame-drop cascade
- [ ] Door-line count error vs APC ground truth within tolerance (target ≤5% per dwell)
- [ ] No thermal throttle of the Hailo-8 over a full cycle
- [ ] Saloon absolute count usable to re-zero cumulative door-flow drift

## Fallback if FPS ceiling is missed

If 8 concurrent streams cannot hold target FPS:
- **Stagger:** activate door streams only during the dwell window (Phase 2 gating brought forward), freeing budget for saloon streams.
- **Reduce:** drop one saloon overhead to 7 streams; the W400 car keeps priority.

## Inputs needed before run

- Per-stream input resolution/framerate from the 3 trip artifacts (2026-06-05)
- YOLOX throughput baseline on Hailo-8
- Confirmed door-camera FOV list (GA 200.102 d crop × CCTV mount list)
