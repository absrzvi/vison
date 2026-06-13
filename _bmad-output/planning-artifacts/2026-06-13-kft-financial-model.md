# Kft Financial Model — AI Passenger-Analytics SaaS to ÖBB

**Date:** 2026-06-13
**Scope:** Hungarian company (Kft) P&L only — Abbas's personal economics excluded by design (he is an arms-length Nomad employee with no Kft equity/IP; see [venture structure](#structural-assumptions)).
**Status:** Working model. Numbers below the line marked *"honest"* fold in an adversarial cost review; numbers marked *"rosy"* are the naive fixed-cost-dilution model. **Several inputs are still estimates — see [§ Costs the model does not yet capture](#costs-the-model-does-not-yet-capture).**

This is the financial backbone for two negotiations: the **ÖBB pricing conversation** and the **Nomad conduit/change-request fee negotiation**. It is not a forecast — it is a decision tool. Drop real figures into the estimate lines before either negotiation.

---

## Bottom line

This is a viable, structurally attractive business that **self-funds at fleet scale** — but it is a *working-capital* problem dressed up as a margin question. The margin is excellent and never in real doubt from 30 trains up. Only two things can kill it:

1. **The PoC failing to convert to the ~30-train first order.** Everything good in this model lives on the far side of that single event. Below ~12 trains the business loses money; at 30 trains it nets 55–65% after honest costs. Protect that conversion contractually above all else.
2. **No working-capital headroom behind ÖBB's slow state-railway payment terms.** The realistic peak cash trough is **€130k–180k**, driven almost entirely by receivables timing and per-train install labour — *not* run-rate loss.

Fix both and this is a 70%+ net-margin annuity by 100 trains.

---

## Structural assumptions

- **Kft owns the product IP and contracts ÖBB directly.** Nomad provides the data conduit (it is contractually obliged to deliver collected onboard data to ÖBB) plus change-request work. Nomad's fee for this is **not yet set** — it is the key sensitivity in this model, not a known input.
- **Product is analytics-only, not safety-critical** (occupancy, congestion, luggage, accessibility-aggregate). No safety case → no insured-prime requirement → Kft-direct-to-ÖBB is viable.
- **Hardware the Kft must provide = the Hailo-8 M.2 only** (~€220 unit + ~€80 integration ≈ €300, amortised ~36 months ≈ €7–8/train/mo). Cameras, edge devices (R5001C CCU), and switches **already exist on the train** (Nomad's kit). There is no full sensor BOM to fund.
- **Price:** €750/train/month base case; €500 floor; €1,000 ceiling.
- **Fleet trajectory:** PoC (handful of trains, ideally ÖBB-funded) → **first order ≈ 30 trains** → expansion up to **≈ 200 trains**. The ÖBB KISS/DOSTO fleet is large (100+), so the scale is genuinely reachable. ("DOSTO" = ÖBB's name for the Stadler KISS — same train.)
- **Margin goal:** ≥40% gross margin over hardware + ops (originally a Nomad-era goal; re-evaluated here as the Kft's).

The business shape is **fixed-cost dilution**, not unit economics: per-train marginal cost is genuinely ~€10–15/month, so cost per train ≈ (fixed cloud floor + support labour) ÷ fleet size. Brutal margin at PoC scale, excellent at fleet scale.

---

## Margin picture — honest, not rosy

The naive model showed 79–88% ex-Nomad margins. Those are *steady-state* figures that load **zero** per-train field commissioning, no SLA/on-call labour, and no model retraining. Folding in the adversarial corrections:

| Fleet | Ex-Nomad GM (rosy) | Ex-Nomad GM (honest)¹ | Net after Nomad (curve) | Net after Nomad (flat €90) |
|---|---|---|---|---|
| PoC (~5) | −13% | loss — fund via ÖBB | n/a | n/a |
| 30 | 79% | **~60–68%** | ~58–65% | ~55–62% |
| 50 | 80% | **~50–58%** ← worst point | ~50–55% | ~48–53% |
| 100 | 85% | **~68–72%** | ~66–70% | ~62–66% |
| 200 | 88% | **~75–80%** | ~73–78% | ~70–74% |

¹ *Honest GM loads:* per-train onboarding NRE amortised over a 36-month contract (~4–6 pts); real SLA/on-call labour forcing ~2 FTE by 50 trains, not 200 (~8–12 pts at 50); model-retraining/drift ~€2–4k/mo (~3–5 pts); and 1.5–2× the modelled infra step magnitudes including the un-priced multi-worker SSE fan-out tier.

**Key structural correction: margin does NOT rise monotonically.** It dips at the **50-train step** — exactly where HA Postgres + multi-AZ, the forced second on-call FTE, *and* the receivables drag all land at once. It recovers and climbs again above 100. The business clears the 40% goal everywhere from 30 trains up — but do not promise anyone a smooth climb; budget for the 50-train valley.

---

## Flat fee vs volume curve (Nomad's cut) — resolved

**Push Nomad toward a declining volume curve.** But know precisely why, because it shapes the negotiation:

At the €750 base case the choice is **not existential** — the ex-Nomad cost stack is so thin that even a flat €90/train fee leaves the Kft >55% net from 30 trains up. **So do not trade away expensive concessions elsewhere to win the curve.** The curve matters decisively in two cases:

1. **The low-price case (€500/train).** A flat €250 fee crushes 30 trains to ~20% and 50 trains to ~18% — below the 40% goal. The curve holds 30 trains at ~46%. → *Price floor and Nomad's fee structure are linked; do not negotiate them separately.*
2. **An uncapped flat fee.** Its defect is **temporal, not fleet-size**: it extracts a constant amount while per-train cost collapses. By 200 trains a flat €90 fee *exceeds the Kft's entire ex-Nomad per-train cost* — Nomad earns more per train than it costs the Kft to deliver, for fixed conduit effort.

**Position to take with Nomad:** *"Your conduit and change-request effort is fixed, not per-train — so the fee should be a declining curve that grows your absolute ARR while never starving the rollout it depends on."*

- Proposed curve (illustrative): **€50 → €60 → €55 → €45** across fleet bands.
- If Nomad insists on flat: **hard cap ≤ €150/train + an explicit re-opener at 100 trains.** Never accept an uncapped flat fee — its damage hides behind a harmless-looking 68% at 30 trains.

**Nomad's rational-reconsideration crossover is ~100 trains / ~€100k+ ARR.** Below 50 trains Nomad's take is €18–54k/yr — rounding error to a connectivity vendor. At 100+ the flat-vs-curve gap becomes real money to Nomad (€108k flat vs €66k curve at 100; €216k vs €108k at 200) and they will fight to reclaim it. **Lock the curve AND the full schedule through 200 trains now, at first-order signing, while the fleet is below 50 and Nomad is not paying attention.**

---

## Cash-runway reality

**Run-rate: the business does not need outside equity.** 30 trains throws off ~€14–16k/mo net even after honest costs. A slow 30→200 rollout is the *safe* state, not a risk — parked at 30–50 trains the Kft is firmly cash-generative on a P&L basis.

**But the cash *calendar* is far tighter than run-rate suggests, and this needs founder cash or a facility:**

- **ÖBB is a state railway → NET-60 to NET-90, from an acceptance milestone that itself lags install by 30–60 days.** At 30 trains × €750 = €22,500/mo billing, a 90-day collection lag permanently ties up **~€67,500 in receivables**.
- **Per-train field commissioning is real upfront NRE:** €1,500–3,000/train (depot access, Hailo install on a live consist, per-door camera-mapping validation, ~15% first-pass-fail revisits) = **€45k–90k upfront for 30 trains**, spent *before* the matching revenue clears — on top of ~€120k build NRE.
- **Nomad's fee is paid monthly in arrears on the Kft's schedule while ÖBB pays 60–90 days late** — it compounds the drag.
- **The €9k of Hailo chips for 30 trains is a real upfront buy**, not something to amortise away; only a leasing line removes that trough.

**Realistic peak cash trough: €130k–180k** (the naive model implied €35–40k — a 3.5–5× understatement). A slow rollout *prolongs* the receivables drag rather than relieving it.

**Funding recommendation:** Hold a **€150k working-capital buffer** — founder cash or a small invoice-financing facility, **not equity** (the business needs bridge timing, not dilutive capital). Get ÖBB to fund the PoC so the loss period and its onboarding NRE sit on ÖBB's evaluation budget.

---

## The numbers to walk in with

### (a) ÖBB pricing conversation
- **Anchor €750/train/month; floor €500** (below which a flat Nomad fee breaks the early rollout — price floor and fee structure are linked).
- **ÖBB funds the PoC** at floor price or a fixed pilot fee (~€12k+ over 6 months).
- **Bill onboarding separately** as a one-off €2,000–3,000/train commissioning charge — recover the NRE at install, don't carry it 36 months.
- **Capped SLA** (response + availability) with **penalty liability capped at one month's fees per incident.** Uncapped SLA penalty is the single largest hidden downside — one multi-day peak outage otherwise claws back 1–3 months of margin.

### (b) Nomad fee negotiation
- **Declining volume curve** (e.g. €50 → €60 → €55 → €45 across bands), framed on fixed-effort logic.
- If forced flat: **hard cap ≤ €150/train + 100-train re-opener.**
- **Lock the full schedule through 200 trains at first-order signing**, while Nomad's take is still immaterial.

---

## Costs the model does not yet capture

Get real data on these before signing. The top three set your actual cash exposure.

1. **Per-train field-commissioning labour** *(top priority)* — get a real depot-access + engineer-day quote on a live Stadler KISS in an ÖBB depot, plus the first-pass-fail rate. €45k–90k at 30 trains; currently a guess.
2. **ÖBB payment terms + acceptance-milestone definition** *(top priority)* — the exact NET-x. This single number sets the entire cash trough.
3. **SLA terms and penalty cap** *(top priority)* — no SLA is priced anywhere yet, yet selling operational alerts mandates one; penalty exposure is currently uncapped.
4. **Model retraining / drift revalidation** — recurring ~€2–4k/mo skilled ML labour the repo's own model-provenance/drift artifacts confirm is in scope; counted as zero in every lens.
5. **Multi-worker SSE fan-out** (architecture §681 / OQ-13) — current in-process subscribers don't fan out across workers; fleet rollout forces a managed Redis / PG-LISTEN-NOTIFY tier plus re-architecture labour, never priced.
6. **Cross-border HU→AT tax** — confirm VAT reverse-charge handling and whether ÖBB applies Austrian withholding on any IP/royalty-flavoured element (potential 10–20% top-line haircut). Plus FX exposure for a HUF-functional entity with EUR revenue and EUR/USD costs.
7. **Single-customer churn as a 36-month renewal cliff**, not a smooth %. Non-renewal zeroes the entire annuity. Apply an explicit risk discount to ARR.
8. **Real cloud quotes** for the stepped HA infra — the step magnitudes (€1,200 → €2,600 at 50) are analyst estimates and likely 1.5–2× low for managed multi-AZ HA Postgres + replica + the un-priced Redis tier.
9. **Entity formation + DPA + contracting legal** — real pre-revenue cash, excluded from the run-rate model.

---

## Next modelling step

Once Nomad signals a fee range, add it as a second cost line and produce the **net (post-Nomad) margin curve** showing the flat-fee-vs-volume-curve gap in the fragile 30–50 train zone — that is the chart to put in front of Nomad in the negotiation. Pair this with ÖBB's actual rollout *timeline* (30→200): that timeline is what converts this margin model into a true cash-runway model, and it is the single most important unknown still outstanding.
