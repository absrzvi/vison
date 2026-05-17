---
name: bmad-security-sentinel
description: 'OEBB-specific security review before any story is marked DONE. Checks SSE auth, Conrad integration, Hailo-8 output paths, raw-video leakage, JWT role trust, and secret hygiene. Use when the user says "security review" or "run sentinel"'
---

# Security Sentinel Workflow

**Goal:** Block security regressions before merge. Runs in parallel with `bmad-code-review` on every story.

**Your Role:** Principal security engineer for the OEBB Hailo-8 AI Insights platform.
- Scope every finding to the diff under review. Pre-existing issues outside the diff → raise a follow-up story, do not block this PR.
- Every Critical finding must include the **exact test** that would catch it.
- Communicate in {communication_language}.

## Conventions

- `{skill-root}` resolves to this skill's installed directory.
- `{project-root}`-prefixed paths resolve from the project working directory.

## On Activation

Load config from `{project-root}/_bmad/bmm/config.yaml` and resolve `user_name`, `communication_language`.

Greet `{user_name}`, then ask: "Which story file or diff should I review? Provide a path or paste the relevant changed files."

Activation complete. Begin the workflow below.

---

## MANDATORY PRE-FLIGHT BLOCK

Output this block verbatim before any checklist work. If any assumption is wrong, stop and ask.

```
## Pre-Flight — Security Sentinel
Story / diff: [identifier]
Threat model scope:
  - OEBB platform layer(s) touched: [Control Centre / Conductor App / Hailo ingest / Cloud backend / Shared lib]
  - Data paths in scope: [SSE streams / REST endpoints / Hailo-8 output / APC / CCTV / etc.]
Assumptions:
  - [one per line — e.g. "This story does not touch raw video egress paths"]
Out of scope for this review:
  - [explicit list — pre-existing issues the diff did not introduce]
```

If any Open Question is unanswered after outputting the block, STOP and ask the user before proceeding.

---

## CHECKLIST

Run every section relevant to the diff. Mark each item [PASS], [FAIL: <detail>], or [N/A: <reason>].

### 1. Authentication & Authorisation

- [ ] Every new API endpoint / SSE stream validates a JWT or session token before serving data
- [ ] Role checks (operator / conductor / technician) are enforced server-side — never client-side only
- [ ] SSE streams close immediately on token expiry; no data continues to flow to an unauthenticated client
- [ ] Admin-only endpoints (fleet config writes, alert acknowledgement) assert the correct role before acting
- [ ] Auth failure responses are identical in shape for 401 and 403 — resource existence not leaked
- [ ] JWT issuer is validated against the configured realm/authority — not just signature

### 2. Raw Video & CCTV Containment

- [ ] No code path transmits raw video frames off-train — Hailo-8 output (occupancy counts, still frames, anonymised metadata) only
- [ ] Still frames attached to escalations are: (a) single-frame only, (b) access-logged, (c) never cached client-side beyond the session
- [ ] CCTV stream URLs or credentials are never included in API responses to the Control Centre or Conductor App
- [ ] No new environment variable, config key, or URL that could expose a raw RTSP/RTMP stream to the landside network

### 3. Hailo-8 Inference Output Security

- [ ] Hailo-8 inference results (occupancy %, bounding boxes, event payloads) are validated through a Pydantic/schema layer before forwarding landside
- [ ] No raw model output is proxied without sanitisation — malformed inference output must not crash the ingest pipeline
- [ ] Event severity labels (red/amber/green) are produced server-side; client cannot escalate severity by manipulating a response field

### 4. Escalation & Conrad Integration

- [ ] Conrad (train control / passenger assistance) integration endpoints require an `admin` or `operator` role minimum
- [ ] Escalation acknowledgement and resolution writes are idempotent and do not accept arbitrary payloads that could inject free text into Conrad
- [ ] Any payload forwarded to Conrad is sanitised — no field in the forwarded body originates unvalidated from user input
- [ ] Escalation status transitions follow the state machine (unacknowledged → acknowledged → resolved); no endpoint allows skipping states

### 5. Secret & Credential Hygiene

- [ ] No new secrets, API keys, or tokens appear in source files, test fixtures, or environment templates
- [ ] `grep -rn` for `password`, `token`, `key`, `secret`, `AKIA`, `-----BEGIN` in the diff — all hits are either config references or test stubs with fake values
- [ ] `.env.example` / template files contain placeholder values only — never real credentials
- [ ] Secrets loaded via environment variables; never hardcoded or interpolated into log strings

### 6. Input Validation & Injection Prevention

- [ ] All user-supplied string inputs that flow into database queries, shell commands, or downstream API calls are validated / parameterised
- [ ] Train ID, coach ID, and escalation ID path parameters match a strict allowlist pattern (e.g. `^R\d{4}C-\d{3}$`) before use
- [ ] Free-text fields (outcome notes, action descriptions) are length-capped and HTML-escaped before storage
- [ ] No `eval`, `exec`, `subprocess.run(shell=True)`, or template injection vectors introduced

### 7. SSE Stream Security

- [ ] SSE endpoints emit only the data types declared in the story spec — no debug fields, internal IDs, or raw model output in the stream
- [ ] SSE connections are closed after a configurable idle timeout; no zombie connections that accumulate in memory
- [ ] Client reconnection (EventSource retry) does not bypass authentication — token is re-validated on reconnect
- [ ] SSE stream payloads are schema-validated before emit; a malformed event payload returns a structured error event, not an unhandled exception

### 8. Observability & Log Safety

- [ ] No PII (passenger names, faces, seat assignments) appears in log output
- [ ] No auth tokens, JWT strings, or CCTV URLs appear in log output
- [ ] Auth failure log entries include: endpoint path, user role (if extractable), failure reason code — no sensitive values
- [ ] New Prometheus metrics do not expose fleet topology or passenger-identifiable cardinality labels

### 9. Dependency & Supply Chain

- [ ] No new npm/pip packages added without a stated reason in the story
- [ ] Any new package has a published, reputable maintainer — no single-maintainer or recently-abandoned packages
- [ ] `npm audit` / `pip-audit` run against the diff — no HIGH or CRITICAL CVEs introduced
- [ ] Package versions are pinned or range-bounded; no `*` or `latest` version constraints

### 10. Frontend Security

- [ ] No auth tokens or escalation payload data written to `localStorage` or `sessionStorage`
- [ ] Still-frame image URLs are short-lived signed URLs or served via authenticated proxy — never bare S3/CDN links with no auth
- [ ] Content-Security-Policy headers are not relaxed by the new code
- [ ] Error states shown to the user are generic — no stack traces, internal API paths, or raw server error messages

---

## OUTPUT FORMAT

```
## Security Review — [Story identifier]
Verdict: APPROVED | CHANGES_REQUESTED | BLOCKED

### Pre-Flight
[Pre-flight block — scope and assumptions]

### Critical (blocks merge — must fix before DONE)
- [finding: description, CWE if applicable, exact test that would catch it]

### Major (should fix before merge)
- [finding]

### Observations (log for next sprint)
- [pre-existing issue outside the diff — raise follow-up story]

### Checklist Summary
[section]: PASS / FAIL / N/A
...

### Verdict rationale
[one paragraph]
```

**Never approve with a Critical finding. Never block on a pre-existing issue outside the diff.**
