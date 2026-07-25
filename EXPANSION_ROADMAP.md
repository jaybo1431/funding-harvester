# Funding Harvester — Multi-Venue Expansion Roadmap
_Research swarm (6 agents), Jul 25 2026. Decision-ready. UK-first; Algeria jurisdiction revisited later._

## ⚠️ THE OVERRIDING TRUTH (read first)
**The blocker is the ALPHA in this regime, not the venue count.** Funding is structurally compressed
in 2025-26 (extreme spikes down ~90% since 2016, arbed away in hours). Realistic **~8-20% net for the
whole book right now**. Adding venues widens the opportunity set + cheaper fees improve unit economics
but **does NOT manufacture alpha in a compressed regime**. The fat (100%+) numbers need the regime to
un-compress — i.e. a **bull run** (leveraged longs pay rich funding). Build the machine now; the bull
turns the water on.

## PROVE-FIRST — before ANY expansion, prove LIVE on Hyperliquid (small real money)
1. **Maker fill rate** holds the cost assumption — edge dies above ~8bps roundtrip. Measure realised bps/rotation.
2. **Live slippage on rotation** at $1-10k stays in budget (the rank-and-rotate rebalance is where it silently breaks).
3. **Hedge leg holds neutral** through a funding-flip + real move (Feb-2026 crash = the stress case).
4. **Net APY clears 8% gate LIVE**, not just backtest. If HL-only can't clear it, venues won't fix it.
5. **Security spine works** end-to-end: trade-only/no-withdraw key, IP whitelist, watchdog, kill-switch — tested BEFORE the treasury holds anything.
Only once HL clears 1-5 → build next venue read-only → paper-forward → gate → fund. **One venue at a time.**

## RANKED VENUE EXPANSION (after HL + Drift)
1. **Lighter (zkLighter)** — 0% maker AND 0% taker (biggest carry-margin headroom), 150+ markets, 8h
   funding offset from HL's hourly = real cross-venue spread windows. zk-rollup → ETH. Grey-reachable (verify UK geo).
2. **Injective / Helix (Cosmos)** — NEGATIVE maker fee (−0.01% rebate = paid to place legs), on-chain
   orderbook (clean funding signal, gRPC/REST like driftpy), best chain diversifier. GREEN UK access. Bridge = IBC/Peggy.
3. **Extended (X10, Starknet)** — RWA/forex perps (EUR/USD, XAU, S&P, oil) = uncorrelated funding drivers,
   kills k=2 concentration risk. 2/4bps fees (maker-only discipline mandatory). Starknet AA signing wrinkle.
4. **Vertex / ApeX (tertiary)** — cheap fees but funding tracks CEX (thin standalone edge). **Paradex = HEDGE LEG only** (Funding V2 = weighted median of Binance/Bybit/OKX/HL/Lighter; had a pricing-glitch mass-liq incident).

## IDLE COLLATERAL — park dry powder UNCORRELATED to funding
1. **Aave V3 / Morpho USDC** (~3-7%, L2) — DEFAULT: instant liquidity to redeploy into hot regimes, deepest audits.
2. **sDAI / USDS** (~8%) — higher park for capital not about to move; ERC-4626, instant redeem.
3. **Tokenized T-bills** (BUIDL/USDY/OUSG ~4-5%) — cleanest risk-free leg BUT mostly KYC/permissioned (UK-retail access = binding constraint).
- **NEVER park hedge collateral in sUSDe (Ethena)** — its yield IS funding carry = your strategy in a wrapper.
  In a negative-funding crash, live book AND "safe" park bleed together. Tiny satellite only, never the home.

## TREASURY — TWO PLANES THAT NEVER MERGE (drains: 3Commas $14.8M, Kronos $25M — compromised keys)
- **Plane A — TRADING (autonomous, powerless over money):** bot holds ONLY trade-only, no-withdraw,
  IP-whitelisted keys (HL agent wallet / Drift program key / equivalent). Bot risk layer caps per-order +
  per-interval notional, trades only liquid perps (blunts self-trade drain). Only working margin on-venue; bulk off-bot.
- **Plane B — MONEY MOVEMENT (rare, human-gated above a cap):** central pot in **Safe multisig (2/3, one
  hardware key)**. Bot = Allowance-Module delegate with a SMALL daily cap to a SHORT allow-list of your own
  venue-deposit addresses. That is the ONLY autonomous movement — capped at smart-contract level → compromised
  mover loses one day's small top-up, not the pot. Rebalancing isn't latency-sensitive, so human approval is free.
- **MAY automate:** execution; flatten; internal CEX main↔sub transfers; small capped allow-listed top-ups;
  profit-sweep detect+propose; monitoring + kill-switch (cancel/flatten/revoke agent key/pause mover).
- **MUST stay human-approved:** transfers above cap; new withdrawal/allow-list address; enabling withdrawal;
  moving funds OUT of treasury; large emergency withdrawals. CEX: external withdrawal DISABLED on bot key +
  allow-list + 24-48h time-lock + hardware 2FA.
- **WATCHDOG:** independent reconciler, SEPARATE host, READ-ONLY keys — alerts on new key/withdrawal address,
  permission toggles, balance deltas, cap approach, fills outside traded universe. Reuse the Telegram-cron pattern.
- **Sizing:** $1-3k → hardware cold reserve + trade-only keys + small on-venue balances + manual top-ups +
  allow-listed withdrawals + watchdog. Add Safe + Allowance Module + sub-account routing at ~$5-10k. MPC/Fireblocks
  only at six figures. Fund via FCA-registered UK spot (Kraken/Coinbase UK, GBP Faster Payments) → USDC → self-custody.

## UK ACCESS CEILING → ALGERIA LATER
Every reachable venue is a permissionless grey-zone DEX (FCA retail derivative ban PS20/10 firmly in force
through 2026; only ETNs un-banned Oct 2025, NOT perps). Every CENTRALISED perp (Bybit/Binance/OKX/dYdX/Aevo)
hard-blocks UK retail — VPN + foreign KYC = withdrawal-freeze/seizure risk, no recourse. Kraken Futures/Deribit
need FCA Professional-Client status (~£500k). dYdX hard-blocks UK by IP. **The Algeria plan (non-UK accounts)
is what unlocks the CEX venue menu — revisit after the UK/DEX version proves live.**

## HONEST CAVEATS
- Alpha (not venues) is the blocker; compressed regime; anchor ~8-20% net, not 30-100% (those are gross/spike cherry-picks).
- HL's ~11% baseline funding is the HL-specific moat — every new venue must clear the gate on ITS OWN data first.
- Correlation in the tail: carry + basis + sUSDe all short-funding → diversify the idle park AWAY from funding.
- New venues (Lighter/Injective/Extended) = younger SDKs, thinner tail depth (hedge slippage), token-incentive liquidity that can reverse.
- The real drain risk is credential compromise, not the market. Never a naive autonomous treasury with withdrawal keys.
