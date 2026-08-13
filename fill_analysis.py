"""fill_analysis.py — read the fill log the executor accumulates live and summarise it.

The executor logs two row types to fill_log.jsonl: 'place' (order + order-book FEATURES at
placement) and 'outcome' (did it fill, maker/taker, realized slippage, time-to-fill — the
LABELS). This reads them, pairs them by oid, and prints the stats that tell you whether the
maker strategy is working — and, once there are enough rows (~1k+), whether an ML fill model
is worth training. NO training here yet: this is the honest read of the data first.
"""
import json
import os
import statistics as st

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fill_log.jsonl")


def load():
    rows = []
    try:
        for line in open(LOG):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    except FileNotFoundError:
        return [], []
    return [r for r in rows if r.get("t") == "place"], [r for r in rows if r.get("t") == "outcome"]


def main():
    places, outcomes = load()
    if not places:
        print("fill_log.jsonl empty or absent — no live orders logged yet. (Expected pre-go-live.)")
        return
    n_fill = len(outcomes)
    fill_rate = 100 * n_fill / len(places) if places else 0
    makers = [o for o in outcomes if o.get("is_maker")]
    slips = [o["realized_slip_bps"] for o in outcomes if o.get("realized_slip_bps") is not None]
    ttf = [o["time_to_fill_s"] for o in outcomes if o.get("time_to_fill_s") is not None]
    print(f"orders placed:     {len(places)}")
    print(f"orders filled:     {n_fill}  ({fill_rate:.0f}% fill rate)")
    print(f"maker fills:       {len(makers)}/{n_fill}  ({100*len(makers)/n_fill:.0f}% maker)" if n_fill else "")
    if slips:
        print(f"realized slippage: median {st.median(slips):+.1f} bps  (negative = we EARNED edge as maker)")
    if ttf:
        print(f"time-to-fill:      median {st.median(ttf)/60:.1f} min")
    print(f"\nrows for ML: {n_fill} labelled examples. Train a fill-probability model at ~1000+.")


if __name__ == "__main__":
    main()
