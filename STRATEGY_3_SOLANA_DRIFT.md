# 🟣 STRATEGY 3 — Solana / Drift Funding Carry (SCOPE)
_The high-yield satellite. Scoped Aug 14 2026. Status: PAPER-PROVEN (~24d), live build GATED behind HL going live first._

## Thesis
Drift (Solana perp DEX) funding runs far richer than HL because it's **less arbitraged** — thinner books, fewer sophisticated players, funding hits silly levels before anyone corrects it. Same delta-neutral carry as the HL core: short the high-funding perp, hedge delta, collect funding. The edge is real; the catch is **capacity**.

## The capacity reality (why this is a SATELLITE, not the core)
Paper book (~24d) is riding **ME-PERP, IO-PERP, DRIFT-PERP** — thin Drift-native alts. Their funding is real but only capturable at small size:
- You **become the arb** — your own short pushes funding down.
- You **eat slippage** on a thin book.
- So capture **decays as you scale**:

| Capital on Drift | Realistic sustainable capture |
|---|---|
| ~$200–500 | 80–150% (cherry-pick fattest, thin books don't hurt yet) |
| ~$1–2k | 50–80% (starting to move funding + slippage) |
| ~$5k+ | ~30–40% (you're the marginal player; converges to HL-like) |

**Plan around 50–100% on a CAPPED $500–1k allocation.** The +247% honest-cost headline is a mirage — real funding, uncapturable at size. Ignore it for planning.

## The security difference — READ THIS (the one real gotcha)
HL live uses a **trade-only agent wallet that CANNOT withdraw** — that's why it's low-risk. **Drift/driftpy has no equivalent: it signs with a keypair that CAN move funds.** So Solana live = a **hot wallet with a real key on the server** — a bigger security surface than HL.

Mitigations (all required before live):
- **Dedicated, minimally-funded wallet** — $500–1k max, nothing you can't lose. Never your main.
- Key set by USER in `/root/drift-live/.env` (chmod 600), **never in chat/logs/code** — same rule as HL.
- **Drain watchdog** — read-only balance monitor, Telegram alert on any unexpected balance drop / new signer.
- Keep only trading capital in it; sweep profits out to cold storage periodically (human-approved).

## Build scope (when un-gated)
Mirror the HL live path, adapted for Solana:
1. **drift_execution.py** (DRY-RUN first) — reuse `drift_paper.py`'s funding read + top-K/hysteresis selection; add order placement via driftpy (`place_perp_order`, post-only where supported), delta hedge, the same risk gates (MAX_LEVERAGE cap, funding-flip fast-exit, daily-loss halt). SDK-touching code lazy-imported inside the container.
2. **CAPITAL_CAP collar** — same dynamic-equity + hard-cap pattern as HL, but capped LOW ($500–1k) given capacity. Never scale past where capture craters.
3. **Fill logging** — same fill_log.jsonl pattern (Solana fills → ML dataset later).
4. **drift_watchdog.py** — the drain monitor above; on the 30-min cron with the others.
5. **Dashboard** — add a 🟣 Drift Live panel (read-only status, same as HL's Live Setup).

## Go-live gate (do NOT start until ALL true)
- [ ] **HL £150 live test has PROVEN OUT** (maker fills hold, net clears gate live) — HL is the pipeline proof; Drift inherits it.
- [ ] Drift paper still clearing its gate at that point (it's been ~18% net / 24d).
- [ ] Dedicated $500–1k Solana wallet funded (USDC on Solana + a little SOL for gas), key set by user.
- [ ] Drain watchdog live and alert-tested.
- [ ] DRY-RUN order plan eyeballed and sane.

## Realistic contribution to the blend
A capped $500–1k Drift book at 50–100% adds a **high-yield tilt on small money** on top of the scalable HL core — juices blended APY without risking the stack. It's the spice, not the meal.

---
_Sequencing: HL live-proven → Drift tiny security-hardened live test → then the rest of the queue (Lighter, Injective, cross-venue, LP). Prove-first, one at a time, always._
_Where it lives: paper harness `drift_paper.py` (container `drift-paper`, 3wk up) · repo `jaybo1431/funding-harvester` · full roadmap `EXPANSION_ROADMAP.md`._
