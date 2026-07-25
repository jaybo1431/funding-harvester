
## 🌶️ CONCENTRATION BOOK spun up (Jul 22 2026) — proving the spike-hunter RISK forward
- Concentration dial OOS-VALIDATED on RETURN (spike_hunter.py: flat 22.1% → α=1 48.9% on unseen
  test half — HELD, ~2x, didn't collapse). Regime-leverage weaker OOS (63→47) — lean on concentration.
- BUT OOS validated return, NOT risk — backtest still models perfect capture + fantasy -0.06% DD.
  Concentration's REAL risk (idiosyncratic flip / thin liquidity / liquidation on fat-funding alts) only
  shows forward. So: spun up a CONCENTRATED paper book head-to-head with the flat one.
- hl_paper.py now supports HL_ALPHA (0=flat equal-weight default, 1=funding-weighted concentration) +
  HL_TAG (state file suffix). Concentrated instance: cron  HL_TAG=_conc HL_ALPHA=1.0 →
  hl_paper_conc_state.json / _pnl.csv / _conc.log. Dashboard shows it as 3rd book (🌶️).
- THE TEST: does concentrated stay as smooth as flat forward, or take real hits? That's the risk proof
  OOS couldn't give. If smooth + ~2x return holds → it's the profit booster. If it draws down hard → flat wins.

## ⚔️⚔️ AGGRESSIVE TARGET CONFIG — LOCKED (Jul 24 2026, via aggressive_model.py)
Go-live target once 1× proves live: **3× leverage × α=1 concentration × K=3 → ~135% APY**
(OOS-honest base ~21% flat / ~45% concentrated × 3× — NOT the ~160% live-paper figure, which
only accrues funding and ignores costs/hedge-slippage/tail). Normal-regime drawdown <4%.

- **MAX_LEVERAGE=3 HARD CAP ENFORCED** in hl_execution.py (5× → "🛑 refusing to trade", verified).
  The engine physically refuses anything above 3× regardless of env. Never past 5×.
- **Liquidation math** — single-venue, cross-margined, delta-neutral → raw PRICE cancels between
  the two legs, so liquidation needs a BASIS DIVERGENCE (or venue/tail event), not a price swing:
  - 3× → legs must diverge ~30% to liquidate (wide buffer). 2× → ~47%. 5× → ~17% (thin, avoid).
  - Funding-flip bleed negligible per event (fast-exit caps it) — flips erode, don't liquidate.
  - BLACK SWAN (venue hack / mass delist / depeg cascade) blows ANY leverage — un-modellable.
    Keep leverage where a tail event hurts but doesn't end you.
- **RAMP:** prove 1× live → step to 3× on evidence → run α=1 concentrated (already proven in the
  live paper concentrated book). Aggressive on READINESS, disciplined on the TRIGGER.

## 📌 STATUS Jul 25 2026 — RUNNING, let it cook
- **Paper-forward ~3.7 days**, 3 books climbing (FLAT ~52% / CONC ~147% / DRIFT ~266% APY paper).
  Now gathering multi-week data across regime changes — the real test of the sustainable rate.
- **Multi-venue expansion roadmap added** → see `EXPANSION_ROADMAP.md` (research swarm, Jul 25).
  Ranked: Lighter → Injective → Extended. Idle collateral: Aave/sDAI (NOT sUSDe). Two-plane treasury.
- **PROVE-FIRST GATE stands:** prove HL clears 8% net LIVE (maker fills, slippage, hedge-holds,
  security spine) on small real money BEFORE any expansion. Alpha is regime-compressed — venues don't fix that.
- **Deployment:** UK-first (grey-zone DEXs). Algeria VPS + accounts revisited later (unlocks CEX venues).
- Repos PRIVATE + backed up: jaybo1431/funding-harvester (this) + jaybo1431/robinhood-runner (signal bots).
- No real money yet. Weapon loaded (MAX_LEVERAGE=3 cap), safety on. Telegram tripwire armed for first signal trade.
