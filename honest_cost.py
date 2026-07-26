"""honest_cost.py — READ-ONLY. Re-price the paper books under REALISTIC costs.

The live paper number (cum_funding − cum_cost) is OPTIMISTIC: it assumes maker fills at 8bps
and 100% funding capture (perfect hedge). This re-computes the TRUE net rate from the SAME
accumulated data under honest assumptions, so we know what to actually expect live — before a
penny moves. Touches nothing, changes nothing; pure analysis.

Two real drags the headline ignores:
  • Turnover cost — if maker orders don't all fill you pay taker (HL taker ~45bps). Model a
    higher effective roundtrip bps. Cost scales linearly: realistic_cost = cum_cost × (R / R_base).
  • Hedge imperfection — you don't capture 100% of the |funding|; basis/slippage on the hedge
    leg skims some. Model a haircut h on captured funding.
"""
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# (label, state file, roundtrip bps the paper cost was computed with)
BOOKS = [
    ("HL Flat", "hl_paper_state.json", 8),
    ("HL Conc", "hl_paper_conc_state.json", 8),
    ("Drift", "drift_paper_state.json", 10),
]
# (label, effective roundtrip bps, funding-capture haircut)
SCENARIOS = [
    ("headline", None, 0.0),                 # the current optimistic number
    ("realistic", 15, 0.10),                 # mixed maker/taker + 10% hedge slip
    ("conservative", 25, 0.20),              # mostly taker + 20% hedge slip
]
GATE = 8.0  # net APY % gate


def apy_for(F, C, days, R, h, R_base):
    net = (F - C) if R is None else (F * (1 - h) - C * (R / R_base))
    return (net / days * 365 * 100) if days > 0.02 else 0.0


print("HONEST-COST RE-PRICING (read-only) — net APY under realistic assumptions\n")
hdr = f"{'book':9}{'days':>6}  " + "  ".join(f"{s[0]:>13}" for s in SCENARIOS)
print(hdr)
print("-" * len(hdr))
for name, f, rbase in BOOKS:
    try:
        st = json.load(open(os.path.join(HERE, f)))
    except Exception:
        print(f"{name:9}  (no data)")
        continue
    F = st.get("cum_funding", 0.0)
    C = st.get("cum_cost", 0.0)
    days = (time.time() - st.get("start_ts", time.time())) / 86400
    cells = []
    for _, R, h in SCENARIOS:
        a = apy_for(F, C, days, R, h, rbase)
        cells.append(f"{a:+.0f}% {'✓' if a >= GATE else '✗'}")
    print(f"{name:9}{days:>6.1f}  " + "  ".join(f"{c:>13}" for c in cells))

print(f"\n✓/✗ = clears the {GATE:.0f}% net gate. 'realistic' is the number to trust for go-live.")
print("Headline is funding-only (no slippage/hedge drag) — expect the live rate near 'realistic'.")
