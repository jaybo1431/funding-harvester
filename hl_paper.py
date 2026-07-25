"""hl_paper.py — LIVE paper-forward harness for the HL cross-sectional funding carry.

Read-only. No keys, no money, no orders. Each run it:
  1. pulls LIVE Hyperliquid funding across the universe (metaAndAssetCtxs — one call),
  2. runs the SAME selection the backtest validated (top-K |funding|, hysteresis entry/
     exit floors), maintaining a paper delta-neutral book,
  3. accrues the funding EARNED on held positions since last run, minus turnover costs,
  4. logs cumulative net P&L + annualised rate.

This is the honest "does the validated backtest actually work on live out-of-sample
data" test — the step we skipped on the memecoin bots and paid for. When this forward
P&L tracks the backtest's ~15-20% APY over a real sample, THEN real money is earned.

Delta-neutral model: short the high-funding perps / long the negative-funding perps,
each hedged (spot or low-funding perp) so price nets ~0 → the return IS the |funding|
collected minus costs, exactly what the backtest measured. Runs hourly (HL cadence).
Output: hl_paper_state.json, hl_paper_pnl.csv.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://api.hyperliquid.xyz/info"
# HL_TAG lets a 2nd instance run a variant on its own state (e.g. _conc = the
# concentration/spike-hunter book). Empty = the default flat book.
TAG = os.environ.get("HL_TAG", "")
STATE = os.path.join(HERE, f"hl_paper{TAG}_state.json")
PNL = os.path.join(HERE, f"hl_paper{TAG}_pnl.csv")

# match the validated backtest
K = int(os.environ.get("HL_K", "3"))
ENTRY_ANN = float(os.environ.get("HL_ENTRY_ANN", "0.12"))   # open if |funding| APY >= this
EXIT_ANN = float(os.environ.get("HL_EXIT_ANN", "0.03"))     # hold until it decays below this
ROUNDTRIP_BPS = float(os.environ.get("HL_ROUNDTRIP_BPS", "8"))
MIN_OI_USD = float(os.environ.get("HL_MIN_OI", "5000000"))  # skip illiquid (<$5M OI): slippage
# ALPHA = concentration dial (OOS-validated ~2x return): 0 = flat equal-weight (default),
# 1 = capital weighted by funding richness (piles into the fat spikes). Proving RISK forward.
ALPHA = float(os.environ.get("HL_ALPHA", "0"))
HOURS_PER_YEAR = 24 * 365


def _post(body, tries=5):
    data = json.dumps(body).encode()
    for a in range(tries):
        try:
            req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=25).read())
        except Exception:
            time.sleep(2 * (a + 1))
    return None


def live_funding():
    """coin -> (annualised funding, oi_usd). HL funding is hourly."""
    m = _post({"type": "metaAndAssetCtxs"})
    if not m:
        return {}
    out = {}
    for u, ctx in zip(m[0]["universe"], m[1]):
        if u.get("isDelisted"):
            continue
        try:
            f_hr = float(ctx.get("funding") or 0)          # hourly funding fraction
            oi = float(ctx.get("openInterest") or 0) * float(ctx.get("markPx") or 0)
        except (TypeError, ValueError):
            continue
        out[u["name"]] = (f_hr * HOURS_PER_YEAR, oi)       # annualised
    return out


def _load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


def main():
    now = time.time()
    fund = live_funding()
    if not fund:
        print("hl_paper: HL fetch failed — skip")
        return
    st = _load(STATE, {"book": {}, "cum_funding": 0.0, "cum_cost": 0.0,
                       "start_ts": now, "last_ts": now})
    book = st["book"]                       # coin -> {side, ann_at_entry}
    dt_h = (now - st["last_ts"]) / 3600 if st["last_ts"] else 0

    # 1) ACCRUE funding on held positions since last run. Capital is split by CONCENTRATION
    #    weight = |funding|^ALPHA (ALPHA=0 → equal 1/K; ALPHA=1 → piled into the fattest funding).
    weights = {c: abs(fund.get(c, (0.0, 0.0))[0]) ** ALPHA for c in book}
    tot_w = sum(weights.values()) or 1.0
    for coin in book:
        ann, _ = fund.get(coin, (0.0, 0.0))
        w = weights[coin] / tot_w                       # fraction of capital on this coin
        st["cum_funding"] += (abs(ann) / HOURS_PER_YEAR) * dt_h * w

    # 2) EXIT decayed positions (|funding| fell below exit floor, or coin gone)
    for coin in list(book):
        ann, _ = fund.get(coin, (0.0, 0.0))
        if coin not in fund or abs(ann) < EXIT_ANN:
            del book[coin]

    # 3) FILL free slots with the richest carry above the entry floor (liquid only)
    ranked = sorted(fund.items(), key=lambda kv: -abs(kv[1][0]))
    opens = 0
    for coin, (ann, oi) in ranked:
        if len(book) >= K:
            break
        if coin in book or abs(ann) < ENTRY_ANN or oi < MIN_OI_USD:
            continue
        book[coin] = {"side": "short" if ann > 0 else "long", "ann_at_entry": round(ann, 3)}
        opens += 1
    st["cum_cost"] += opens * (ROUNDTRIP_BPS / 10_000.0) / K

    st["last_ts"] = now
    json.dump(st, open(STATE, "w"), indent=1)

    # P&L + annualised rate
    net = st["cum_funding"] - st["cum_cost"]
    days = (now - st["start_ts"]) / 86400
    apy = (net / days * 365 * 100) if days > 0.02 else 0.0    # simple annualisation on net-so-far
    new = not os.path.exists(PNL)
    with open(PNL, "a") as f:
        if new:
            f.write("ts,days,cum_funding_pct,cum_cost_pct,net_pct,apy_est_pct,book\n")
        f.write(f"{int(now)},{days:.3f},{st['cum_funding']*100:.4f},{st['cum_cost']*100:.4f},"
                f"{net*100:.4f},{apy:.1f},{'|'.join(book)}\n")

    print(f"hl_paper: {len(book)} positions | net {net*100:+.3f}% over {days:.2f}d "
          f"(~{apy:+.1f}% APY est) | book: "
          + ", ".join(f"{c}[{book[c]['side'][0]}{book[c]['ann_at_entry']*100:.0f}%]" for c in book))


if __name__ == "__main__":
    main()
