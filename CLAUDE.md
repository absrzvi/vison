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
