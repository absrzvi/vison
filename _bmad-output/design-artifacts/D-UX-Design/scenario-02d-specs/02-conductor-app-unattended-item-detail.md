# Page Spec — Conductor App: Unattended Item Detail Panel

**Scenario:** 02d — Conrad Investigates an Unattended Bag
**Interface:** Conductor App (handheld)
**State:** Unattended Item Alert — Detail Panel
**Base state:** Unattended Item Alert Active — `01-conductor-app-unattended-item-alert.md`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Conrad taps the unattended item alert banner, the app opens a full-screen detail panel. This panel gives him everything he needs to make a triage decision without leaving his seat:

1. A camera still-frame of the item, captured at detection
2. Contextual timeline — when the item appeared, when the area emptied
3. Action options: PA announcement, or immediate escalation to Claudia

The still-frame is event-gated: it is a single image captured by Hailo-8 at the moment of detection, embedded in the alert payload. Conrad cannot request a new frame, cannot access other cameras, and cannot browse camera feeds. Camera access is scoped entirely to this one detection event.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  ALERT BANNER        │────▶│  DETAIL PANEL        │────▶│  PA SENT STATE       │
│  (spec 01)           │     │  (this spec)         │     │  (post-PA action)    │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
                                        │
                                        ▼ (Conrad taps Escalate)
                             ┌──────────────────────┐
                             │  ESCALATION FLOW     │
                             │  (standard form,     │
                             │   pre-filled)        │
                             └──────────────────────┘
                                        │
                                        ▼ (Conrad taps Resolved)
                             ┌──────────────────────┐
                             │  RESOLUTION LOG      │
                             │  (alert closed)      │
                             └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Alert banner | Detection + timer | Conrad taps banner |
| **Detail panel** | Tap on banner | Conrad sends PA / escalates / marks resolved |
| PA sent | Conrad sends PA | Conrad marks resolved / escalates |
| Escalated | Conrad taps escalate | Standard escalation flow takes over |
| Resolved | Conrad selects resolution option | Alert removed from feed, logged |

---

## State: Detail Panel

> **The Story:** Conrad taps the banner. A still-frame loads in 2 seconds — dark backpack, floor of the coach 6 vestibule, no one nearby. Below the image: "Item appeared 8 min ago. Area empty for 7 min. No return." He scans the image. Standard bag, standard placement. Not unusual. He taps "PA — owner request." The pre-filled message appears. He reads it — generic, no alarm words. He hits send. The PA fires across the train. He pockets his phone and walks.

### New Element: `ca-unattended-item-detail`

**OBJECT ID:** `ca-unattended-item-detail`
**Type:** Full-screen modal panel
**Entry:** Tap on `ca-alert-banner` (unattended item variant) or `ca-unattended-item-feed-item`

#### Layout (top to bottom)

---

**1. Panel header**

| Element | Content |
|---------|---------|
| Title | "Unattended item" |
| Sub-title | "Coach 6 · Vestibule · [N] min stationary" |
| Header background | `--color-review` (steel blue) strip — matches alert banner colour |
| Back navigation | "← Alerts" — returns to home screen, alert remains active |

---

**2. Still-frame image — `ca-unattended-item-still`**

**OBJECT ID:** `ca-unattended-item-still`

| Property | Value |
|----------|-------|
| Source | Hailo-8 JPEG capture at detection moment — embedded in alert payload |
| Load target | ≤ 3 seconds from panel open |
| Loading state | Skeleton placeholder with "Loading image …" label during fetch |
| Failure state | "Image unavailable" placeholder with camera-off icon + "Walk to location to assess" guidance |
| Timestamp overlay | Bottom-left corner: "Captured [HH:MM:SS]" in white text on semi-transparent dark background |
| Privacy scope label | Bottom-right corner: "Event image only" in muted white — reminds Conrad (and any observer) that this is a single event capture, not a live feed |
| Aspect ratio | 16:9, full panel width |
| Tap to enlarge | Tap image → full-screen zoom view; pinch-to-zoom supported; back swipe returns to detail panel |

**Camera access model:** The still-frame is captured by Hailo-8 at detection and stored in the Nomad Digital alert payload. Conrad does not have a camera connection — he is viewing a stored image. No new frame can be requested. No other coach cameras are accessible from this panel.

---

**3. Context timeline — `ca-unattended-item-timeline`**

**OBJECT ID:** `ca-unattended-item-timeline`

A compact 2–4 line chronological summary beneath the image:

| Timestamp | Event |
|-----------|-------|
| [HH:MM] | Item first detected in frame |
| [HH:MM] | Last passenger departed area |
| [HH:MM] | Alert fired (timer threshold reached) |
| Now | [N] min since alert — area still empty |

Visual treatment: small monospace timestamps · `--text-secondary` · 13sp · left-aligned. No icons — text-only for maximum scannability.

**Last known location context (if available from coach diagram):**
Below the timeline, a single line: "Coach 6 · Vestibule — between doors 2 and 3" (derived from Hailo-8 zone mapping). Shown only if zone resolution is available; omitted if only coach-level location is known.

---

**4. Action strip — `ca-unattended-item-actions`**

**OBJECT ID:** `ca-unattended-item-actions`

Three actions, presented as full-width tappable rows (not buttons — large touch targets, legible while walking):

---

**Action A: PA — owner request — `ca-unattended-item-pa-action`**

**OBJECT ID:** `ca-unattended-item-pa-action`

| Property | Value |
|----------|-------|
| Label | "PA — owner request" |
| Icon | Megaphone icon |
| Colour | `--color-review` (matches alert context) |
| Tap action | Opens PA confirmation modal — `ca-unattended-item-pa-modal` |

**PA Confirmation Modal — `ca-unattended-item-pa-modal`:**

| Element | Content |
|---------|---------|
| Title | "Send PA announcement" |
| Pre-filled message (DE) | "Sehr geehrte Fahrgäste, hat jemand im Wagen 6 in der Nähe der Türen ein Gepäckstück liegen lassen? Bitte kommen Sie umgehend zurück." |
| Pre-filled message (EN) | "Attention passengers — has anyone left a bag in coach 6 near the doors? Please return to collect it immediately." |
| Edit | Conrad can edit the message (200 char max) — but the default is deliberately generic: no words like "suspicious," "security," "unattended," or "concern" |
| Language selector | DE / EN / Both (bilingual sequential) |
| Send button | "Send PA" — 56px height, full width |
| Cancel | "Cancel" — dismisses modal, returns to detail panel |

On send: PA fires, modal closes, detail panel shows **PA Sent state** (see below).

---

**Action B: Escalate to Control Centre — `ca-unattended-item-escalate-action`**

**OBJECT ID:** `ca-unattended-item-escalate-action`

| Property | Value |
|----------|-------|
| Label | "Escalate to Control Centre" |
| Icon | Warning shield icon |
| Colour | `--color-warning-amber` (amber — signals higher severity choice) |
| Tap action | Opens standard escalation form (pre-filled — see below) |

**Pre-fill values passed to standard escalation form:**
- Category: "Suspected security threat" (Operational → Claudia)
- Location: "Coach 6 · Vestibule" (auto-filled)
- Severity: "Urgent"
- Details: "Unattended item — stationary [N] min. Area empty. Image attached." (auto-filled, editable)
- Attachment: `ca-unattended-item-still` image automatically attached — Conrad does not need to manually attach the image

Conrad can review and edit the pre-filled form before submitting. Category and location are editable in case his assessment differs from the AI suggestion.

---

**Action C: Mark Resolved — `ca-unattended-item-resolve-action`**

**OBJECT ID:** `ca-unattended-item-resolve-action`

| Property | Value |
|----------|-------|
| Label | "Mark resolved" |
| Icon | Checkmark icon |
| Colour | `--color-secondary` (neutral — lowest visual weight of the three actions) |
| Tap action | Opens resolution selector modal — `ca-unattended-item-resolve-modal` |

**Resolution Selector Modal — `ca-unattended-item-resolve-modal`:**

| Option | Code | When to use |
|--------|------|-------------|
| Owner identified | `OWNER_ID` | Conrad or a passenger physically identified the owner |
| False positive — passenger present | `FALSE_POS_PAX` | Owner was nearby and not detected as departed |
| False positive — item moved | `FALSE_POS_MOVED` | Item was moved by owner between detection and alert |
| No owner found — item removed | `NO_OWNER_REMOVED` | Conrad removed the item (station hand-off or depot) |

On selection: alert removed from feed, event logged with resolution code and timestamp. No further UI shown — Conrad returns to home screen.

---

### PA Sent State — `ca-unattended-item-detail` (post-PA)

After Conrad sends the PA, the detail panel updates in place:

| Element | Change |
|---------|--------|
| Action A (PA) | Replaced by "PA sent — [HH:MM:SS]" confirmation row (non-tappable, green tick icon) |
| Action B (Escalate) | Remains available — Conrad may still escalate if the PA does not resolve the situation |
| Action C (Resolved) | Remains available |
| New element | "Owner has [N] min to return before walking to location" — a soft timer Conrad can use as a personal reference. Not a system countdown, not tied to any automatic action. Counts up from PA send time. |

The soft timer is advisory only — it does not trigger any system action, push notification, or automatic escalation at expiry. It gives Conrad a mental frame for when to start walking, without the system pressuring him.

---

## Interaction Rules

1. The still-frame is loaded from the alert payload cache. If the cache is unavailable (e.g. network interruption between coach and server), the failure state shows immediately — Conrad is not left looking at a spinner for more than 3 seconds.
2. Conrad cannot request a refreshed still-frame. The "Event image only" label confirms this is a snapshot, not a live feed. This is intentional and documented.
3. The PA pre-fill text must never include the words: "suspicious," "security," "unattended" (in the passenger-audible text), "concern," or any synonym that could alarm passengers in coach 6. The word "unattended" appears in Conrad's UI (alert title) but not in the PA broadcast text.
4. If Conrad has already sent a PA and then taps "Escalate," the escalation form auto-fills "PA announcement sent at [HH:MM:SS]" in the details field — this gives Claudia full context.
5. The detail panel remains open if Conrad navigates away (e.g. takes a call). Returning to the Alerts tab shows the active alert; tapping it re-opens the detail panel at the same state.

---

## Design Rationale

**Why event-gated still-frame rather than live camera access?**
Privacy, infrastructure simplicity, and sufficiency. The image captured at detection is the evidence Conrad needs to triage. A live feed would require a persistent camera connection per coach — significant infrastructure, and a significant privacy risk if access controls fail. The event-gated model means Conrad has exactly the evidence the system generated, and nothing more. ÖBB and Nomad Digital do not need to define access control policies for live browsing — the architecture eliminates the need.

**Why "Event image only" label on the still-frame?**
Conrad may be standing in a public vestibule with the phone visible. The label communicates to any observer (and to Conrad himself) that this is not a surveillance view — it is a single captured image tied to a specific event. It is a transparency signal that protects Conrad professionally and operationally.

**Why a soft personal timer after PA, not an automatic escalation countdown?**
Conrad is a 12-year veteran who resents tools that dictate his judgement. A countdown that auto-escalates at expiry removes his decision authority and creates a system that panics on his behalf. A soft advisory timer respects his professional judgement while giving him a useful reference. He decides when to walk and when to escalate.

**Why are action labels full-width rows rather than buttons?**
Conrad will often be reading this panel while standing or walking. Full-width rows with large touch targets (56px+ height) are easier to tap accurately in motion than small buttons. The visual hierarchy (review blue → amber → neutral) communicates priority through colour and position without requiring Conrad to read all three labels before acting.

**Why is the PA pre-fill in German primary?**
ÖBB standard is German primary. The PA is heard by all passengers in the train, not just coach 6. Conrad can switch to English or bilingual from the language selector if his assessment of the passenger mix warrants it.

---

## Accessibility (App UI)

- `ca-unattended-item-still` provides `alt` text: "Camera still-frame — Coach 6 vestibule — [timestamp]" for screen reader users
- `ca-unattended-item-timeline` uses `role="list"` with `role="listitem"` for each timeline entry — screen reader traversal in order
- All action rows minimum 56px height (exceeds 44px minimum — justified by motion-use context)
- PA modal send button minimum 56px height
- Resolution modal options minimum 48px height each

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Camera access model | Event-gated still-frame embedded in alert payload — no live camera, no browsing |
| Still-frame load target | ≤ 3 seconds; failure state at 3s (no indefinite spinner) |
| PA pre-fill content | Generic, no alarm words; German primary; bilingual option available |
| Post-PA behaviour | Soft advisory timer (no auto-escalation) |
| Image auto-attach on escalation | Yes — Conrad does not manually attach; pre-filled and editable |
| Resolution codes | 4 discrete options — logged for analytics and audit |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | What image format and resolution does Hailo-8 produce for the still-frame? JPEG assumed — confirm compression level sufficient for triage at phone screen size. | Nomad Digital ML / Hailo integration |
| 2 | Where is the still-frame stored? Alert payload in Nomad Digital backend assumed — confirm retention policy (how long is the image kept post-resolution?) for GDPR compliance. | Nomad Digital / ÖBB data governance |
| 3 | Can the PA system be triggered from the Conductor App directly, or does Conrad need to use a separate PA handset? If separate handset is required, the PA action in this spec becomes "Copy PA text" rather than "Send PA." | Systems integration / ÖBB onboard systems |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `01-conductor-app-unattended-item-alert.md` | Prior state — alert banner and feed item |
| `03-control-centre-unattended-item-escalation.md` | Claudia's view when Conrad escalates from this panel |
| `2026-05-14-oebb-ux-design-v2.md § Escalate flow` | Standard escalation form (pre-filled by this panel) |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | Base Conductor App spec |
