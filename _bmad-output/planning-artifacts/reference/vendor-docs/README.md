# Vendor Source Documents — Stadler KISS ÖBB (Project L-4550 / 4736)

Authoritative Stadler engineering documents for the DOSTO/KISS 6-car. These are **source of truth** inputs — analysis notes derived from them live in `../../research/`. TLP:Amber where marked; do not redistribute.

| File | Stadler doc | Type | Status / Date | What it gives us |
|---|---|---|---|---|
| `AL_5457087_VLAN-Konzept_KISS-OEBB.pdf` | AL_5457087 _.000 | VLAN Konzept (13 pp) | **In Bearbeitung (draft)** — 2023-07-12 | Authoritative VLAN list + IP schema + inter-VLAN routing matrix |
| `Netzwerk_FIS_L-4550_6-teiler_2023-06-01.pdf` | L-4550 FIS-Netzwerk Funktionsübersicht | Port-allocation diagram (2 sheets) | 2023-06-01 | Per-car, per-switch port map: which Kamera/AFZ/NVR/Sprechstelle on which FIS-switch port |
| `AL_4958944h_IoB-Konzept_KISS-OEBB_FINAL.pdf` | AL_4958944 index h | IoB Konzept (81 pp) | **Freigegeben (released)** — 2023-12-01, TLP:Amber | Full onboard network architecture: topology, IP/services, OBS landside gateway, redundancy, WLAN, CCU/R5001c install, bandwidth budgets |

## Key facts extracted (2026-06-05)

### VLAN map (VLAN Konzept Tabellen 14–22) — confirms CLAUDE.md
2 ZFR · 3 FIS · 5 Video · 6 Reservation(Sitzplatz) · 7 OBS · 8 AFZ(Fahrgastzählung) · 9 Sprechstellen · 12 Energiemessung.
ZFR = Zentraler Fahrgastinformationsrechner. OBS = On-Board System Server. AFZ = Automatische Fahrgast Zählung (= the "APC" of ADR-15).

### IP schema (Tabelle 13)
Base `172.16.0.0/12`. Address bits: static prefix `172.` | **VLAN-ID (5 bits, 1–31)** | **Vehicle-ID (8 bits, 1–255)** | **Device (7 bits, 1–127)**. Subnet mask `255.255.128.0` (mask encodes vehicle but NOT VLAN — intra-VLAN traffic between vehicles is not routed). Explains the `172.18.192.x` camera addressing.

### Device counts (corrections to prior assumptions)
- **Innenkameras: max 59** (VLAN 5, Tabelle 17) — NOT 53. The 53 in the IP-allocation note was unit 4736-101's populated rows; 59 is the design max.
- Aussenkameras: 12 · Video Recorder (NVR): 2 (Wagen B/600 + Wagen A/100 per FIS diagram).
- **AFZ Zählsensoren: 29** (VLAN 8, Tabelle 20). AFZ units appear per-car (A–F) in the FIS diagram.
- FIS: Frontanzeigen 2 · Seitenanzeigen 24 · Bildschirme 56 · Audio Verstärker 12 · ADU 4 · Verpflegungsautomaten 2.
- Sprechstellen: 44 (VLAN 9). Reservationssystem: 6 (VLAN 6).

### Network architecture (IoB Konzept Abbildung 1)
`IOB Netzwerk —[Firewall]— DMZ —[Firewall]— TCMS —[Firewall]— ETCS`. The **firewall is both the inter-VLAN router and the TCMS↔IoB gateway** — anything inference does that consumes TCMS-side signals (door-open from ZFR/Stadler) crosses a firewall boundary.

### Landside egress path (Tabelle 23 — inter-VLAN routing)
- Camera streams (VLAN 5) → TCMS-Netz for IDU display.
- AFZ (8) → ZFR (2). Reservation (6) → ZFR. FIS (3) → ZFR.
- **ZFR (2) → Landside via OBS (7)** — "OBS ist das Gateway für den ZFR". This is the sanctioned derived-event egress path; raw video stays onboard.

### FIS port-allocation diagram — door→camera bridge (partial)
Resolves **camera → FIS-switch → car** binding per car (Kamera Innen / Aussen / AFZ / NVR / Sprechstelle on named switch ports B1/F3/E2 etc.). Still does NOT give physical mount position within the car → **door-level pin still needs GA cross-reference or an on-train walk.** Also surfaces: **Funksensor** (radio sensors, multiple/car), **OBS Reserve** in Wagen F(500)+E(400), Access Points per car.

## Open follow-ups
1. Update `project_oebb_context` / reconciliation note: camera baseline is **59** (design max), 53 was unit-specific.
2. ADR terminology: ADR-15 "APC" = onboard **AFZ** (VLAN 8, 29 sensors).
3. Architecture: capture the **DMZ + firewall boundary** and the **OBS landside-gateway** egress path — affects container map and how inference output reaches cloud-backend.
4. Door→camera mapping: cross-ref FIS port diagram (camera↔switch↔car) with GA `200.102 d` door positions, or confirm on the train walk.
