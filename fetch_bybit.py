"""Fetch Bybit linear-perp funding history for the majors, to test the CROSS-VENUE
funding-spread strategy (long perp on the low-funding venue, short perp on the
high-funding venue for the SAME asset => price- and venue-neutral, capture the spread).

Output: data/funding_bybit.csv (symbol, ts, funding_rate)
"""
from __future__ import annotations

import time

import httpx
import pandas as pd

BASE = "https://api.bybit.com"
DAYS = 365
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "LINKUSDT", "LTCUSDT", "ADAUSDT", "AVAXUSDT"]


def fetch(client: httpx.Client, symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    """Bybit returns newest-first, <=200/call; page backward via endTime."""
    out, cursor_end = [], end_ms
    while cursor_end > start_ms:
        r = client.get(f"{BASE}/v5/market/funding/history",
                       params={"category": "linear", "symbol": symbol,
                               "startTime": start_ms, "endTime": cursor_end, "limit": 200})
        r.raise_for_status()
        rows = r.json().get("result", {}).get("list", [])
        if not rows:
            break
        out.extend(rows)
        oldest = int(rows[-1]["fundingRateTimestamp"])
        if len(rows) < 200 or oldest <= start_ms:
            break
        cursor_end = oldest - 1
        time.sleep(0.2)
    return out


def main() -> None:
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - DAYS * 24 * 3600 * 1000
    frames = []
    with httpx.Client(timeout=20, headers={"User-Agent": "funding-harvester/0.1"}) as c:
        for sym in SYMBOLS:
            try:
                rows = fetch(c, sym, start_ms, now_ms)
            except Exception as e:  # noqa: BLE001
                print(f"  {sym:12} FAILED: {e}")
                continue
            if not rows:
                print(f"  {sym:12} no data")
                continue
            df = pd.DataFrame(rows)
            df["ts"] = pd.to_datetime(df["fundingRateTimestamp"].astype("int64"), unit="ms", utc=True)
            df["funding_rate"] = df["fundingRate"].astype(float)
            df["symbol"] = sym
            frames.append(df[["symbol", "ts", "funding_rate"]])
            print(f"  {sym:12} {len(df):5d} rows  {df['ts'].min().date()}..{df['ts'].max().date()}")
    out = pd.concat(frames, ignore_index=True)
    out.to_csv("data/funding_bybit.csv", index=False)
    print(f"\nsaved {len(out)} rows -> data/funding_bybit.csv")


if __name__ == "__main__":
    main()
