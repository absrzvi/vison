# CLAUDE.md

Project-specific behavioral guidelines for the OEBB Smart Rail PoC. These override defaults.

---

## Project Context

Nomad Digital / OEBB Hailo-8 AI Insights-as-a-Service platform. Single Hailo-8 M.2 on R5001C SYS2 (Debian 12 + Docker). Raw video never leaves the train.

**Data sources (VLANs on SYS2):** VLAN 5 CCTV, VLAN 8 APC door counts, VLAN 7 Stadler SNMP, VLAN 3 PIS/FIS, VLAN 6 reservations, VLAN 46–48 bistro, VLAN 12 energy, VLAN 2 ZFR train control.

**Service tiers:** Tier 1 Core Intelligence → Tier 2 Operational Excellence → Tier 3 Experience & Insights.

**Interfaces:** Conductor App, Technician App, Bistro App, Driver Display (onboard); Control Centre Dashboard, Maintenance Dashboard, Analytics & Station View (landside).

**Current phase:** Architecture complete. First dev target: Control Centre Dashboard. Source control: GitLab (use `.gitlab-ci.yml`).

---

## Git & Version Control

- After every major milestone (epic/story batch, ADR, architecture doc, design delivery, skill workflow step), commit relevant files and push to `origin master` — do this automatically, without being asked.
- Stage only files changed in that milestone. Write descriptive commit messages.
- Remote: `https://github.com/absrzvi/vison`

---

## Coding Craft (Karpathy Guidelines)

### 1. Think Before Coding

Before implementing: state assumptions explicitly, ask if uncertain. If multiple interpretations exist, present them — don't pick silently. If something is unclear, stop and name what's confusing.

### 2. Simplicity First

Minimum code that solves the problem. No features beyond what was asked, no abstractions for single-use code, no speculative flexibility. If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

Touch only what you must. Don't improve adjacent code, comments, or formatting. Match existing style. If you notice unrelated dead code, mention it — don't delete it. Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Transform tasks into verifiable goals. For multi-step tasks state a brief plan with per-step verification criteria. Strong success criteria let you loop independently.

---

## Collaboration Preferences

- **No visual companion** during brainstorming or design sessions — work inline in the terminal only.
- **UX topics in party mode:** always invoke Freya, never Sally.
- **Responses:** short and concise; no trailing summaries of what you just did.
- **Comments in code:** default to none; add only when the WHY is non-obvious.

---

## Skills & Workflow

- BMAD skills handle PM/design process. Superpowers skills handle implementation workflow.
- Context7 MCP: use for any library/framework/API documentation lookup — even well-known ones.
- Brainstorm before any creative or feature work. Write plans before touching code on multi-step tasks.

---

## Design Methodology — BMAD + WDS

Two frameworks work together. BMAD handles the full lifecycle; WDS (Whiteport Design Studio) is a design-only expansion module that sits between the PRD and implementation phases.

### Agents

| Agent | Framework | Role | Phases |
|---|---|---|---|
| **Saga** | WDS | Business & Product Analyst | 0–2: Alignment, Product Brief, Trigger Mapping |
| **Freya** | WDS | UX/UI Designer | 3–8: Scenarios, UX Design, Dev, Assets, Design System, Evolution |
| BMAD agents | BMAD | PM, Architect, Dev, Tech Writer | PRD, architecture, epics, stories, implementation |

**Freya replaces Sally.** Always use Freya for UX/design topics — Sally is BMAD's generic UX persona; Freya is the WDS specialist with the full methodology.

### Full Workflow Sequence

```
BMAD:  brainstorming → product-brief → PRD → architecture → epics & stories
                                                    ↓
WDS:        Saga: Phase 0 Alignment
                  Phase 1 Product Brief  →  A-Product-Brief/
                  Phase 2 Trigger Mapping →  B-Trigger-Map/
            Freya: Phase 3 UX Scenarios  →  C-UX-Scenarios/
                   Phase 4 UX Design     →  D-UX-Design/
                   Phase 5 Agentic Dev   →  G-Product-Development/
                   Phase 6 Asset Gen
                   Phase 7 Design System →  D-Design-System/
                   Phase 8 Product Evol.
                                                    ↓
BMAD:  dev-story → quick-dev → implementation → qa → sprint review
```

### WDS Phase Map

| Phase | Agent | Focus | Output folder |
|---|---|---|---|
| 0. Alignment & Signoff | Saga | Stakeholder alignment | — |
| 1. Product Brief | Saga | Vision, positioning, success criteria | `A-Product-Brief/` |
| 2. Trigger Mapping | Saga | User psychology, business goals | `B-Trigger-Map/` |
| 3. UX Scenarios | Freya | 8-question scenario dialog | `C-UX-Scenarios/` |
| 4. UX Design | Freya | Page specs, interactions, design log | `D-UX-Design/` |
| 5. Agentic Development | Freya | AI-assisted dev & testing | `G-Product-Development/` |
| 6. Asset Generation | Freya | Visual and text assets | — |
| 7. Design System | Freya | Component library, design tokens | `D-Design-System/` |
| 8. Product Evolution | Freya | Brownfield improvements | — |

### Design output location

All WDS artifacts live in `_bmad-output/design-artifacts/`. Design tools: Figma (via MCP), Excalidraw (wireframes), Penpot, Stitch.

### Current project position

Architecture complete (BMAD Steps 1–8). Now in WDS Phase 4–5 — Freya owns Control Centre Dashboard UX Design before any coding starts.
