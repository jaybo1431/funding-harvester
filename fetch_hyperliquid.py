"""Fetch Hyperliquid funding-rate HISTORY (hourly) for the majors, to backtest the
CEX<->DEX spread (short HL to collect its ~11% baseline funding, long Binance) through
the same honest gate. Symbols saved as BTCUSDT... to match the Binance CSV.

Output: data/funding_hyperliquid.csv (symbol, ts, funding_rate)   [hourly rows]
"""
from __future__ import annotations

import time

import httpx
import pandas as pd

URL = "https://api.hyperliquid.xyz/info"
DAYS = 365
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "LINK", "LTC", "ADA", "AVAX"]


def fetch(client: httpx.Client, coin: str, start_ms: int, end_ms: int) -> list[dict]:
    out, cur = [], start_ms
    while cur < end_ms:
        r = client.post(URL, json={"type": "fundingHistory", "coin": coin,
                                   "startTime": cur, "endTime": end_ms})
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out.extend(rows)
        last = rows[-1]["time"]
        if last <= cur:
            break
        cur = last + 1
        if len(rows) < 500:
            # HL returns up to 500; fewer means we caught up (but keep going by time)
            if last >= end_ms - 3600_000:
                break
        time.sleep(0.15)
    return out


def main() -> None:
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - DAYS * 24 * 3600 * 1000
    frames = []
    with httpx.Client(timeout=20, headers={"User-Agent": "funding-harvester/0.1"}) as c:
        for coin in COINS:
            try:
                rows = fetch(c, coin, start_ms, now_ms)
            except Exception as e:  # noqa: BLE001
                print(f"  {coin:6} FAILED: {e}")
                continue
            if not rows:
                print(f"  {coin:6} no data")
                continue
            df = pd.DataFrame(rows)
            df["ts"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True)
            df["funding_rate"] = df["fundingRate"].astype(float)
            df["symbol"] = coin + "USDT"
            df = df[["symbol", "ts", "funding_rate"]].drop_duplicates("ts")
            frames.append(df)
            ann = df["funding_rate"].mean() * 24 * 365 * 100  # hourly -> APY
            print(f"  {coin:6} {len(df):5d} rows  {df['ts'].min().date()}..{df['ts'].max().date()}  avg~{ann:6.1f}% APY")
    out = pd.concat(frames, ignore_index=True)
    out.to_csv("data/funding_hyperliquid.csv", index=False)
    print(f"\nsaved {len(out)} rows -> data/funding_hyperliquid.csv")


if __name__ == "__main__":
    main()
