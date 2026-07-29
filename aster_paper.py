"""aster_paper.py — LIVE paper-forward funding carry on Aster (perp DEX, Binance-style API).

Venue book #5. Reads Aster's funding via the public Binance-compatible endpoint
(fapi.asterdex.com/fapi/v1/premiumIndex — one call, all ~680 symbols). Same cross-sectional
top-K carry, accrues funding − costs. Read-only, NO keys/money.

NOTE: Aster funding cadence assumed 8-hourly (Binance-standard). The carry SELECTION is unaffected
by the cadence; only the reported APY scales — verify/tune AST_PERIODS_YR if needed.
Output: aster_paper_state.json, aster_paper_pnl.csv.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://fapi.asterdex.com/fapi/v1/premiumIndex"
TICKER_URL = "https://fapi.asterdex.com/fapi/v1/ticker/24hr"
STATE = os.path.join(HERE, "aster_paper_state.json")
PNL = os.path.join(HERE, "aster_paper_pnl.csv")
MIN_VOL_USD = float(os.environ.get("AST_MIN_VOL", "2000000"))   # liquidity filter — skip thin mirage funding

K = int(os.environ.get("AST_K", "3"))
ENTRY_ANN = float(os.environ.get("AST_ENTRY_ANN", "0.12"))
EXIT_ANN = float(os.environ.get("AST_EXIT_ANN", "0.03"))
ROUNDTRIP_BPS = float(os.environ.get("AST_ROUNDTRIP_BPS", "8"))   # Binance-like fee structure
FUND_CAP = float(os.environ.get("AST_FUND_CAP", "3.0"))
PERIODS_YR = int(os.environ.get("AST_PERIODS_YR", str(3 * 365)))  # 8h assumed
HOURS_PER_YEAR = 24 * 365


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ast/1", "Accept": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    return d if isinstance(d, list) else [d]


def live_funding():
    """symbol -> annualised funding, LIQUIDITY-FILTERED (24h quote volume >= MIN_VOL_USD) so we only
    trade coins whose funding is real and harvestable, not thin-market mirages that decay/churn."""
    try:
        fr = _get(URL)
        vol = {t.get("symbol"): float(t.get("quoteVolume") or 0) for t in _get(TICKER_URL)}
    except Exception:
        return {}
    out = {}
    for x in fr:
        try:
            ann = float(x.get("lastFundingRate") or 0) * PERIODS_YR
        except (TypeError, ValueError):
            continue
        if 0 < abs(ann) <= FUND_CAP and vol.get(x.get("symbol"), 0) >= MIN_VOL_USD:
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
        print("aster_paper: fetch failed — skip")
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
    print(f"aster_paper: {len(book)} positions | net {net*100:+.3f}% over {days:.2f}d "
          f"(~{apy:+.1f}% APY est) | book: "
          + ", ".join(f"{c}[{book[c]['side'][0]}{book[c]['ann_at_entry']*100:.0f}%]" for c in book))


if __name__ == "__main__":
    main()
