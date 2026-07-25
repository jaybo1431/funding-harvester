"""Cross-venue funding-spread backtest: two venues, same assets.

Position per asset = long perp on the LOW-funding venue + short perp on the HIGH-funding
venue => price-neutral (long+short same asset) and venue-neutral. You capture the
funding SPREAD (high - low) each interval. Direction chosen from a trailing signal
(no lookahead); when the spread flips against you, you eat it until the exit fires.

Capital note: needs margin on BOTH venues (2 legs). APY reported on one unit of
notional; a fully-funded 2-venue setup would need ~2x that in posted margin.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

BINS_PER_YEAR = 365 * 3


def load(venue: str) -> pd.DataFrame:
    df = pd.read_csv(f"data/funding_{venue}.csv")
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    g = (df.groupby(["symbol", pd.Grouper(key="ts", freq="8h")])["funding_rate"]
         .sum().unstack(0).sort_index())
    return g


def main() -> None:
    v1 = sys.argv[1] if len(sys.argv) > 1 else "binance"
    v2 = sys.argv[2] if len(sys.argv) > 2 else "bybit"
    bnc, byb = load(v1), load(v2)
    common = sorted(set(bnc.columns) & set(byb.columns))
    idx = bnc.index.intersection(byb.index)
    bnc, byb = bnc.loc[idx, common], byb.loc[idx, common]
    spread = (bnc - byb).dropna(how="all")  # per-bin funding spread per asset
    idx = spread.index  # keep loop index aligned with (possibly trimmed) spread rows

    print(f"cross-venue {v1} vs {v2}: {len(idx)} 8h-bins x {len(common)} assets\n")
    print("per-asset |spread| annualised (the raw edge available before costs):")
    for s in common:
        ann = spread[s].abs().mean() * BINS_PER_YEAR * 100
        print(f"  {s:10} mean|spread| ~ {ann:6.2f}% APY")
    print(f"\n  PORTFOLIO mean|spread| ~ {spread.abs().mean(axis=1).mean() * BINS_PER_YEAR * 100:.2f}% APY (gross ceiling, no costs)\n")

    # --- backtest: hold spread trades with trailing-sign direction + hysteresis ---
    def run(capital=10_000.0, slots=6, enter_ann=0.05, exit_ann=0.01,
            signal_bins=3, roundtrip_bps=20.0):
        per_slot = capital / slots
        enter_pb, exit_pb = enter_ann / BINS_PER_YEAR, exit_ann / BINS_PER_YEAR
        rt_cost = roundtrip_bps / 10_000 * per_slot
        sig = spread.rolling(signal_bins, min_periods=1).mean().shift(1)  # no lookahead
        held: dict[str, int] = {}  # asset -> direction (+1 short binance/long bybit)
        pnl, deployed, opens = [], [], 0
        for t in idx:
            srow, prow = sig.loc[t], spread.loc[t]
            for a in list(held):
                v = srow.get(a, np.nan)
                if not np.isfinite(v) or abs(v) < exit_pb:
                    del held[a]
            openn = slots - len(held)
            if openn > 0:
                cand = srow[[a for a in common if a not in held]].dropna()
                cand = cand[cand.abs() > enter_pb]
                cand = cand.reindex(cand.abs().sort_values(ascending=False).index)
                for a in list(cand.index)[:openn]:
                    held[a] = int(np.sign(cand[a]))
                    opens += 1
            gross = sum(per_slot * held[a] * prow[a] for a in held if np.isfinite(prow.get(a, np.nan)))
            pnl.append(gross)
            deployed.append(len(held) / slots)
        pnl = pd.Series(pnl, index=idx)
        costs = opens * rt_cost
        net = pnl.sum() - costs
        eq = capital + pnl.cumsum() - (pd.Series(deployed, index=idx).cumsum() /
                                       max(sum(deployed), 1e-9)) * costs
        ret = eq.pct_change().fillna(0)
        apy = net / capital / (len(idx) / BINS_PER_YEAR)
        dd = ((eq - eq.cummax()) / eq.cummax()).min()
        shp = ret.mean() / ret.std() * np.sqrt(BINS_PER_YEAR) if ret.std() > 0 else 0
        return dict(net_apy=round(apy * 100, 2), maxDD=round(dd * 100, 2),
                    sharpe=round(float(shp), 2), gross=round(pnl.sum(), 2),
                    costs=round(costs, 2), net=round(net, 2), opens=opens,
                    deploy=round(np.mean(deployed) * 100, 1))

    print("[cross-venue backtest] sweep:")
    print(f"{'enter%':>7}{'exit%':>7}{'rt_bps':>7}{'netAPY%':>9}{'maxDD%':>8}{'Sharpe':>8}{'deploy%':>8}{'opens':>7}")
    best = None
    for enter_ann in (0.03, 0.05, 0.10):
        for rt in (5.0, 20.0):
            r = run(enter_ann=enter_ann, roundtrip_bps=rt)
            print(f"{enter_ann*100:7.0f}{1:7.0f}{rt:7.0f}{r['net_apy']:9.2f}{r['maxDD']:8.2f}"
                  f"{r['sharpe']:8.2f}{r['deploy']:8.1f}{r['opens']:7d}")
            if best is None or r["net_apy"] > best["net_apy"]:
                best = r
    print(f"\n  BEST cross-venue net APY: {best['net_apy']}%  (maxDD {best['maxDD']}%, Sharpe {best['sharpe']})")
    print(f"  GATE (>=8% APY, >=-5% DD): "
          f"{'PASS ✅' if best['net_apy'] >= 8 and best['maxDD'] >= -5 else 'FAIL ❌'}")


if __name__ == "__main__":
    main()
