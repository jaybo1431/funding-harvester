"""Fetch Hyperliquid funding history across a BROAD perp universe (not just majors) —
the venue we'll actually trade. HL's richer carry lives in its alts. Output matches
the backtest format: data/funding_hl_broad.csv (symbol, ts, funding_rate)."""
import time, httpx, pandas as pd
URL = "https://api.hyperliquid.xyz/info"
DAYS = 365

def _post(c, body, tries=5):
    for a in range(tries):
        r = c.post(URL, json=body)
        if r.status_code == 429:
            time.sleep(3 * (a+1)); continue
        r.raise_for_status(); return r.json()
    return []

def fetch_funding(c, coin, start_ms, end_ms):
    out, cur = [], start_ms
    while cur < end_ms:
        rows = _post(c, {"type":"fundingHistory","coin":coin,"startTime":cur,"endTime":end_ms})
        if not rows: break
        out.extend(rows); last = rows[-1]["time"]
        if last <= cur: break
        cur = last + 1
        if len(rows) < 500 and last >= end_ms - 3600_000: break
        time.sleep(0.5)
    return out

with httpx.Client(timeout=25, headers={"User-Agent":"fh/0.2"}) as c:
    # universe + live context (to rank by open interest / volume for liquidity)
    meta = c.post(URL, json={"type":"metaAndAssetCtxs"}).json()
    universe = meta[0]["universe"]; ctxs = meta[1]
    coins = []
    for u, ctx in zip(universe, ctxs):
        if u.get("isDelisted"): continue
        oi = float(ctx.get("openInterest",0)) * float(ctx.get("markPx",0) or 0)
        coins.append((u["name"], oi))
    # take the top ~45 by notional OI (liquid enough to actually trade)
    coins = [n for n,_ in sorted(coins, key=lambda x:-x[1])[:30]]
    print(f"HL universe: {len(universe)} perps, fetching top {len(coins)} by OI")
    now = int(time.time()*1000); start = now - DAYS*24*3600*1000
    frames = []
    for i, coin in enumerate(coins):
        try:
            rows = fetch_funding(c, coin, start, now)
        except Exception as e:
            print(f"  {coin} FAIL {str(e)[:40]}"); continue
        if not rows: continue
        df = pd.DataFrame(rows)
        df["symbol"] = coin + "USDT"
        df["ts"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df["funding_rate"] = df["fundingRate"].astype(float)
        frames.append(df[["symbol","ts","funding_rate"]])
        if i % 10 == 0: print(f"  {i+1}/{len(coins)} {coin} ({len(rows)} rows)")
    out = pd.concat(frames, ignore_index=True)
    out.to_csv("data/funding_hl_broad.csv", index=False)
    print(f"saved {len(out)} rows, {out.symbol.nunique()} symbols -> data/funding_hl_broad.csv")
