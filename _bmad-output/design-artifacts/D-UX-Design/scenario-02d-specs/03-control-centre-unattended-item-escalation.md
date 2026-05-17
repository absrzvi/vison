# Page Spec — Control Centre Dashboard: Unattended Item Escalation

**Scenario:** 02d — Conrad Investigates an Unattended Bag
**Interface:** Control Centre Dashboard (web, 1920×1080)
**State:** Escalations Inbox — Unattended Item Escalation from Conrad
**Base state:** Control Centre Dashboard — Escalations Inbox — documented in `2026-05-14-oebb-ux-design-v2.md § Interface 5`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Conrad escalates an unattended item to the Control Centre, Claudia receives the escalation in her Escalations Inbox with the camera still-frame, timeline context, and Conrad's assessment already attached. She does not need to call Conrad or request information — everything she needs to decide on a response is in the escalation payload.

Claudia's role here is coordination and authority: she can loop in ÖBB security, notify the next station, or instruct Conrad to proceed. This spec defines what she sees and what actions she can take.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  ESCALATIONS INBOX   │────▶│  UNATTENDED ITEM     │────▶│  RESOLVED            │
│  (normal)            │     │  ESCALATION DETAIL   │     │  (Claudia resolves)  │
│                      │     │  (Claudia reviews)   │     │                      │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Inbox (normal) | — | Conrad submits escalation |
| **Unattended item escalation detail** | Claudia taps escalation in inbox | Claudia acknowledges / resolves |
| Resolved | Claudia resolves with outcome | Conrad receives push; alert closed on both sides |

---

## State 1 (Baseline): Escalations Inbox — Normal

> Documented in `2026-05-14-oebb-ux-design-v2.md § Interface 5 — Escalations inbox`. Not repeated here.

Key elements from baseline relevant to this state:
- Escalations inbox (right column) — incoming operational escalations, sorted by severity then time
- Status pills: New (pulsing) · Acknowledged · Resolved
- Tap → detail panel with full submission, photo, voice note player, reply/resolve actions

---

## State 2: Unattended Item Escalation — Inbox Entry

When Conrad's escalation arrives, it appears at the top of the inbox (or below any active safety-critical AI-direct escalations) as a new entry:

### New Element: `cc-unattended-item-inbox-entry`

**OBJECT ID:** `cc-unattended-item-inbox-entry`

| Element | Content |
|---------|---------|
| Severity dot | Amber (Urgent) |
| Category icon | Warning shield icon (Suspected security threat) |
| Title | "Unattended item — [Train ID] Coach 6 · Vestibule" |
| Free-text preview | "Stationary [N] min. Area empty. PA sent at [HH:MM]. Image attached." |
| Staff name | "Conrad [surname] · Train [ID]" |
| Time raised | "[HH:MM:SS]" |
| Image indicator | Camera icon — indicates still-frame is attached |
| Status pill | "New" (pulsing amber dot) |

The camera icon in the inbox entry is a quick signal to Claudia that visual evidence is attached before she opens the detail. She knows within 2 seconds of seeing the entry whether she has an image to review.

---

## State 3: Unattended Item Escalation — Detail Panel

### New Element: `cc-unattended-item-escalation-detail`

**OBJECT ID:** `cc-unattended-item-escalation-detail`
**Type:** Right-column detail panel (expands from inbox entry tap — same layout as standard escalation detail)

#### Layout (top to bottom)

---

**1. Header**

| Element | Content |
|---------|---------|
| Title | "Unattended item — Suspected security threat" |
| Train + route | "[Train ID] · [Route] · Currently between [Station A] and [Station B]" |
| Raised by | "Conrad [surname] · [HH:MM:SS]" |
| Status | "New" pill → changes to "Acknowledged" on Claudia's first action |

---

**2. Still-frame image — `cc-unattended-item-still`**

**OBJECT ID:** `cc-unattended-item-still`

Same image as `ca-unattended-item-still` in Conrad's app — rendered at full panel width in the Control Centre detail view.

| Property | Value |
|----------|-------|
| Source | Same Hailo-8 event capture — served from Nomad Digital alert payload |
| Timestamp overlay | "Captured [HH:MM:SS]" |
| Privacy scope label | "Event image only — single capture at detection" |
| Zoom | Click to open in lightbox (full browser viewport); Esc to close |
| No refresh | Claudia cannot request a new frame — same event-gated model as Conrad's view |

---

**3. Context timeline — `cc-unattended-item-timeline`**

**OBJECT ID:** `cc-unattended-item-timeline`

Same timeline data as Conrad's view, presented in table format suitable for a desktop display:

| Time | Event |
|------|-------|
| [HH:MM:SS] | Item first detected in frame |
| [HH:MM:SS] | Last passenger departed area |
| [HH:MM:SS] | Alert threshold reached — Conrad notified |
| [HH:MM:SS] | PA sent by Conrad (if PA was sent before escalation) |
| [HH:MM:SS] | Escalation raised by Conrad |
| Now | [N] min since escalation · Train location: between [A] and [B] |

---

**4. Conrad's assessment note**

The details text Conrad entered (or the auto-filled text) displayed verbatim:

> "Unattended item — stationary [N] min. Area empty. PA announcement sent at [HH:MM:SS]. Image attached."

If Conrad edited the pre-fill text, his edited version is shown. If a voice note was recorded (optional in the standard escalation form), the voice note player appears here.

---

**5. Action strip — `cc-unattended-item-actions`**

**OBJECT ID:** `cc-unattended-item-actions`

Three actions available to Claudia:

---

**Action A: Acknowledge**

| Property | Value |
|----------|-------|
| Label | "Acknowledge" |
| Behaviour | Status changes to "Acknowledged" · Conrad receives push: "Claudia acknowledged — [HH:MM:SS]" · Claudia can then use reply/resolve actions |
| When to use | Claudia has reviewed and is actioning — standard first step |

Acknowledging does not commit Claudia to any specific response. It tells Conrad his escalation has been seen.

---

**Action B: Resolve with outcome — `cc-unattended-item-resolve`**

**OBJECT ID:** `cc-unattended-item-resolve`

| Property | Value |
|----------|-------|
| Label | "Resolve" |
| Tap action | Opens resolve form — outcome text (required, 200 char) + action tags |

**Action tags available for unattended item resolution:**

| Tag | Meaning |
|-----|---------|
| Passenger assisted | Owner returned, situation resolved by Conrad |
| ÖBB security notified | ÖBB security coordination initiated |
| Next station notified | Station staff at next stop alerted to meet the train |
| Item removed from service | Item removed; train continues |
| False positive confirmed | Reviewed and determined not a concern |
| Further investigation required | Situation ongoing — tagged for follow-up |

On resolve: Conrad receives push with Claudia's outcome text and action tags. Alert removed from active escalations on both sides. Logged to escalation history.

---

**Action C: Reply (without resolving)**

| Property | Value |
|----------|-------|
| Label | "Reply to Conrad" |
| Tap action | Opens free-text reply field (200 char) — sends push to Conrad's handheld without closing the escalation |
| When to use | Claudia needs to give Conrad interim instructions ("Hold your position — security team notified") without closing the escalation |

Reply thread is visible in Conrad's Escalations tab detail view.

---

## Claudia's Broader Situational Context

While reviewing the escalation detail, Claudia retains visibility of:
- The live incident feed in the left column — if other alerts are firing on the same train simultaneously, she can see them without closing the detail panel
- The fleet train list — the escalated train's card is flagged with an open escalation badge

She does not need to navigate away from the escalation detail to check the train's broader status.

---

## Interaction Rules

1. The still-frame in Claudia's view is the same event-gated image Conrad sees. Claudia cannot request a live feed or new frame from the Control Centre. This is consistent with the privacy model — no role has live camera browsing access.
2. If a second unattended item escalation arrives for the same train while Claudia is reviewing the first, it appears as a separate inbox entry below the current one. Both remain independently actionable.
3. "Acknowledged" status is shown on Conrad's Escalations tab in real time — he knows Claudia has seen it within seconds of her tapping Acknowledge.
4. Claudia can resolve without acknowledging first — the resolve action sets status to "Resolved" directly. The separate Acknowledge step is available for situations where she needs to signal receipt before she has a resolution.
5. AI-direct escalations (fire, fall, door at speed) remain above Conrad's manual escalations in the inbox sort order regardless of severity — per `2026-05-14-oebb-ux-design-v2.md § Escalations System Summary`.

---

## Design Rationale

**Why does Claudia see the same event-gated still-frame as Conrad?**
Consistency and privacy. Both roles operate within the same access model — the image is evidence of the detection event, not a surveillance tool. Claudia has higher authority than Conrad but not broader camera access. She coordinates response based on the same evidence base Conrad used to escalate.

**Why are action tags used for resolution rather than free text only?**
Resolution codes create structured data for post-incident analysis. ÖBB can review how many unattended item escalations resulted in security involvement vs false positive vs owner return — and use that data to calibrate the Hailo-8 timer threshold. Free text is available for nuance; tags provide the structured layer.

**Why is "Reply without resolving" an explicit action?**
A common failure mode in radio/phone-based escalation systems is that Claudia gives Conrad instructions but the escalation remains visually "open" with no record of her instruction. A reply thread creates an auditable record of Claudia's interim directives within the escalation — useful for post-incident review and for Conrad's situational awareness.

---

## Accessibility (Dashboard UI)

- `cc-unattended-item-inbox-entry` uses semantic list item structure — screen reader navigates escalation list in order
- Still-frame image has `alt` text: "Camera still-frame — [Train ID] Coach 6 vestibule — [timestamp]"
- Status pill colour changes (New amber → Acknowledged → Resolved green) accompanied by text label change — not colour alone
- Action buttons meet minimum 44px height; resolve form text area minimum 44px height

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Camera access model | Same event-gated still-frame as Conrad's view — no live feed for any role |
| Image display | Full panel width in detail; click to lightbox; no refresh |
| Resolution structure | Outcome text (required) + action tags (structured data for analytics) |
| Reply without resolving | Explicit action — creates auditable interim instruction thread |
| Inbox sort position | Below AI-direct escalations; above standard operational escalations at same severity |
| Cross-visibility | Roland sees this in read-only (Claudia's operational escalations visible to Roland per base spec) |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Does ÖBB security notification happen through the Nomad Digital platform (e.g. via Claudia's resolve action) or through a separate ÖBB security system? If separate, the "ÖBB security notified" tag is a manual label, not an automated notification trigger. | ÖBB operations / integration |
| 2 | What is the retention period for escalation records including the attached still-frame? GDPR requires a defined retention policy for images of train interiors. | ÖBB data governance / Nomad Digital legal |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `01-conductor-app-unattended-item-alert.md` | Alert origin — Conrad's notification |
| `02-conductor-app-unattended-item-detail.md` | Detail panel where Conrad escalates — source of the payload Claudia receives |
| `2026-05-14-oebb-ux-design-v2.md § Interface 5` | Base Control Centre spec — escalations inbox base state |
| `2026-05-14-oebb-ux-design-v2.md § Escalation resolution flow` | Base resolution flow this spec extends |
