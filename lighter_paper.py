"""lighter_paper.py — LIVE paper-forward funding carry on Lighter (zk-rollup perp DEX).

Third venue book (sibling of hl_paper.py / drift_paper.py). Reads Lighter's OWN funding via the
public REST feed (mainnet.zklighter.elliot.ai/api/v1/funding-rates, filtered to exchange=="lighter",
~202 markets INCLUDING tokenized-stock perps TSLA/MRVL — uncorrelated RWA funding). Runs the SAME
cross-sectional top-K carry, accrues funding − costs. Read-only, NO keys/money.

Lighter funding is 8-hourly. Lighter charges 0% fees, so turnover cost ≈ slippage only (tiny) — the
biggest cost-headroom in the venue field. Output: lighter_paper_state.json, lighter_paper_pnl.csv.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://mainnet.zklighter.elliot.ai/api/v1/funding-rates"
STATE = os.path.join(HERE, "lighter_paper_state.json")
PNL = os.path.join(HERE, "lighter_paper_pnl.csv")

K = int(os.environ.get("LT_K", "3"))
ENTRY_ANN = float(os.environ.get("LT_ENTRY_ANN", "0.12"))
EXIT_ANN = float(os.environ.get("LT_EXIT_ANN", "0.03"))
ROUNDTRIP_BPS = float(os.environ.get("LT_ROUNDTRIP_BPS", "2"))   # Lighter 0% fees → slippage only
FUND_CAP = float(os.environ.get("LT_FUND_CAP", "3.0"))          # skip |funding|>300% APY = illiquid noise
PERIODS_YR = 3 * 365                                             # 8-hourly funding
HOURS_PER_YEAR = 24 * 365


def live_funding():
    """symbol -> annualised funding, from Lighter's own rates (8h)."""
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "lt/1", "Accept": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    except Exception:
        return {}
    out = {}
    for x in d.get("funding_rates", []):
        if x.get("exchange") != "lighter":
            continue
        try:
            ann = float(x.get("rate", 0)) * PERIODS_YR
        except (TypeError, ValueError):
            continue
        if abs(ann) <= FUND_CAP:
            out[x["symbol"]] = ann
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
        print("lighter_paper: fetch failed — skip")
        return
    st = _load(STATE, {"book": {}, "cum_funding": 0.0, "cum_cost": 0.0,
                       "start_ts": now, "last_ts": now})
    book = st["book"]
    dt_h = (now - st["last_ts"]) / 3600 if st["last_ts"] else 0

    for coin in book:
        ann = fund.get(coin, 0.0)
        st["cum_funding"] += (abs(ann) / HOURS_PER_YEAR) * dt_h / K

    for coin in list(book):
        ann = fund.get(coin, 0.0)
        if coin not in fund or abs(ann) < EXIT_ANN:
            del book[coin]

    ranked = sorted(fund.items(), key=lambda kv: -abs(kv[1]))
    opens = 0
    for coin, ann in ranked:
        if len(book) >= K:
            break
        if coin in book or abs(ann) < ENTRY_ANN:
            continue
        book[coin] = {"side": "short" if ann > 0 else "long", "ann_at_entry": round(ann, 3)}
        opens += 1
    st["cum_cost"] += opens * (ROUNDTRIP_BPS / 10_000.0) / K

    st["last_ts"] = now
    json.dump(st, open(STATE, "w"), indent=1)

    net = st["cum_funding"] - st["cum_cost"]
    days = (now - st["start_ts"]) / 86400
    apy = (net / days * 365 * 100) if days > 0.02 else 0.0
    new = not os.path.exists(PNL)
    with open(PNL, "a") as f:
        if new:
            f.write("ts,days,cum_funding_pct,cum_cost_pct,net_pct,apy_est_pct,book\n")
        f.write(f"{int(now)},{days:.3f},{st['cum_funding']*100:.4f},{st['cum_cost']*100:.4f},"
                f"{net*100:.4f},{apy:.1f},{'|'.join(book)}\n")
    print(f"lighter_paper: {len(book)} positions | net {net*100:+.3f}% over {days:.2f}d "
          f"(~{apy:+.1f}% APY est) | book: "
          + ", ".join(f"{c}[{book[c]['side'][0]}{book[c]['ann_at_entry']*100:.0f}%]" for c in book))


if __name__ == "__main__":
    main()
