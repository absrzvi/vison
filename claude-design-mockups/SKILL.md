---
name: obb-railnet-design
description: Use this skill to generate well-branded interfaces and assets for ÖBB Railnet — the on-board WiFi captive portal and infotainment landing for Austrian Federal Railways (Österreichische Bundesbahnen) railjet trains. Contains essential design guidelines, colors, type, fonts, brand assets (logos for railnet / railnet regio / railnet night, service icons), and a high-fidelity UI kit recreating the three-screen captive WiFi flow (welcome carousel, terms & connect, connected).
user-invocable: true
---

Read the `README.md` file within this skill first — it covers the brand context, content fundamentals (formal Sie/Ihr tone, DE+EN bilingual copy, never emoji), visual foundations (ÖBB house red `#E2002A` + monochrome ramp, restrained motion, single-column phone-width layout), and iconography (brand SVGs + Lucide CDN for chrome). Then explore the other available files:

- `colors_and_type.css` — design tokens (colours, type ramp, spacing, radii, shadows, motion). Import this at the top of any new HTML artifact and reference variables via `var(--obb-red)`, `var(--space-4)`, etc.
- `fonts/` — currently empty; the system substitutes Open Sans from Google Fonts (loaded automatically by `colors_and_type.css`). If ÖBB Iconic or Frutiger files are dropped in, update the `@font-face` rule.
- `assets/logos/` — `ÖBB railnet`, `railnet regio`, `railnet night` wordmarks. Use the PNG/JPG for raster; use `OeBB_railnet_night.svg` for dark-background contexts.
- `assets/icons/` — brand service icons (Filme und Serien, Services im Zug, Info).
- `ui_kits/railnet_portal/` — reference interactive recreation of the captive portal. Read `App.jsx` for the state machine; copy individual `.jsx` components into new mockups as needed. Verbatim DE+EN strings live in `copy.js`.
- `preview/` — small specimen cards showing tokens in isolation; useful as visual references when picking values.
- `_sources/` — extracted plain-text from the original XLSX/DOCX briefing docs (canonical screen copy, GDPR/Datenschutz text, terms of use).

If creating visual artifacts (slides, mocks, throwaway prototypes, marketing surfaces), copy assets out of `assets/` and create static HTML files for the user to view. Always link `colors_and_type.css` so the tokens come along. Re-use components from `ui_kits/railnet_portal/` for any captive-portal or on-train screen mockups — do not redraw them from scratch.

If working on production code, copy the asset files and read the rules in `README.md` to become an expert in designing with this brand. The kit is a thin reference; component implementations are intentionally cosmetic.

If the user invokes this skill without other guidance, ask them what they want to build or design, ask a few framing questions (which surface? phone or desktop? DE/EN/other languages? bound by the captive-portal mini-browser viewport?), then act as an expert designer who outputs HTML artifacts or production code depending on the need.
