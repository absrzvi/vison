# Epic-11 Admin/Identity Shell — WDS Coherence Review

**Agent:** Freya (WDS UX Designer) ✨
**Date:** 2026-06-15
**Type:** Brownfield retroactive coherence review (Built + Not designed)
**Scope:** The Epic-11 admin/identity surface reviewed as ONE unified shell — Login, logout, role-gated nav (AppShell), Users (S2), Profile (S3), Alert Classes (S4), Configuration (S5).
**Method:** Reviewed the shipped, browser-verified screens side-by-side against the `--obb-*` dark-ops design system and WDS coherence principles. No code changed — this is a findings doc; each finding maps to a candidate follow-up story.

> **Context.** Each Epic-11 story deliberately shipped a *minimal functional, theme-correct, browser-verified* screen so the backend critical path wasn't gated on design. The epic named this WDS pass as the tracked exit step — designing the shell as a whole rather than five screens grown independently. That's what this is. None of the 12 existing UX scenarios cover admin/identity, so in WDS terms this surface is **Built + Not designed**; this review is the retroactive coherence layer, by design pragmatic (not full page specs).

---

## What's coherent already (the good)

The screens were built by mirroring each other, so the bones are sound:

- **Consistent three-state contract.** Users / Alert Classes / Configuration all render loading / error / populated with matching `data-testid` patterns and a `runAction → refetch` server-truth idiom. This is the right pattern and it's applied uniformly.
- **One auth/gating model.** Every admin screen sits behind `RequireAdmin` (route) + a `role === 'admin'` nav gate, with the server enforcing `require_role("admin")`. Double-gated, consistent, correct.
- **Token discipline holds.** All five screens use `--obb-*` tokens — no hex literals. Severity colours (`--obb-sev-normal`/`--obb-sev-critical` for the Alert Classes pill) are used correctly.
- **Shared error-envelope handling.** The API clients (`api/users.js`, `api/alertClasses.js`, `api/config.js`) all use the same `_send` helper shape (`authHeaders` + `handle401` + `(await res.json())?.detail?.detail`).

This is a solid foundation. The findings below are *coherence polish*, not rework — none block anything.

---

## Findings (prioritized) — each is a candidate follow-up story

### 🔴 P1 — High value, clear UX gap

**F1 — No sign-out control anywhere in the shell.**
`AuthContext` exposes `logout()` (and wires it to the 401 auto-logout), but **nothing renders it** — a signed-in operator has no way to deliberately sign out. The header (`AppShell`) shows the ÖBB brand, the alert-hook, a ⚙ preferences button, and "Control Centre", but no user menu / sign-out.
*UX:* add a user affordance in the header (username + role + Sign out), ideally a small menu anchored where the ⚙ lives. This also gives the identity a consistent home (today `username`/`role` only appear on the Profile screen).
*Trace:* `AppShell.jsx` header, `AuthContext.logout`.

**F2 — Two settings homes with an unclear split (Profile screen vs ⚙ gear-modal).**
Operator preferences live in **two** places: the Profile screen (alert + staleness thresholds, server-backed) and the ⚙ gear-modal in the header (`OperatorPreferences`, which still hosts `unattended_threshold_min`, localStorage-only). This split was a deliberate S3 clash-resolution (D5), but to a user it's two doors to "settings" with no signposting. The WDS-coherent end state is **one settings home**: fold the gear-modal controls into Profile once `unattended_threshold_min` gets server persistence (tracked: E11S3-D5), and make ⚙ either open Profile or be retired.
*Trace:* `AppShell.jsx` ⚙ button + `OperatorPreferences`, `Profile.jsx`. Depends on E11S3-D5 (server column).

### 🟠 P2 — Consistency / craft

**F3 — Three copy-pasted button systems (`.users-btn`, `.alert-classes-btn`, `.configuration-btn`).**
The three admin screens each define their own near-identical button, table, error, and muted-text classes. They're visually consistent *today* only because they were copied carefully — they will **drift** the moment one screen is restyled. The design-system-correct move is a shared admin primitive set (`.obb-admin-table`, `.obb-btn`, `.obb-btn--primary`, `.obb-pill`) extracted to one place (or a small set of shared components: `AdminTable`, `AdminButton`), and the three screens consume it. This is the single highest-leverage consistency fix.
*Trace:* `Users.css`, `AlertClasses.css`, `Configuration.css` (all three duplicate the same ~6 class roots).

**F4 — Inconsistent admin-screen headers + page titles.**
Users → "Users" + a "+ New user" action button in the header row; Alert Classes → "Alert Classes" (no action); Configuration → "Configuration — confidence thresholds" + a descriptive paragraph. Three different header treatments for three peer screens. Standardise an admin-page header pattern: `<h2>` title + optional one-line description + optional right-aligned primary action, applied identically.
*Trace:* the `__header`/`__title` blocks in each admin `.jsx`.

**F5 — Edit affordances differ across the table screens.**
Users mutates via row action *buttons* (Make admin / Deactivate / Reset password) + a create *modal*; Alert Classes via a single per-row *toggle* button; Configuration via an inline *numeric input + Save* per row. Three different in-table editing models. Some divergence is justified (a threshold is a value, a role is a toggle), but the *visual language* of "an editable row" should be unified — e.g. a consistent actions-column placement, consistent Save/confirm affordance, consistent disabled/dirty states.
*Trace:* the `<tbody>` row renderers in `Users.jsx`, `AlertClasses.jsx`, `Configuration.jsx`.

### 🟡 P3 — Polish / nice-to-have

**F6 — Login screen is functional-minimal, visually unbranded.**
`Login.jsx` is a bare card (title + two fields + button). It's the first impression of the whole product and the only fully-public screen. A light brand pass (ÖBB logo lockup, the dark-ops surface treatment the rest of the app uses, a touch of vertical rhythm) would align it with the operational dashboards it gates. Low urgency — it works and is theme-correct — but it's the highest-visibility unstyled surface.
*Trace:* `Login.jsx` + `Login.css`.

**F7 — Profile avatar is a coloured initial; identity treatment is ad-hoc.**
The Profile screen invents an avatar (first initial in a circle) that appears nowhere else. If F1 adds a header identity affordance, the avatar/initial treatment should be defined *once* and reused (header + Profile), not invented per-screen. (This was flagged at S3 close as "Freya owns the identity treatment at epic-close" — this is that moment.)
*Trace:* `Profile.jsx` `.profile-avatar`.

**F8 — "Last changed by / at" is shown on Alert Classes but not Configuration.**
Alert Classes shows who toggled a class and when; Configuration (which also records `updated_by`/`updated_at` server-side) shows neither. For two peer admin-config screens, the audit-visibility should be consistent — either both show last-changed-by, or neither does inline.
*Trace:* `AlertClasses.jsx` (shows it) vs `Configuration.jsx` (doesn't surface the columns it has).

---

## Recommended sequencing (if these become stories)

1. **F1 (sign-out + header identity)** — real functional gap, small, high value. Do first.
2. **F3 (shared admin primitives)** — do before any restyle, so F4/F5/F6 build on one system instead of three. The enabling refactor.
3. **F4 + F5 + F8** — the table/header/edit-consistency cluster, on top of F3.
4. **F2** — fold settings into one home; gated on E11S3-D5 (server-persist `unattended_threshold_min`).
5. **F6 + F7** — brand/identity polish; lowest urgency.

These would fit an "Epic-8-style" UI-hardening batch, or a small dedicated "admin shell coherence" epic. None are blockers; the shell is shippable as-is.

## Also fold in here (tracked elsewhere, belongs to this surface)

- **E11S4-D5** — the E10-S3 critical-alert SOP + routing matrix still document operating the kill-switch via `curl` + `X-Admin-Key`; that path 401s now (it's the Alert Classes admin screen under JWT). Rewrite the SOP's kill-switch-operation section to point at the UI. This is the documentation half of the same admin surface and was explicitly slated to pair with this UX pass.

---

## Design-system note

The `--obb-*` token set (74 tokens in `colors_and_type.css`) is healthy and consistently used. The gap is not tokens — it's **component-level** primitives: the admin surface re-implements the same table/button/pill/field at the CSS level three times. Extracting a shared admin component layer (F3) is the one structural design-system action worth taking; everything else is screen-level polish on top of it.
