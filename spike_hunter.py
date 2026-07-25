"""spike_hunter.py — backtest the 2 spike-hunter dials vs the flat carry (HL data).
Dial1 concentration alpha: weight positions by funding^alpha (0=flat, 1=funding-weighted).
Dial2 regime leverage: scale exposure with the bin's funding heat, capped."""
import sys
import pandas as pd
from cross_sectional import load_bins, HOURS_PER_YEAR, BIN_H

def bt(mat, k=4, alpha=0.0, regime_lev=False, max_lev=3.0, base_lev=1.0,
       roundtrip_bps=8, entry_ann=0.12, exit_ann=0.03):
    bpy = HOURS_PER_YEAR / BIN_H
    rt = roundtrip_bps/10000; ef, xf = entry_ann/bpy, exit_ann/bpy
    held={}; rets=[]
    # heat scale: median |funding| across universe each bin → leverage 1..max
    heat_series = mat.abs().median(axis=1)
    hmed = heat_series.median() or 1e-9
    for ts,row in mat.iterrows():
        r=row.dropna()
        # regime leverage from this bin's heat
        if regime_lev:
            lev = min(max_lev, base_lev * (heat_series[ts]/hmed))
        else:
            lev = base_lev
        # concentration weights on held
        if held:
            w = {c: (abs(r[c])**alpha if c in r.index else 0) for c in held}
            tot = sum(w.values()) or 1e-9
            earn = sum((w[c]/tot)*abs(r[c]) for c in held if c in r.index)
        else:
            earn = 0.0
        for c in list(held):
            if c not in r.index or abs(r[c])<xf: del held[c]
        opens=0
        for c in r.abs().sort_values(ascending=False).index:
            if len(held)>=k: break
            if c in held or abs(r[c])<ef: continue
            held[c]=1; opens+=1
        cost=(opens*rt)/max(len(held),1)
        rets.append((earn - cost)*lev)
    s=pd.Series(rets,index=mat.index); eq=(1+s).cumprod()
    days=(mat.index[-1]-mat.index[0]).total_seconds()/86400
    apy=(eq.iloc[-1]**(365/days)-1) if days>0 else 0
    dd=((eq-eq.cummax())/eq.cummax()).min()
    return apy*100, dd*100

m=load_bins('data/funding_hl_broad.csv')
print(f"HL {m.shape[1]} syms, {m.shape[0]} bins\n")
print(f"{'config':38} {'net_APY%':>9} {'maxDD%':>8}")
print(f"{'FLAT (base carry, k=4)':38} {bt(m,k=4)[0]:>9.1f} {bt(m,k=4)[1]:>8.2f}")
print(f"{'+ concentration alpha=0.5':38} {bt(m,k=4,alpha=0.5)[0]:>9.1f} {bt(m,k=4,alpha=0.5)[1]:>8.2f}")
print(f"{'+ concentration alpha=1.0':38} {bt(m,k=4,alpha=1.0)[0]:>9.1f} {bt(m,k=4,alpha=1.0)[1]:>8.2f}")
print(f"{'+ regime leverage (max 3x)':38} {bt(m,k=4,regime_lev=True)[0]:>9.1f} {bt(m,k=4,regime_lev=True)[1]:>8.2f}")
print(f"{'+ BOTH (alpha=0.7, regime 3x)':38} {bt(m,k=4,alpha=0.7,regime_lev=True)[0]:>9.1f} {bt(m,k=4,alpha=0.7,regime_lev=True)[1]:>8.2f}")
print(f"{'+ BOTH aggressive (a=1, max 5x)':38} {bt(m,k=3,alpha=1.0,regime_lev=True,max_lev=5)[0]:>9.1f} {bt(m,k=3,alpha=1.0,regime_lev=True,max_lev=5)[1]:>8.2f}")
