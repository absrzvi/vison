---
title: 'Security Sentinel Review Checklist'
validation-target: 'Story diff / changed files'
validation-criticality: 'HIGHEST'
required-inputs:
  - 'Story file or list of changed files'
  - 'Pre-flight block completed and reviewed'
---

# Security Sentinel Checklist

**Block merge if any Critical item is FAIL. Observations are non-blocking.**

## Pre-Flight Gate

- [ ] Pre-Flight block output before any checklist work
- [ ] Scope is limited to the diff — pre-existing issues are logged as Observations only
- [ ] Every Open Question resolved before proceeding

## Auth & Authorisation

- [ ] Every new endpoint / SSE stream validates JWT or session token
- [ ] Role checks enforced server-side
- [ ] SSE streams close on token expiry
- [ ] Admin-only endpoints assert correct role
- [ ] 401/403 responses are identical shape

## Raw Video & CCTV Containment

- [ ] No raw video transmitted off-train
- [ ] Still frames: single-frame, access-logged, not cached client-side
- [ ] No CCTV URLs or credentials in API responses

## Hailo-8 Output

- [ ] Inference results validated through schema before forwarding
- [ ] No raw model output proxied without sanitisation
- [ ] Severity labels produced server-side only

## Escalation & Conrad

- [ ] Conrad endpoints require operator/admin role
- [ ] Payloads forwarded to Conrad are sanitised
- [ ] Escalation state machine respected — no state-skip paths

## Secrets & Credentials

- [ ] No secrets in source files or fixtures
- [ ] Pattern scan (AKIA, BEGIN, password, token) — all hits are stubs
- [ ] No real credentials in .env templates

## Input Validation

- [ ] ID parameters match allowlist patterns
- [ ] Free-text fields length-capped and escaped
- [ ] No shell injection vectors

## SSE Streams

- [ ] SSE payloads schema-validated before emit
- [ ] Idle timeout configured
- [ ] Reconnect re-validates token

## Log Safety

- [ ] No PII in logs
- [ ] No tokens or CCTV URLs in logs

## Dependencies

- [ ] New packages have stated reason and reputable maintainer
- [ ] No HIGH/CRITICAL CVEs introduced

## Frontend

- [ ] No tokens in localStorage/sessionStorage
- [ ] Error states are generic — no stack traces exposed

## Verdict

```
Security Sentinel: {{APPROVED / CHANGES_REQUESTED / BLOCKED}}
Critical findings: {{count}}
Major findings: {{count}}
Observations (non-blocking): {{count}}
```
