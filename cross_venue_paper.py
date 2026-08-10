"""cross_venue_paper.py — PAPER cross-venue funding-SPREAD carry (HL ↔ Lighter).

The upgrade to the single-venue harvester. Instead of shorting the fattest-funding coin on ONE
venue and hedging delta with BTC (which carries a little basis risk), this books the SAME coin on
BOTH venues in opposite directions:

    short the venue paying the HIGHER funding  (collect it)
    long  the venue paying the LOWER  funding  (pay the smaller amount)
    net capture ≈ |funding_A − funding_B|  ← the SPREAD, and it's the same asset both legs,
    so the book is PERFECTLY delta-neutral with NO hedge leg needed.

This is strictly cleaner neutrality than the BTC-hedged single-venue book, and it harvests
funding DISPERSION between venues (often large on newer venues like Lighter). Same market-neutral,
latency-tolerant DNA as the proven edge — an additive module, not a new risk class.

Feeds (both already pulled on this box, both plain-symbol, both stdlib):
  • HL      — POST metaAndAssetCtxs, hourly funding annualised
  • Lighter — GET funding-rates (exchange=="lighter"), 8h funding annualised

Selection: top-K coins by spread that clear ENTRY_SPREAD, hysteresis exit at EXIT_SPREAD.
Cost: HL leg pays fees (2 sides of turnover), Lighter is 0% — so cost ≈ HL roundtrip only.
Read-only. NO keys, NO orders, NO money. Forward-proves before it ever joins the live pot.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "cross_venue_state.json")
CSV = os.path.join(HERE, "cross_venue_log.csv")

HL_URL = "https://api.hyperliquid.xyz/info"
LT_URL = "https://mainnet.zklighter.elliot.ai/api/v1/funding-rates"
HOURS_PER_YEAR = 24 * 365
LT_PERIODS_YR = 3 * 365                                       # Lighter funding is 8-hourly

K            = int(os.environ.get("XV_K", "3"))               # how many spreads to hold
ENTRY_SPREAD = float(os.environ.get("XV_ENTRY", "0.10"))     # open when spread ≥ 10% APY
EXIT_SPREAD  = float(os.environ.get("XV_EXIT", "0.03"))      # close when spread decays < 3% APY
SPREAD_CAP   = float(os.environ.get("XV_CAP", "3.0"))        # skip >300% APY = illiquid noise
# roundtrip cost in APY terms: HL maker both-sides turnover; Lighter 0% → HL only. Conservative.
COST_APY     = float(os.environ.get("XV_COST_APY", "0.06"))  # 6%/yr drag assumption on the HL leg


def _get(url, body=None):
    for a in range(4):
        try:
            if body is None:
                req = urllib.request.Request(url, headers={"User-Agent": "xv/1"})
            else:
                req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            time.sleep(2 * (a + 1))
    return None


def hl_funding() -> dict:
    """symbol -> annualised funding on Hyperliquid."""
    m = _get(HL_URL, {"type": "metaAndAssetCtxs"})
    if not m:
        return {}
    out = {}
    for u, ctx in zip(m[0]["universe"], m[1]):
        if u.get("isDelisted"):
            continue
        try:
            out[u["name"].upper()] = float(ctx.get("funding") or 0) * HOURS_PER_YEAR
        except (TypeError, ValueError):
            continue
    return out


def lighter_funding() -> dict:
    """symbol -> annualised funding on Lighter (8h → annualised)."""
    d = _get(LT_URL)
    if not d:
        return {}
    out = {}
    for x in d.get("funding_rates", []):
        if x.get("exchange") != "lighter":
            continue
        try:
            out[x["symbol"].upper()] = float(x.get("rate", 0)) * LT_PERIODS_YR
        except (TypeError, ValueError):
            continue
    return out


def spreads() -> list:
    """Every coin listed on BOTH venues, with its capturable funding spread and the trade
    direction. Sorted widest-spread first. spread = |hl − lt|; short the higher-funding leg."""
    hl, lt = hl_funding(), lighter_funding()
    common = set(hl) & set(lt)
    rows = []
    for c in common:
        h, l = hl[c], lt[c]
        sp = abs(h - l)
        if sp > SPREAD_CAP:                                   # illiquid distortion — skip
            continue
        short_venue = "HL" if h > l else "Lighter"           # short the venue paying MORE
        rows.append({"coin": c, "hl": h, "lt": l, "spread": sp, "short": short_venue})
    rows.sort(key=lambda r: -r["spread"])
    return rows


def _load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


def run():
    now = time.time()
    rows = spreads()
    if not rows:
        print("cross_venue: no common-listed coins / feeds down — skip")
        return
    by_coin = {r["coin"]: r for r in rows}
    st = _load(STATE, {"book": {}, "cum_funding": 0.0, "cum_cost": 0.0, "start_ts": now})
    book = st["book"]                                         # coin -> {spread_at_entry, short, ts}
    last = st.get("last_ts", now)
    dt_h = max(0.0, (now - last) / 3600.0)

    # 1) accrue: each held spread earns spread/yr, pays COST_APY/yr on the HL leg, split across K
    for coin, pos in book.items():
        r = by_coin.get(coin)
        live_sp = r["spread"] if r else 0.0
        st["cum_funding"] += (live_sp / HOURS_PER_YEAR) * dt_h / K
        st["cum_cost"] += (COST_APY / HOURS_PER_YEAR) * dt_h / K

    # 2) hysteresis exit: drop a spread that decayed below EXIT or vanished from a venue
    for coin in list(book):
        r = by_coin.get(coin)
        if not r or r["spread"] < EXIT_SPREAD:
            del book[coin]

    # 3) fill free slots with the widest spreads clearing ENTRY
    for r in rows:
        if len(book) >= K:
            break
        if r["coin"] in book or r["spread"] < ENTRY_SPREAD:
            continue
        book[r["coin"]] = {"spread_at_entry": round(r["spread"], 4), "short": r["short"], "ts": now}

    st["last_ts"] = now
    st["book"] = book
    json.dump(st, open(STATE, "w"), indent=1)

    net = st["cum_funding"] - st["cum_cost"]
    days = (now - st.get("start_ts", now)) / 86400
    apy = (net / days * 365 * 100) if days > 0.02 else 0.0

    new_file = not os.path.exists(CSV)
    with open(CSV, "a") as f:
        if new_file:
            f.write("ts,days,cum_funding_pct,cum_cost_pct,net_pct,apy_est_pct,book\n")
        bk = "|".join(f"{c}:{p['short'][0]}{p['spread_at_entry']*100:.0f}%" for c, p in book.items())
        f.write(f"{int(now)},{days:.3f},{st['cum_funding']*100:.4f},{st['cum_cost']*100:.4f},"
                f"{net*100:.4f},{apy:.1f},{bk}\n")

    print(f"cross_venue [{days:.1f}d] net {net*100:+.3f}% (~{apy:+.0f}% APY) | {len(book)} spreads held")
    for c, p in book.items():
        r = by_coin.get(c, {})
        drift = f" now {r.get('spread',0)*100:.0f}%" if r else " (gone)"
        print(f"   {c:8} short {p['short']:7} entry {p['spread_at_entry']*100:.0f}%{drift}")
    top = ", ".join(f"{r['coin']} {r['spread']*100:.0f}%({r['short'][0]})" for r in rows[:6])
    print("   widest now:", top)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "scan":         # just show the spreads, don't book
        for r in spreads()[:20]:
            print(f"{r['coin']:8} HL {r['hl']*100:+6.0f}%  LT {r['lt']*100:+6.0f}%  "
                  f"spread {r['spread']*100:5.0f}%  short {r['short']}")
    else:
        run()
