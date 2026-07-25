"""cross_sectional.py — CROSS-SECTIONAL funding-carry backtest (the real test).

The single-pair harvest capped at ~3.6% because majors' funding is compressed and one
pair whipsaws. But the live regime monitor shows the MEDIAN best-single opportunity is
~11% APY and something is HOT 35% of the time — the juice exists, it's just spread
across the universe and rotating. This harvests it properly:

  Each funding period, go DELTA-NEUTRAL on the top-K richest-carry coins — short the
  highest positive-funding perps (you RECEIVE funding), long the most negative-funding
  perps (also receive), each hedged with spot so the book is market-neutral. Always
  sitting on the fattest carry, diversified so no single pair can whipsaw the book.

Same honest, pre-registered GATE as the single-pair test:
    net APY >= 8%  AND  max drawdown <= 5%   over the collected window, realistic costs.

No-lookahead: the funding you EARN in a bin is that bin's realised funding on positions
chosen from the PRIOR bin's ranking. Costs charged on turnover (coins entering/leaving
the book), both legs. Pure stdlib + pandas (already a repo dep).
"""
from __future__ import annotations

import sys
import pandas as pd

DATA = "data/funding_binance.csv"
BIN_H = 8                      # align everything to 8h bins (majors' native cadence)
HOURS_PER_YEAR = 24 * 365


def load_bins(path: str = DATA) -> pd.DataFrame:
    """→ DataFrame indexed by 8h bin, columns = symbols, values = funding PAID that bin
    (fraction). Sub-8h-cadence alts have their intra-bin payments summed, so annualising
    is honest regardless of each coin's native interval."""
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    df = df.set_index("ts").sort_index()
    # sum each symbol's funding into 8h bins
    binned = (df.groupby("symbol")["funding_rate"]
                .resample(f"{BIN_H}h").sum().rename("f").reset_index())
    mat = binned.pivot(index="ts", columns="symbol", values="f")
    return mat


def backtest(mat: pd.DataFrame, k: int = 6, roundtrip_bps: float = 12.0,
             entry_ann: float = 0.15, exit_ann: float = 0.04) -> dict:
    """Hold-with-hysteresis delta-neutral carry (a real carry book, not a chaser).
      k          max positions (capital split k ways)
      entry_ann  only OPEN a new position if its annualised |funding| clears this
      exit_ann   HOLD an open position until its |funding| decays below this, then close
    No-lookahead: positions are chosen on the PRIOR bin's funding; we EARN the current
    bin's realised funding on whatever we were already holding. Cost = one round-trip
    per open (charged at open), amortised over k slots."""
    bins_per_year = HOURS_PER_YEAR / BIN_H
    rt = roundtrip_bps / 10_000.0
    entry_f = entry_ann / bins_per_year        # APY floors → per-bin fraction
    exit_f = exit_ann / bins_per_year

    held: dict = {}        # symbol -> entry side (+1 short a +funding perp / -1 long a -funding)
    slot_ret, deployed_frac = [], []
    prev_row = None
    for _, row in mat.iterrows():
        r = row.dropna()
        # 1) EARN this bin's realised funding on positions we already held (no lookahead)
        earn = 0.0
        for sym, side in list(held.items()):
            f = r.get(sym)
            if f is None:               # symbol missing this bin — treat as closed, no earn
                del held[sym]; continue
            earn += side * f            # short a +funding perp → +f; long a -funding → -(-|f|)=+|f|
        gross = earn / k if k else 0.0
        # 2) DECIDE next book from THIS bin's ranking (acts next bin): drop decayed, add rich
        opens = 0
        for sym in list(held):                       # exit decayed positions
            if sym not in r.index or abs(r[sym]) < exit_f:
                del held[sym]
        ranked = r.reindex(r.abs().sort_values(ascending=False).index)
        for sym, f in ranked.items():                # fill free slots with rich carry
            if len(held) >= k:
                break
            if sym in held or abs(f) < entry_f:
                continue
            held[sym] = 1 if f > 0 else -1
            opens += 1
        cost = (opens * rt) / k if k else 0.0        # one round-trip per open, /k capital
        slot_ret.append(gross - cost)
        deployed_frac.append(len(held) / k if k else 0.0)

    s = pd.Series(slot_ret, index=mat.index)
    equity = (1 + s).cumprod()
    total_ret = equity.iloc[-1] - 1
    days = (mat.index[-1] - mat.index[0]).total_seconds() / 86400
    apy = (equity.iloc[-1] ** (365 / days) - 1) if days > 0 else 0.0
    peak = equity.cummax()
    max_dd = ((equity - peak) / peak).min()
    return {
        "k": k, "roundtrip_bps": roundtrip_bps,
        "net_apy_pct": round(apy * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "total_return_pct": round(total_ret * 100, 2),
        "avg_deployed_pct": round(pd.Series(deployed_frac).mean() * 100, 0),
        "days": round(days),
        "gate_pass": bool(apy >= 0.08 and abs(max_dd) <= 0.05),
    }


def main():
    mat = load_bins(sys.argv[1] if len(sys.argv) > 1 else DATA)
    print(f"universe: {mat.shape[1]} symbols, {mat.shape[0]} × {BIN_H}h bins "
          f"({round(mat.shape[0]*BIN_H/24)} days)\n")
    print(f"{'k':>3} {'rt_bps':>7} {'net_APY%':>9} {'maxDD%':>8} {'deployed%':>10} {'GATE':>6}")
    for rt in (8.0, 12.0, 20.0):
        for k in (3, 4, 6, 8, 10):
            r = backtest(mat, k=k, roundtrip_bps=rt)
            gate = "PASS ✅" if r["gate_pass"] else "fail"
            print(f"{k:>3} {rt:>7.0f} {r['net_apy_pct']:>9} {r['max_drawdown_pct']:>8} "
                  f"{r['avg_deployed_pct']:>10} {gate:>6}")
    print("\nGATE = net APY ≥ 8% AND max drawdown ≤ 5%")


if __name__ == "__main__":
    main()
