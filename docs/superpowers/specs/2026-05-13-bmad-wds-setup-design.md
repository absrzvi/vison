# BMAD + WDS Setup for ÖBB Agent Project

**Date:** 2026-05-13  
**Project:** oebb-agent  
**Goal:** Install BMAD-METHOD + WDS expansion, reorganize existing design artifacts, and set up the project to continue ÖBB design refinement through WDS agents before moving to architecture/implementation.

---

## Context

The `oebb-agent` directory contains in-progress design work for an ÖBB (Austrian rail) multi-app platform:

- `2026-05-13-oebb-ux-design.md` — UX design document
- `2026-05-13-oebb-hailo8-ai-service-design.md` — AI service design
- `2026-05-13-oebb-user-stories.md` — User stories
- `mockups/` — 9 HTML mockups (conductor, technician, driver, bistro, control centre, etc.)

These are treated as **starting-point inputs** to the WDS design process, not completed artifacts.

---

## Target Directory Structure

```
oebb-agent/
├── _bmad/                              # BMAD core framework (installer creates)
│   └── wds/                            # WDS expansion (Saga + Freya agents)
├── _bmad-output/
│   ├── design-artifacts/               # WDS phase outputs
│   │   ├── A-Product-Brief/
│   │   ├── B-Trigger-Map/
│   │   ├── C-UX-Scenarios/
│   │   ├── D-UX-Design/                # ← existing UX docs moved here
│   │   └── G-Product-Development/
│   └── planning-artifacts/             # BMAD planning outputs
│       └── (existing user stories moved here)
├── mockups/                            # HTML mockups (stay in root)
├── project-context.md                  # ÖBB project summary for agents
└── docs/
    └── superpowers/specs/              # Design specs (this file)
```

---

## Installation Steps

### 1. Run BMAD installer

```bash
npx bmad-method install
```

- Creates `_bmad/` with agents, workflows, tasks, config
- Creates `_bmad-output/` with `planning-artifacts/` and `implementation-artifacts/`
- Node.js v20+ required

### 2. Run WDS installer

```bash
npx whiteport-design-studio install
```

- Adds `_bmad/wds/` with Saga and Freya agent definitions, phase workflows, templates
- Creates `_bmad-output/design-artifacts/` with phase subdirectories

### 3. Reorganize existing files

| Source | Destination |
|--------|-------------|
| `2026-05-13-oebb-ux-design.md` | `_bmad-output/design-artifacts/D-UX-Design/` |
| `2026-05-13-oebb-hailo8-ai-service-design.md` | `_bmad-output/design-artifacts/D-UX-Design/` |
| `2026-05-13-oebb-user-stories.md` | `_bmad-output/planning-artifacts/` |
| `mockups/` | stays in root (referenced as design inputs) |

### 4. Create project-context.md

A summary file at the root for BMAD/WDS agents to understand the project without reading all artifacts. Covers:
- Project name and domain (ÖBB rail operations platform)
- Target user roles (conductor, driver, technician, bistro staff, control centre, maintenance)
- Current design stage (UX design + mockups complete, refinement needed)
- Key design decisions already made
- Pointer to existing artifacts

---

## Design Process After Setup

1. **Activate Saga** (WDS Phase 1 agent) — point it at existing docs as inputs, work through design phases
2. **WDS phases produce refined artifacts** in `_bmad-output/design-artifacts/`
3. **Hand off to BMAD architecture workflows** once design phases are complete
4. **BMAD planning artifacts** (PRD, architecture, epics) land in `_bmad-output/planning-artifacts/`

---

## Constraints

- Node.js v20+ and Python 3.10+ required for BMAD
- Existing `.claude/` settings are preserved (not touched by installers)
- `mockups/` stays in root to avoid breaking any relative paths in the HTML files
