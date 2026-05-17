# ÖBB Railnet Portal — UI Kit

A high‑fidelity, interactive React recreation of the **ÖBB Railnet captive WiFi portal** — the screen that appears when a passenger joins the free on‑board Wi‑Fi on an ÖBB *railjet* train.

Open `index.html` in this folder. The kit boots inside an iOS frame at iPhone size, since the captive portal almost always renders inside the OS mini‑browser when joining a SSID.

## What's modelled

The full **Railnet variant** end‑to‑end:

1. **Welcome carousel** (`PortalWelcome.jsx`)
   - Slide 1 · *Kennen Sie das Railnet? · Do you know Railnet?*
   - Slide 2 · *Wie erreicht man das Railnet? · How to get to Railnet?*
   - Slide 3 · *Top Inhalte für Sie · Top content for you*
2. **Terms & connect** (`PortalConnect.jsx`)
   - Title *Gratis WLAN am Zug*, body legalese, T&C checkbox, primary CTA
3. **Connecting** (in‑place state of `PortalConnect`) — spinner replaces CTA label
4. **Connected** (`PortalConnected.jsx`)
   - Success state with *railnet öffnen* secondary CTA

A **language picker** (`LanguagePicker.jsx`) is pinned top‑right on every screen and toggles all copy DE ↔ EN (extensible to the five other reserved language slots from the source spec).

## What's intentionally faked

- The actual captive‑portal handshake (DHCP, RADIUS, walled garden release) — we just delay 1.6 s and resolve.
- The walled‑garden destination after success — *railnet öffnen* in this kit just loops back to the start of the carousel.
- The dropdown of all 7 languages — only DE and EN are wired to real copy; the other slots show but the copy keys would need translation.

## Files

| File | Component |
|---|---|
| `index.html` | Mounts everything inside an iOS frame. |
| `App.jsx` | Top‑level state machine (`welcome | connect | connecting | connected`) + portal shell. |
| `PortalShell.jsx` | Phone‑width white column, header with logo + language picker. |
| `PortalWelcome.jsx` | The carousel screen. |
| `PortalConnect.jsx` | T&C screen with checkbox + primary CTA. |
| `PortalConnected.jsx` | Success screen. |
| `LanguagePicker.jsx` | Pill picker + flyout. |
| `Button.jsx`, `Carousel.jsx`, `Checkbox.jsx`, `Spinner.jsx` | Atomic primitives. |
| `copy.js` | DE + EN string table sourced verbatim from `_sources/WIFI_PAGE_Railnet.txt`. |

## Source of every string

Every passenger‑facing string in this kit comes directly from `_sources/WIFI_PAGE_Railnet.txt` (extracted from `WIFI PAGE Railnet - CNA portal_v1.1.xlsx`). If a string was missing in one language it is marked `// TODO` in `copy.js`.
