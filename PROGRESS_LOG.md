
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
