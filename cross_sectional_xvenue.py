"""cross_sectional_xvenue.py — CROSS-SECTIONAL CROSS-VENUE funding-spread carry.

The next edge beyond single-venue carry: the same coin often pays very different funding
on two venues. Capture the SPREAD — for the top-K widest-spread coins, short the perp on
the HIGH-funding venue (collect) + long the perp on the LOW-funding venue (pay less).
Long+short same coin ⇒ price-neutral AND venue-neutral, and NO spot hedge needed (both
legs are perps that cancel). Net per position = |funding spread| between the venues.

Proof-of-concept on HL vs Binance (data we have). For the UK-executable version, swap
Binance → Drift (Solana, via the Helius key) — same math, different venue. Same honest
gate (net APY ≥8%, max DD ≤5%), hysteresis, no-lookahead, realistic costs (2 perp legs).

Usage: python3 cross_sectional_xvenue.py [venueA.csv] [venueB.csv]
"""
from __future__ import annotations
import sys
import pandas as pd
from cross_sectional import load_bins, HOURS_PER_YEAR, BIN_H


def spread_matrix(a_csv: str, b_csv: str):
    a, b = load_bins(a_csv), load_bins(b_csv)
    common = sorted(set(a.columns) & set(b.columns))
    idx = a.index.intersection(b.index)
    a, b = a.loc[idx, common], b.loc[idx, common]
    return (a - b), common          # per-bin funding spread (venueA − venueB) per coin


def backtest(spread: pd.DataFrame, k: int = 4, roundtrip_bps: float = 12.0,
             entry_ann: float = 0.10, exit_ann: float = 0.03) -> dict:
    """Hold-with-hysteresis on the widest |spread| coins. roundtrip_bps here = full cycle
    of BOTH perp legs (open+close), since a cross-venue position is 2 perps."""
    bins_per_year = HOURS_PER_YEAR / BIN_H
    rt = roundtrip_bps / 10_000.0
    entry_f, exit_f = entry_ann / bins_per_year, exit_ann / bins_per_year
    held: dict = {}          # coin -> side (+1 short-A/long-B, set at entry; sign of spread then)
    slot_ret, deployed = [], []
    for _, row in spread.iterrows():
        r = row.dropna()
        # SIDE-AWARE earn: your side is fixed at entry; if the spread flips you LOSE.
        earn = sum(side * r[s] for s, side in held.items() if s in r.index) / k if k else 0.0
        for s in list(held):                              # exit when the (signed) spread decays/flips
            if s not in r.index or held[s] * r[s] < exit_f:
                del held[s]
        opens = 0
        for s in r.abs().sort_values(ascending=False).index:   # fill richest spreads
            if len(held) >= k:
                break
            if s in held or abs(r[s]) < entry_f:
                continue
            held[s] = 1 if r[s] > 0 else -1               # short high-funding venue leg
            opens += 1
        cost = (opens * rt) / k if k else 0.0
        slot_ret.append(earn - cost)
        deployed.append(len(held) / k if k else 0.0)
    s = pd.Series(slot_ret, index=spread.index)
    eq = (1 + s).cumprod()
    days = (spread.index[-1] - spread.index[0]).total_seconds() / 86400
    apy = (eq.iloc[-1] ** (365 / days) - 1) if days > 0 else 0.0
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    return {"k": k, "net_apy_pct": round(apy * 100, 2), "max_drawdown_pct": round(dd * 100, 2),
            "avg_deployed_pct": round(pd.Series(deployed).mean() * 100, 0), "days": round(days),
            "gate_pass": bool(apy >= 0.08 and abs(dd) <= 0.05)}


def main():
    a = sys.argv[1] if len(sys.argv) > 1 else "data/funding_hl_broad.csv"
    b = sys.argv[2] if len(sys.argv) > 2 else "data/funding_binance.csv"
    sp, common = spread_matrix(a, b)
    print(f"cross-venue: {a.split('/')[-1]} vs {b.split('/')[-1]} | {len(common)} common coins, "
          f"{sp.shape[0]} bins ({round(sp.shape[0]*BIN_H/24)}d)\n")
    print(f"{'k':>3} {'net_APY%':>9} {'maxDD%':>8} {'deployed%':>10} {'GATE':>6}")
    for k in (2, 3, 4, 6):
        r = backtest(sp, k=k)
        print(f"{k:>3} {r['net_apy_pct']:>9} {r['max_drawdown_pct']:>8} {r['avg_deployed_pct']:>10} "
              f"{'PASS ✅' if r['gate_pass'] else 'fail':>6}")
    # out-of-sample
    n = len(sp); half = n // 2
    tr, te = sp.iloc[:half], sp.iloc[half:]
    bk = max((2, 3, 4, 6), key=lambda k: backtest(tr, k=k)["net_apy_pct"])
    rt = backtest(te, k=bk)
    print(f"\nOUT-OF-SAMPLE: best-on-train k={bk} → TEST {rt['net_apy_pct']:+.1f}% APY, DD {rt['max_drawdown_pct']}%")
    print("GATE = net APY ≥ 8% AND max DD ≤ 5%")


if __name__ == "__main__":
    main()
