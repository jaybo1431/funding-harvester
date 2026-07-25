"""Fetch historical perpetual funding-rate history from Binance USD-M futures.

Public endpoint, no API key. Paginates /fapi/v1/fundingRate back over `DAYS`.
Interval hours are inferred per-row from the spacing between funding stamps
(Binance runs 8h on majors, 4h/1h on some alts), so annualisation is honest.

Output: data/funding_binance.csv  (symbol, ts, funding_rate, interval_h)

The point of this file: get REAL funding history so the backtest can answer
"does hold-when-positive delta-neutral clear ~8% APY at <5% drawdown?" BEFORE
any execution code exists.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
import pandas as pd

BASE = "https://fapi.binance.com"
DAYS = 365
# Liquid majors + a spread of higher-funding alts (alts carry richer funding).
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT", "DOTUSDT",
    "NEARUSDT", "SUIUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT",
    "TIAUSDT", "SEIUSDT", "WLDUSDT", "PEPEUSDT",
]


def fetch_funding(client: httpx.Client, symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    """Page through funding history (<=1000 rows/call) from start to end."""
    out: list[dict] = []
    cur = start_ms
    while cur < end_ms:
        r = client.get(
            f"{BASE}/fapi/v1/fundingRate",
            params={"symbol": symbol, "startTime": cur, "endTime": end_ms, "limit": 1000},
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out.extend(rows)
        last = rows[-1]["fundingTime"]
        if len(rows) < 1000:
            break
        cur = last + 1
        time.sleep(0.25)  # be polite to the public endpoint
    return out


def main() -> None:
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - DAYS * 24 * 3600 * 1000
    frames = []
    with httpx.Client(timeout=20, headers={"User-Agent": "funding-harvester/0.1"}) as c:
        for sym in SYMBOLS:
            try:
                rows = fetch_funding(c, sym, start_ms, now_ms)
            except Exception as e:  # noqa: BLE001
                print(f"  {sym:12} FAILED: {e}")
                continue
            if not rows:
                print(f"  {sym:12} no data")
                continue
            df = pd.DataFrame(rows)
            df["ts"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
            df["funding_rate"] = df["fundingRate"].astype(float)
            df = df[["ts", "funding_rate"]].sort_values("ts")
            # infer interval hours from spacing (fallback 8h)
            dt_h = df["ts"].diff().dt.total_seconds().div(3600)
            df["interval_h"] = dt_h.round().fillna(8).clip(lower=1, upper=8)
            df["symbol"] = sym
            frames.append(df)
            ann = df["funding_rate"].mean() * (8760 / df["interval_h"].mean()) * 100
            print(f"  {sym:12} {len(df):5d} rows  {df['ts'].min().date()}..{df['ts'].max().date()}  avg~{ann:6.1f}% APY")
    if not frames:
        raise SystemExit("no data fetched")
    alldf = pd.concat(frames, ignore_index=True)[["symbol", "ts", "funding_rate", "interval_h"]]
    alldf.to_csv("data/funding_binance.csv", index=False)
    print(f"\nsaved {len(alldf)} rows across {alldf['symbol'].nunique()} symbols -> data/funding_binance.csv")


if __name__ == "__main__":
    main()
