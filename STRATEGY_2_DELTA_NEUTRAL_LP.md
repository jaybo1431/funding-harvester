# Strategy #2 — Delta-Neutral LP (scope)
_Scoped Jul 26 2026. Market-neutral yield stack, sibling of the funding carry. DO NOT build until funding carry proves live — this is the queued #2._

## THESIS
Earn AMM trading fees market-neutrally. An LP position is implicitly *long* the volatile token;
hedge that exposure so net delta ≈ 0 → you keep the fees without the directional bleed.

## ⚠️ THE HARD PART — gamma (why most LPs lose)
- Concentrated-LP delta is DYNAMIC: as price moves the pool auto-rebalances your holdings, so a
  STATIC perp short drifts off-neutral within hours. You must continuously re-hedge.
- Re-hedging costs (fees + slippage on the perp) EAT the LP fees. This is gamma bleed.
- Evidence: >51% of Uniswap v3 LPs were unprofitable — IL exceeded fee income (Bancor/IntoTheBlock).
- So: naive LP = trap. Even hedged volatile-LP is genuinely hard and must be proven net-of-rebalancing.

## PHASED PLAN (robust first, ambitious later)

### Phase A — Stable-pair LP (BUILD FIRST — the reliable floor)
- Pools: Curve/Uniswap **USDC/USDT, USDC/DAI, USDe/USDC**-type. Both sides are dollars → almost no
  divergence → negligible IL, negligible gamma, NO hedge needed. Market-neutral by construction.
- Real numbers: **8-15% APY from fees alone** (Curve stables, 2024-25), IL barely registers.
- Effort: LOW. Deposit, earn, monitor. This is the treasury floor supercharged (vs ~4-8% plain lending).
- Risks: smart-contract (use battle-tested Curve/Aave-tier), stablecoin depeg (stick to top stables;
  avoid exotic/algo stables), reward-token dilution (target REAL fee yield, not incentive emissions).

### Phase B — Volatile delta-neutral LP (LATER — the ambitious #2)
- Position: ETH/USDC (or SOL/USDC) concentrated LP + **short the token perp on Hyperliquid**
  (REUSES the funding-bot perp infra — same account, same hedge machinery).
- Hedge ratio: **~50-70%**, NOT 100% (higher ratio = tighter collateral = liquidation risk on the
  borrowed/short side). Rebalance the short as pool delta drifts.
- Upside: higher fee APY on volatile pairs + you may also COLLECT funding on the short leg (bonus).
- The make-or-break: does net-of-rebalancing-cost beat Phase A? Gamma bleed can erase the extra fees.
- Alt hedge: options (Deribit puts/calls) statically replicate IL — cleaner gamma but options premium
  cost + Deribit UK-access question. Perp hedge is simpler to start.

## VALIDATION (paper, before a penny — same discipline as the funding bot)
1. Phase A: trivial to validate — historical/live stable-pool fee APY is public (Curve/DefiLlama).
   Just confirm the specific pool's real fee yield net of gas, and depeg history.
2. Phase B: BACKTEST an LP + hourly perp re-hedge on historical ETH/USDC (the papers use 2024-12 →
   2025-08). Measure: LP fees − IL − rebalancing costs − perp funding paid/received = net. Must clear
   a gate (say >8% net, low DD) OUT-OF-SAMPLE, exactly like the funding carry. If gamma bleed sinks
   it below Phase A, DON'T build it — just run Phase A.

## HOW IT FITS THE STACK
- Phase A = the always-on floor (idle/treasury capital earning 8-15% instead of sitting).
- Phase B = a 2nd market-neutral book sharing the perp/hedge infra → multi-strat market-neutral fund.
- Same DNA as funding carry: structural yield, direction-neutral, systematic, backtested-then-live.

## GATE
Do NOT build until funding carry is proven LIVE (Milestone 2). Then: Phase A first (low-risk floor),
Phase B only if its OOS backtest clears the gate net-of-gamma. One strategy live at a time.

## TOOLING SEEN (for reference, verify independently)
Teahouse Finance, Sector Finance, Neutra, Panoptic, Gyroscope E-CLPs (dynamic concentrated LP);
Curve/Convex for stable-pool yield; DefiLlama for real pool APYs; Deribit for options hedging.
