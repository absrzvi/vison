# ÖBB Railnet Portal — Design System

The visual & content system for **ÖBB Railnet**, the on‑board Wi‑Fi captive portal and infotainment landing experience offered to passengers on ÖBB *railjet*, *railjet regio*, and *railjet night* trains operated by Austrian Federal Railways (Österreichische Bundesbahnen, ÖBB‑Personenverkehr AG).

This system covers:

- **The captive WLAN onboarding flow** that appears when a passenger joins the free on‑board Wi‑Fi (`OEBB` / `railnet` SSID). Three core screens: welcome carousel → terms & connect → connected.
- **ÖBB Smart Rail** — the dark‑mode operations product family used by conductors, drivers, technicians, bistro staff, and control‑centre operators. Shares the ÖBB house red but lives in an industrial dark UI with a 6‑step graphite ramp, deep ÖBB blue, and a 5‑step severity scale.
- The supporting marks for `ÖBB railnet`, `ÖBB railnet regio`, and `ÖBB railnet night`.
- Typographic, colour, motion, and tone rules so future portal screens, in‑page banners, marketing surfaces and admin tooling stay on‑brand.

The portal exists in two compositions:
1. **Railnet variant** — the longer onboarding (carousel: *Do you know Railnet?* → *How to get to Railnet?* → *Top content for you* → T&C → *Connection succeeded*).
2. **Without‑Railnet variant** — a slim two‑step path (T&C → *Connection succeeded*) for routes/consists without on‑board content.

Primary languages: **German (Sie‑form)** and **English**. Five additional language slots are reserved (`Language 3 / 5 / 6 / 7 / 8` in the source spec, typically IT / FR / HU / CS / SK depending on route).

---

## Sources of truth

These files were given to me directly. Anyone re‑opening this system later should re‑acquire them if they are missing.

- **`current-portal-design/`** — local mounted folder containing the existing copy spec and logos. Mirrored into `_sources/` (text extracts) and `assets/logos/`, `assets/icons/` (visual assets).
  - `WIFI PAGE Railnet - CNA portal_v1.1.xlsx` — the canonical screen‑by‑screen copy (DE + EN) for the full Railnet captive portal flow.
  - `WIFI PAGE without Railnet - CNA portal_v1.1.xlsx` — copy for the slim flow.
  - `ENGLISCH DSGVO WLAN, final_V2.docx` — Article 13 GDPR notice (EN).
  - `Information nach der DSGVO WLAN, final_V2.docx` — DSGVO Datenschutzinformation (DE).
  - `Nutzungsbedingungen adaptiert.docx` — Terms of use (DE).
  - `Logos & Symbole/` — official wordmarks for `railnet`, `railnet regio`, `railnet night`, plus two service icons (`Filme-und-Serien_red.svg`, `icons_Services_im_Zug.svg`) and an info icon.
- **`uploads/`** — same three icons surfaced via the upload pane (`Filme-und-Serien_red.svg`, `icons_Services_im_Zug.svg`, `Info_icon.png`).

No Figma file, screenshots of the live portal, or production codebase were provided — the UI kit in `ui_kits/railnet_portal/` is a clean reconstruction from the copy spec, logo system, and ÖBB's well‑established public brand guidelines (red `#E2002A`, humanist sans). **The most important open question is whether the live portal layout matches what is built here.** If you have access to the production CNA portal, please share a screenshot so the UI kit can be matched pixel‑for‑pixel.

---

## Index

| File / folder | What's in it |
|---|---|
| `README.md` | This document — brand overview, content & visual foundations, iconography. |
| `colors_and_type.css` | All CSS custom properties — colour tokens, type ramp, radii, spacing, shadows. |
| `fonts/` | Bundled web fonts (currently CDN imports — see Typography below). |
| `assets/logos/` | `ÖBB railnet`, `railnet regio`, `railnet night` wordmarks (PNG, JPG, SVG). |
| `assets/icons/` | Brand service icons (films‑and‑series, on‑board services, info). |
| `preview/` | Small standalone HTML cards that populate the Design System tab. |
| `ui_kits/railnet_portal/` | Interactive React recreation of the existing 3-screen captive WLAN flow. |
| `ui_kits/railnet_passenger/` | Interactive prototype of the **proposed v2 portal** with coach-occupancy guidance panel (10 states). |
| `ui_kits/conductor_app/` | Smart Rail conductor handheld — dark‑mode operations kit (5 scenarios). |
| `_sources/` | Extracted copy from the supplied XLSX/DOCX files, for reference. |
| `SKILL.md` | Skill manifest so this system is usable from Claude Code. |

---

## Content fundamentals

### Voice & tone

ÖBB writes like a **polite Austrian conductor**: precise, courteous, and informative — never chatty or clever. The portal is a service touchpoint, not marketing copy.

- **Sie‑form, always.** German copy uses the formal *Sie / Ihr / Ihnen* — never *du*. The English mirror keeps the same register ("please", "you may", "to your disposal").
- **Short, declarative sentences.** Copy is split across small cards (carousel slides), each one title + one or two lines of body. No paragraphs that overflow the viewport.
- **Title case for buttons and screen titles, sentence case for body.** Buttons in the spec are UPPERCASE for the connect action: `CONNECT` / `VERBINDEN`. Soft actions are normal case: `open railnet` / `railnet öffnen`, `WiFi Connect` / `Wlan Verbinden`.
- **Service before brand.** Almost every screen leads with a benefit (*"Free WLAN on the train"*, *"Top content for you"*, *"Connection succeeded"*) and references the brand second.
- **Bilingual by default.** Every customer‑facing string ships DE + EN minimum; route‑dependent locales (IT/FR/HU/CS/SK) plug into reserved slots.

### Casing & punctuation

- German: standard Duden capitalisation (`WLAN`, `Railnet`, `Filme und Serien`). Compound nouns stay closed (`Onboard Portal`, `Bandbreitensteuerung`).
- `WLAN` (DE) and `WiFi` (EN) are both correct — match the language. `Wi‑Fi` with the hyphen is **not** used in this system; the spec uses `WiFi` and `WLAN`.
- `railnet` is lowercase when written as the wordmark (matches the logo). `Railnet` is acceptable in running prose where it would otherwise start a sentence (*"Kennen Sie das Railnet?"*).
- Exclamation marks are reserved for genuine moments of delight: `Verbindung erfolgreich!`, `Viel Spaß beim Surfen!` — never on a button or a title that is purely informational.
- No emoji. No leetspeak. No ALL CAPS body copy.

### Specific examples from the source spec

> **Title:** *Do you know Railnet?* / *Kennen Sie das Railnet?*
> **Body:** *The onboard portal on railjets with infos about the journey, services and entertainment*

> **Title:** *Free WLAN on the train* / *Gratis WLAN am Zug*
> **Body:** *By connecting to our free WiFi, you agree to the terms of use.*

> **Title:** *Connection succeeded* / *Verbindung erfolgreich!*
> **Body:** *Everything you need to know about your journey, services onboard and Infotainment can be found in our onboard portal railnet. Have fun surfing the web!*

### Legal copy

GDPR / DSGVO blocks are the only place where the writing becomes long‑form. There it follows standard Austrian legal style: full sentences, defined terms, references to article numbers (`Art. 6 Abs. 1 lit. a und f DSGVO`). It is meant to be readable but is not "casual" — keep it set in body type, well‑leaded, with semantic headings.

---

## Visual foundations

### Personality

Calm, **utilitarian, transit‑grade**. Think airport signage and the digital displays inside a railjet, not a consumer SaaS marketing site. The portal sits behind a captive‑portal request from the OS — when a passenger sees it, they have probably been waiting ten seconds and want to know two things: *am I online? what can I do?* Design choices must answer those two questions first.

### Colour

The system is **monochromatic + one strong accent**. ÖBB red is reserved for primary actions, the `ÖBB` lockup, and the highest‑priority status messages (success, error). Everything else is white surfaces with a graphite‑to‑silver gray ramp.

- `--obb-red: #E2002A` — the ÖBB house red. Used on logo, primary CTA fills, top status bar.
- `--obb-red-press: #B70022` — pressed/active state.
- `--obb-ink: #383838` — body copy.
- `--obb-graphite: #58585A` — the dark half of the `railnet` wordmark gradient (`r‑a‑i‑l`).
- `--obb-silver: #9C9E9F` — the light half of the wordmark gradient (`n‑e‑t`) and the secondary text colour.
- `--obb-fog: #E8E8E8`, `--obb-bg: #F5F5F5` — neutral surfaces.

Backgrounds are predominantly **white or very near‑white**. Full‑bleed photography is *not* part of the captive‑portal aesthetic — when imagery does appear (the `Filme und Serien` tile, future content cards), it is a single iconographic SVG silhouette in red on a white card, not a photograph.

### Typography

ÖBB's corporate typeface is **ÖBB Iconic** (proprietary). For public web/portal surfaces the brand permits **Verdana** as a system fallback and increasingly uses humanist sans webfonts.

> **⚠ Font substitution:** No ÖBB Iconic / Verdana licence ships with this project. The system currently substitutes **Open Sans** (very close metrics to Verdana, broad multilingual coverage) loaded from Google Fonts. **If you have access to the licensed ÖBB Iconic or Frutiger files used by the live portal, please drop them into `fonts/` and update `colors_and_type.css` — the rest of the system is metric‑compatible.**

Type ramp is short and quiet — five sizes from 12 px to 28 px on mobile portal screens. The captive portal is rendered inside the OS captive‑network mini‑browser, which is small (typically ≤ 414 px wide on iOS, ≤ 360 px on Android), so the ramp is tuned for that viewport.

### Spacing & layout

- **8 pt base grid.** Spacing tokens step `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`.
- The captive portal is a **single phone‑width column** centred on screen. On wider viewports the column is letterboxed against a white background (no full‑bleed hero).
- **Fixed elements:** the language picker pinned top‑right of the welcome shell; the primary CTA pinned to the bottom of the connect screen with a 16 px safe margin.

### Corner radii

Soft but not pillowy. Buttons and inputs use **8 px**; cards use **12 px**; the language picker chip uses **999 px** (full pill). No 0‑radius hard edges except in the GDPR / Terms full‑sheet view, where the form is set in a rectangular content well.

### Borders

`1px solid var(--obb-fog)` on cards and dividers. Buttons have no border by default — the primary button is a filled red rectangle. The secondary "Open Railnet" button on the success screen is a 1.5 px red outline button with red label.

### Shadows & elevation

Very restrained. Only two:

- `--shadow-card`: `0 1px 2px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.06)` — for the white content card floating on the off‑white app background.
- `--shadow-cta`: `0 2px 6px rgba(226,0,42,.30)` — a subtle red‑tinted lift under the primary CTA so it reads as actionable even when the device is at low brightness in a sunny train carriage.

No inner shadows, no protection gradients, no glassmorphism, no backdrop blur.

### Motion

The captive portal is on a budget — both pixels and CPU. Transitions are short and functional.

- **Carousel paging:** 240 ms ease‑out horizontal slide between welcome cards. No bounce, no parallax.
- **Button press:** 100 ms scale to 0.98 + colour swap to `--obb-red-press`. Spring‑less.
- **Connecting spinner:** a thin red ring rotating at 1.2 s linear, 1.5 px stroke. Replaces the connect button while the request is in‑flight.
- **Success reveal:** the success screen fades and y‑translates 8 px upward over 280 ms once the connection is confirmed.
- No autoplay carousels. No lottie illustrations. No looping background loops.

### Interactive states

| State | Effect |
|---|---|
| Hover (desktop) | Primary button → background `--obb-red-press`. Secondary button → fill `--obb-red-tint` (5% red). Text links → underline. |
| Press / active | Scale 0.98 + 100 ms. |
| Focus visible | 2 px `--obb-red` outline at 2 px offset (keyboard focus only). |
| Disabled | 40% opacity, no pointer events. |
| Loading | Spinner replaces label; button width preserved. |

### Transparency & blur

Effectively unused. The only place a semi‑transparent layer exists is the language‑picker dropdown, which uses an opaque white surface with the standard card shadow. No backdrop‑filter.

### Imagery

The brand uses **flat, single‑colour iconographic SVGs** for content categories (films & series, on‑board services, info). They are drawn red on white. Photography exists in the wider ÖBB universe but is **not part of this captive‑portal subsystem** — keep this kit photo‑free unless a future content tile explicitly calls for it.

---

## Iconography

See `ICONOGRAPHY` section below in detail.

### Approach

- ÖBB does **not** ship a public icon font for the railnet portal. The supplied icons are individual hand‑drawn SVGs from the ÖBB content production system — flat, single‑path, single‑colour (red `#E2002A`), ~32–52 px square viewBoxes.
- For everything **outside** the supplied set (close icon, chevrons, wifi, language, checkbox, spinner) the system uses **Lucide** from CDN — same stroke weight family (2 px round‑joins) and visual register as the existing assets when set in red. **This is a substitution; if ÖBB has an official portal icon library, swap it in.**
- **No emoji.** No unicode pictographs used as icons. No Material/FontAwesome.

### Bundled brand icons (`assets/icons/`)

| File | Use |
|---|---|
| `Filme-und-Serien_red.svg` | Content category — films, series, on‑board video. |
| `icons_Services_im_Zug.svg` | Content category — on‑board services (catering, info). |
| `Info_icon.png` | Generic information / help marker. PNG, black; tint with CSS where possible or replace with `Lucide#Info`. |

### CDN icon set

```html
<script src="https://unpkg.com/lucide@latest"></script>
```

Used inline as `<i data-lucide="wifi"></i>` etc., then `lucide.createIcons()` after mount. Stroke 2, size 24 default, colour inherits `currentColor`.

---

## Quick start

```html
<link rel="stylesheet" href="colors_and_type.css" />
```

Then build with the tokens — `var(--obb-red)`, `var(--font-display)`, `var(--space-4)`, `var(--radius-card)`, `var(--shadow-card)`. See `ui_kits/railnet_portal/index.html` for a full reference assembly.

For **operations / dark‑mode** surfaces (conductor app, control centre, etc.), add `class="obb-dark"` to the body — the semantic aliases (`--fg-*`, `--bg-*`, `--border-*`) remap to the operations palette. Use the surface ramp (`--obb-surface-0` deepest → `--obb-surface-5` highest), the severity scale (`--obb-sev-critical/high/medium/advisory/normal`), and `--obb-blue` for chrome accents.

```html
<body class="obb-dark">
  <!-- conductor app, dashboards, anything 24/7 ops -->
</body>
```

See `ui_kits/conductor_app/index.html` for the full pattern: dark surfaces, ÖBB‑blue app headers, severity‑coded alert banners, train‑coach diagram, vestibule heatmap, PA panel, and unified alert list.
