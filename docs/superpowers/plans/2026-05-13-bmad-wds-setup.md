# BMAD + WDS Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install BMAD-METHOD and WDS expansion into the oebb-agent project directory, reorganize existing design artifacts into BMAD's folder structure, and create a project-context.md so WDS agents can immediately pick up the ÖBB design work.

**Architecture:** Run the BMAD installer first (creates `_bmad/` and `_bmad-output/`), then the WDS installer (adds `_bmad/wds/` and `_bmad-output/design-artifacts/`). After installation, move existing docs into the correct BMAD output folders and write a project-context.md summarizing the project for the agents.

**Tech Stack:** Node.js v20+, npx (bmad-method, whiteport-design-studio), PowerShell (file moves)

---

## File Map

| File / Folder | Action | Purpose |
|---|---|---|
| `_bmad/` | Created by installer | BMAD core agents, workflows, tasks |
| `_bmad/wds/` | Created by WDS installer | Saga + Freya agents, WDS phase workflows |
| `_bmad-output/planning-artifacts/` | Created by installer | BMAD planning outputs |
| `_bmad-output/design-artifacts/D-UX-Design/` | Created by WDS installer | WDS phase D outputs |
| `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md` | Moved | Existing UX design doc |
| `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md` | Moved | Existing AI service design doc |
| `_bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md` | Moved | Existing user stories |
| `mockups/` | Stays in root | HTML mockup files (paths must not change) |
| `project-context.md` | Created | ÖBB project summary for BMAD/WDS agents |

---

## Task 1: Check Node.js version

**Files:** None

- [ ] **Step 1: Verify Node.js is v20 or higher**

Run:
```powershell
node --version
```
Expected: `v20.x.x` or higher. If lower, upgrade Node.js before continuing (use `nvm` or download from nodejs.org).

- [ ] **Step 2: Verify npx is available**

Run:
```powershell
npx --version
```
Expected: version string printed (e.g. `10.x.x`). If not found, it ships with npm — reinstall Node.

---

## Task 2: Install BMAD-METHOD

**Files:**
- Create: `_bmad/` (installer creates this)
- Create: `_bmad-output/` (installer creates this)

- [ ] **Step 1: Run the BMAD installer**

From `C:\Users\AbbasRizvi\Documents\oebb-agent`, run:
```powershell
npx bmad-method install
```

When prompted, accept defaults. If asked about project type, select the option closest to "web application" or "general". If asked about output directory, keep the default (`_bmad-output`).

Expected: installer completes without error, prints something like "BMad Method installed successfully".

- [ ] **Step 2: Verify _bmad/ was created**

Run:
```powershell
Get-ChildItem _bmad | Select-Object Name
```
Expected: folder exists and contains subdirectories (agents, workflows, or similar).

- [ ] **Step 3: Verify _bmad-output/ was created**

Run:
```powershell
Get-ChildItem _bmad-output | Select-Object Name
```
Expected: folder exists and contains at least `planning-artifacts/`.

---

## Task 3: Install WDS expansion

**Files:**
- Create: `_bmad/wds/` (installer creates this)
- Create: `_bmad-output/design-artifacts/` (installer creates this)

- [ ] **Step 1: Run the WDS installer**

From `C:\Users\AbbasRizvi\Documents\oebb-agent`, run:
```powershell
npx whiteport-design-studio install
```

Accept defaults when prompted. If asked where to install, keep `_bmad/wds/`. If asked for design artifacts directory, keep the default (`_bmad-output/design-artifacts` or `design-artifacts`).

Expected: installer completes without error, prints success message.

- [ ] **Step 2: Verify _bmad/wds/ was created**

Run:
```powershell
Get-ChildItem _bmad/wds | Select-Object Name
```
Expected: folder exists and contains `src/` and/or `docs/`.

- [ ] **Step 3: Verify design-artifacts phase folders were created**

Run:
```powershell
Get-ChildItem _bmad-output/design-artifacts -ErrorAction SilentlyContinue | Select-Object Name
```
Expected: folders like `A-Product-Brief`, `D-UX-Design`, etc. If WDS put `design-artifacts/` at the root instead of under `_bmad-output/`, note the actual path — it will be used in Task 4.

---

## Task 4: Ensure D-UX-Design folder exists

**Files:**
- Create (if missing): `_bmad-output/design-artifacts/D-UX-Design/`
- Create (if missing): `_bmad-output/planning-artifacts/`

- [ ] **Step 1: Create D-UX-Design folder if WDS did not create it**

Run:
```powershell
New-Item -ItemType Directory -Path "_bmad-output/design-artifacts/D-UX-Design" -Force | Out-Null
New-Item -ItemType Directory -Path "_bmad-output/planning-artifacts" -Force | Out-Null
Write-Host "Folders ready"
```
Expected: "Folders ready" printed. Safe to run even if folders already exist (`-Force` handles that).

---

## Task 5: Move existing design docs into BMAD structure

**Files:**
- Move: `2026-05-13-oebb-ux-design.md` → `_bmad-output/design-artifacts/D-UX-Design/`
- Move: `2026-05-13-oebb-hailo8-ai-service-design.md` → `_bmad-output/design-artifacts/D-UX-Design/`
- Move: `2026-05-13-oebb-user-stories.md` → `_bmad-output/planning-artifacts/`

- [ ] **Step 1: Move UX design doc**

Run:
```powershell
Move-Item -Path "2026-05-13-oebb-ux-design.md" -Destination "_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md"
```
Expected: no error output.

- [ ] **Step 2: Move AI service design doc**

Run:
```powershell
Move-Item -Path "2026-05-13-oebb-hailo8-ai-service-design.md" -Destination "_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md"
```
Expected: no error output.

- [ ] **Step 3: Move user stories doc**

Run:
```powershell
Move-Item -Path "2026-05-13-oebb-user-stories.md" -Destination "_bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md"
```
Expected: no error output.

- [ ] **Step 4: Verify all three files are in their new locations**

Run:
```powershell
Test-Path "_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md"
Test-Path "_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md"
Test-Path "_bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md"
```
Expected: three lines each printing `True`.

- [ ] **Step 5: Verify original files are gone from root**

Run:
```powershell
Test-Path "2026-05-13-oebb-ux-design.md"
Test-Path "2026-05-13-oebb-hailo8-ai-service-design.md"
Test-Path "2026-05-13-oebb-user-stories.md"
```
Expected: three lines each printing `False`.

---

## Task 6: Create project-context.md

**Files:**
- Create: `project-context.md`

- [ ] **Step 1: Create project-context.md at the project root**

Create `C:\Users\AbbasRizvi\Documents\oebb-agent\project-context.md` with this exact content:

```markdown
# ÖBB Smart Rail — Project Context

## Project Overview

**Name:** OEBB Smart Rail  
**Domain:** Austrian rail operations (ÖBB)  
**Stage:** UX design complete, entering design refinement and architecture phase

A Hailo-8 M.2 edge AI platform onboard ÖBB trains powers two AI services:
- **Passenger AI** — real-time occupancy, luggage detection, accessibility detection, passenger guidance
- **Diagnostics AI** — TCMS/SNMP fault ingestion, plain-language fault explanation, cross-correlated door/camera alerts

Both services are surfaced across 7 role-specific interfaces (4 onboard, 3 landside).

---

## User Roles

### Onboard
| Role | Device | Primary AI service |
|---|---|---|
| Conductor / Train Manager | Mobile handheld | Both |
| Onboard Technician | Mobile handheld | Diagnostics AI |
| Bistro / Café Staff | Tablet or handheld | Passenger AI |
| Driver | Cab-mounted display | Both (display only) |

### Landside
| Role | Device | Primary AI service |
|---|---|---|
| Control Centre Operator | Web dashboard | Both |
| Fleet Maintenance Manager | Web dashboard | Diagnostics AI + occupancy |
| Capacity Planner | Web reports | Passenger AI analytics |
| Platform Staff / Station Manager | Tablet or display | Passenger AI |

---

## Current Design Stage

- 8 personas defined
- 57 user stories written (35 use cases)
- Full UX design spec complete for all 7 interfaces
- HTML mockups complete for all 7 interfaces
- AI service architecture designed (Hailo-8 M.2, edge + cloud hybrid)
- **Next:** Refine design through WDS phases, then move to BMAD architecture + implementation planning

---

## Key Design Decisions Made

- Single Hailo-8 M.2 on SYS2 handles all Passenger AI inference onboard
- Diagnostics AI ML models and LLM run landside (cloud), only structured SNMP data processed onboard
- All 7 interfaces share a unified alert severity model (critical / warning / info)
- Conductor app surfaces both AI services in one unified feed — no separate app per service
- Driver display is read-only (no interaction, safety requirement)

---

## Existing Artifacts

| Artifact | Location |
|---|---|
| UX design spec | `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md` |
| AI service design | `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md` |
| User stories (57) | `_bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md` |
| HTML mockups (7) | `mockups/` |

---

## WDS Design Phase Status

| Phase | Folder | Status |
|---|---|---|
| A — Product Brief | `_bmad-output/design-artifacts/A-Product-Brief/` | Not started (derive from existing docs) |
| B — Trigger Map | `_bmad-output/design-artifacts/B-Trigger-Map/` | Not started |
| C — UX Scenarios | `_bmad-output/design-artifacts/C-UX-Scenarios/` | Partial (user stories exist) |
| D — UX Design | `_bmad-output/design-artifacts/D-UX-Design/` | Complete (refine with Saga/Freya) |
| G — Product Development | `_bmad-output/design-artifacts/G-Product-Development/` | Not started |
```

- [ ] **Step 2: Verify the file was created**

Run:
```powershell
Test-Path "project-context.md"
```
Expected: `True`

---

## Task 7: Verify final directory structure

**Files:** None (verification only)

- [ ] **Step 1: Print top-level directory listing**

Run:
```powershell
Get-ChildItem "C:\Users\AbbasRizvi\Documents\oebb-agent" | Select-Object Name, PSIsContainer | Format-Table -AutoSize
```
Expected output includes: `_bmad`, `_bmad-output`, `mockups`, `docs`, `project-context.md`

- [ ] **Step 2: Print _bmad-output subtree**

Run:
```powershell
Get-ChildItem "_bmad-output" -Recurse | Select-Object FullName | Format-Table -AutoSize
```
Expected: shows `planning-artifacts/`, `design-artifacts/D-UX-Design/`, and the three moved markdown files.

- [ ] **Step 3: Confirm mockups are untouched**

Run:
```powershell
Get-ChildItem "mockups" | Select-Object Name
```
Expected: all 9 HTML files still present (conductor-app-v1.html, technician-app-v1.html, etc.)

---

## Task 8: Activate Saga to begin WDS Phase 1

**Files:** None (agent activation instructions)

- [ ] **Step 1: Find the Saga agent file**

Run:
```powershell
Get-ChildItem "_bmad/wds" -Recurse -Filter "*.md" | Where-Object { $_.Name -match "saga" } | Select-Object FullName
Get-ChildItem "_bmad/wds" -Recurse -Filter "*.yaml" | Where-Object { $_.Name -match "saga" } | Select-Object FullName
```
Expected: one or more files with "saga" in the name. Note the path.

- [ ] **Step 2: Activate Saga in your AI IDE**

In Claude Code (or your AI IDE), tell the assistant:

```
Read [path-to-saga-agent-file] and activate as Saga. 
Our project context is in project-context.md. 
Our existing design artifacts are in _bmad-output/design-artifacts/D-UX-Design/. 
Start from Phase 1 (Product Brief) using our existing docs as inputs.
```

Replace `[path-to-saga-agent-file]` with the path found in Step 1.

Expected: Saga introduces itself and begins Phase 1, referencing the existing ÖBB context.
