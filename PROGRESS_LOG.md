
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

## 🚀 GO-LIVE MACHINERY WIRED + NEW MODULE (Aug 6-10 2026)
Milestone 1 essentially hit: ~16 days paper across a full funding COMPRESS→RECOVER cycle, all 4
books (HL flat/conc, Drift, Lighter) clearing every honest-cost gate the whole way. User green-lit a
small LIVE test — agreed £150 (better than £250: more conservative first strike). Then built the rails:

- **Dynamic capital sizing** (hl_execution.py): reads LIVE account equity read-only, keeps a 10%
  margin buffer, deploys up to CAPITAL_CAP — compounded profits + top-ups auto-redeploy each cycle
  ("savings account that compounds itself"). Cap raised deliberately on evidence (250→1k→5k→20k).
  Falls back to static CAPITAL_USD if equity unreadable. Collars verified clamping to £150.
- **Live maker placement WIRED** (_place_live): real post-only (Alo) limit orders via HL SDK, reusing
  live_test.py rounding. Guarded: LIVE=true + trade-only agent key, SDK lazy-imported, min-notional
  guard, fail-safe. VERIFIED: LIVE=true with no key places NOTHING. Run live via venv python.
- **Dashboard Live Setup panel** (:3040): read-only readiness — key present? (never its value),
  public address + live USDC balance from HL public API, SSH setup commands. No key-input box.
- **User funding pending**: wallet → USDC (Coinbase UK) → bridge to HL → £150 + trade-only agent
  key in /root/hl-live/.env (chmod 600, never in chat). Then place-and-cancel → tiny position → live.
- **NEW MODULE — cross-venue funding-SPREAD book** (cross_venue_paper.py): SAME coin on HL +
  Lighter opposite (short higher-funding leg, long lower) → harvests funding DISPERSION as a perfectly
  delta-neutral spread, NO hedge leg, cleaner neutrality. Hourly cron, read-only. Live scan: real
  dispersion (liquid XMR 19%, JUP 51%, APT 42%; thin fat ones = mirage, paper separates). Drift leg TBD.
- **Repos secured**: primehaul + primehaul-leads PUBLIC→private (0 forks). Authorship verified: 140
  commits timestamped from 2025-12-27, all user identity.

## 🛡️ SIGNAL-BOT REVIVAL + WATCHDOG (Aug 10 2026)
User asked "is the wallet-cluster working?" — investigation found ALL THREE signal bots
(overdose t=0, overdose t+10, wallet-cluster) had been SILENTLY DEAD since ~Jul 24.

- **Root cause**: crons used `... && source ./env && python3 ...` but cron runs /bin/sh (dash),
  where `source` is invalid → the `&&` chain short-circuited → python NEVER ran → state froze
  looking calm/0-0-0. Smoking gun: none of the three log files ever existed. Funding books were
  UNAFFECTED (they use `/usr/bin/python3` directly, no source) — the real edge kept its 20d data.
- **Fix**: added `SHELL=/bin/bash` to top of crontab → all crons now run under bash, `source` works.
  Verified end-to-end: real scheduled cron tick fired overdose (1-min-old state), overdose_d10
  CAUGHT A REAL CALL (queued pending), cluster scanning 146 winner wallets. Wallet-cluster confirmed
  INDEPENDENT of Overdose (watches on-chain wallet clusters, not his posts).
- **17-day gap is a blank** — missed calls/clusters Jul24→Aug10 unrecoverable; forward scoreboard
  restarts from Aug 10. These are unproven paper experiments — nothing real was risked.

- **signal_watchdog.py** (robinhood-runner): dead-man's switch. Checks all 8 paper books' state-file
  mtimes every 30min; Telegrams an alert if any is stale past its cron cadence. Alert path verified
  end-to-end (RUNNER_TG_TOKEN/CHAT). Cron */30.
- **Dashboard Book Health strip** (:3040): green/red freshness chips per book, header flips to
  "⚠️ a book has stalled". Two independent layers now catch a silent stall (dashboard + Telegram).

Commits: funding-harvester 506061c (health strip) · robinhood-runner 3fbc1ff (watchdog+fix).

## 💷 FUNDING SCOPE — ONE WALLET ONLY (Aug 13 2026)
User asked if they need to fund multiple wallets (Solana + USDC for HL + overdose + cluster).
ANSWER: NO — fund ONE wallet, ONE thing: £150 USDC on Hyperliquid. That's the entire live scope.

- ✅ HL funding book → £150 USDC on Hyperliquid. The proven edge. The ONLY thing going live now.
- ❌ Drift (paper) → would need Solana USDC IF it ever went live — NOT now, not proven-live.
- ❌ Lighter / Cross-venue (paper) → later modules in the queue, no funding.
- ❌ Overdose calls + Wallet-cluster → NO funding. Unproven memecoin punts, negative-sum arena,
  honeypot/rug risk, ZERO forward-proven track record (scoreboard only restarted Aug 10 after the
  17-day stall). A signal bot earns real money ONLY after its paper scoreboard wins over weeks.
- RULE reaffirmed: multi-wallet / multi-chain (Solana for Drift etc.) comes LATER, ONE at a time,
  each only after it proves live — never all at once. Don't spread £150 across 5 things and learn
  nothing. One clean, proven, market-neutral bet first.

Status ~23d paper: HL Flat +32% / Conc +78% realistic (parked at run highs, no decay). Cross-venue
now ~51% APY over 2.8d (graduating noise→signal, still haircut for thin names). Overdose t+10 still
holding PUMP flat 3d (heading to +40%TP or 5d stale-close). All 8 books green, watchdog quiet.

## 🧠 FILL-LOGGING LAYER — the ML prerequisite (Aug 13 2026)
User asked if a dynamic ML model would trade better. HONEST VERDICT: not yet, and not for the
strategy. Funding harvest is STRUCTURAL (observe funding → short it → collect), not a prediction
problem — ML can't improve an edge that isn't a forecast. And ZERO live data exists (23d paper, no
fills); a model trained on 23d of one regime would overfit — the exact trap that killed the memecoin
bots. Where ML DOES help later: the FILL layer (maker-fill probability), which needs live fill data.

So built the prerequisite, not a premature model:
- **fill_log.jsonl** — every live maker order logs 2 rows: 'place' (order-book FEATURES at placement:
  spread, bid/ask depth 10 levels, mid, funding, chosen maker offset, size) + 'outcome' (label, next
  cycle via reconcile_fills matching oid→user_fills: filled?, maker vs taker (crossed==False), realized
  slippage vs mid, time-to-fill, fee). That's a full ML training example per order.
- **reconcile_fills()** runs each LIVE cycle, labels last cycle's orders against real fills.
- **fill_analysis.py** — reads/pairs the log, prints fill-rate / maker% / median slippage / TTF. Says
  "train a fill-probability model at ~1000+ rows". No training yet — honest read of data first.
- ALL SDK-touching code inside the LIVE-guarded lazy path. Verified: dry-run untouched, failsafe
  intact (LIVE+no key places nothing), no log file until real orders. Commit 9969be5.

PATH: fund £150 → orders place → log fills → after ~1 month + ~1000 rows, THEN a small fill model
is a grounded few-% uplift on honest net. ML is now wired to happen the moment there's fuel (the £150).

## 🐛 CROSS-CHAIN TICKER RESOLVER FIX — copycat caught live (Aug 15 2026)
User noticed the open PUMP paper position "should have gone up" — investigated, found a real bug.
- Overdose post #3303 called "$PUMP" by TICKER (no address). $PUMP = pump.fun's token on SOLANA.
- BUG: coin_resolver._search_ticker searched ROBINHOOD chain ONLY for ticker calls, so it grabbed a
  same-named Robinhood-chain PUMP copycat (0xf2311c79..) that sat DEAD FLAT (-2%, peak +0%) for 4.5d
  while the REAL PUMP ran to $0.00278 ($17.6M liq). Exact "wrong contract = worthless data" trap.
- FIX (robinhood-runner ce2f2d8): _search_ticker now searches ALL chains, takes DEEPEST-liquidity
  match (copycat-proof 'deepest wins' applied to tickers), returns (token, network). Whole-symbol
  match (PUMP != TRUMP). Solana base58 kept case-sensitive via _tok_netaddr (lowercasing corrupted it).
  Verified: $PUMP → solana pumpCmXq.. $17.6M conf MEDIUM. EVM address path regression-tested intact.
- Bad data VOIDED: PUMP positions in overdose + overdose_d10 marked voided_wrong_contract (£0, excluded
  from scoreboard); false PUMP 'rugged' row stripped from trades CSV (backup kept). Books back to clean 0/0/0.
- Impact: was silently mis-resolving EVERY ticker-only call on Solana/BSC. Now tracks the coins he MEANS
  across all chains. Caught free on paper before any real money.

## 🎯 BACKTEST OF REACHABLE CALLS + TRAILING-STOP EXIT A/B (Aug 15 2026)
User asked to backtest Overdose calls other than PUMP. 2024 unreachable (channel only ~3300 posts,
Robinhood-chain focused = 2026, public preview shows only last ~20 posts). BUT the reachable window
(Jul 8–Aug 9, timestamps in t.me/s HTML) IS backtestable — built backtest_recent.py:
- Extracts (post_id, timestamp, text) from preview, resolves coins copycat-proof (cross-chain fixed),
  pulls hourly OHLCV from call time, simulates the bot rule (+40% TP / rug proxy -90% / 5d stale).
- RESULT (n=3 clean, rest commentary/no-history/rate-limited): JUGGERNAUT TP +40% (peak +59%),
  VEX TP +40% (PEAK +214%), HOODRAT stale -75% (peak +14%). 67% hit, avg +1.8%/call, £100 clips → +£5.
- KEY INSIGHT: flat +40% TP CAPS the runners — VEX ran +214% but booked +40% (left +174% on table).
  And one rug (-75%) eats two +40% wins. Asymmetry the wrong way. Small sample; forward tracker trusted.

FIX/UPGRADE — trailing-stop exit mode to squeeze the runners:
- overdose_tracker.py OD_EXIT: "tp40" (default, unchanged) | "trail" (no hard TP; arm ratcheting stop
  at +40%, exit 25% off running peak). Unit-tested: runner +130% (vs +40% capped), quick-tap -10%
  (vs +40%) — the exact tradeoff. Which wins = how often his calls run vs fake out → forward A/B decides.
- NEW _trail cron instance (t=0 entry, trail exit) seeded #3304, head-to-head with tp40 t=0 + t+10 on
  the SAME calls. Wired into watchdog + dashboard (3rd Overdose card "let winners run") + checkin.
- Commits: robinhood-runner ce4cfa0 (trail + watchdog), funding-harvester d71b492 (dash). All paper.

## 🔬 MAGA ON-CHAIN RECONSTRUCTION + EXIT VARIANTS (Aug 15 2026)
User's REAL 2024 trade: bought MAGA (0xD29DA236..) May 17, rode a big dip on the 21st, sold ~27th for
huge gains. Wanted the bot backtested on it. 2024 unreachable via APIs (GeckoTerminal/CoinGecko free
cap ~6-12mo, 401 on older). Solution: ON-CHAIN reconstruction via user's Infura key.
- Coin confirmed: MAGA/WETH, Ethereum, Uniswap V2 pool 0x0c3fdf9c.., MAGA 9 decimals.
- Pulled 26,422 Sync events (reserve0/reserve1 → MAGA price in ETH) across May-2024 blocks
  19,878,821→19,971,801 via Infura eth_getLogs (10k-block chunks, heavy retry on -32603 transient errs).
- RESULT — MAGA path from entry: +208% (18th), +1867% (21st, dipped to +1120% intraday), pulled back
  to +644% (23rd), then +2237/2439/5403% (25/26/28th). PEAK +2559% in window. User sold ~+2238% (≈23x).
  STORY CONFIRMED on-chain — his call + her diamond hands = real 23x.
- BOMBSHELL: bot would have WRECKED it. +40% TP sold May-17 14:56 (hrs after entry) for +40%. Tight 25%
  trail shaken out +33% same day. User's intuition beat the bot ~56x. Extreme VEX lesson: flat/tight
  exits are catastrophic on moonshots; our 25% trail is FAR too tight for memecoin vol.

FIX — two new exit variants tuned on MAGA (overdose_tracker.py OD_EXIT):
- "partial": bank HALF at +40% (base win even on fakeouts) + ride other half on wide trail. MAGA replay +408%.
- "moon" (= trail run WIDE via env: OD_TRAIL_ARM=2.0 arm+100%, OD_TRAIL_PCT=0.55). MAGA replay +777%.
  (vs flat tp40 +40%, tight trail +33%.) Neither beats the +2238% ride, but 10-19x the flat TP, MECHANICAL.
- Spun up _moon + _part cron instances (5-min, seeded #3304) → now a 5-ARM forward exit A/B on his calls
  (t=0 tp40, t+10 tp40, trail-tight, moon-wide, partial). Wired watchdog + dashboard (5 Overdose cards).
- Commits: robinhood-runner 893fcda, funding-harvester afa00f6. All paper. Infura key user-supplied (rotatable).
