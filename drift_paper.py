"""drift_paper.py — LIVE paper-forward harness for the Drift (Solana) funding carry.

The Solana sibling of hl_paper.py — same validated cross-sectional carry, second
independent book. Reads Drift perp funding ON-CHAIN via driftpy (one batched
getMultipleAccounts on the free public Solana RPC — no Helius/paid RPC needed), runs the
SAME top-K |funding| + hysteresis selection, accrues funding − costs. Read-only, no keys,
no money. Forward-proves the carry on Drift the same way HL is being proved.

Delta-neutral: short the high-funding perps / long the negative-funding perps, hedged so
price nets ~0 → return = |funding| collected − costs. Runs hourly.
Output: drift_paper_state.json, drift_paper_pnl.csv. (Runs in a container — needs driftpy.)
"""
from __future__ import annotations
import asyncio
import glob
import json
import os
import time

import driftpy
from anchorpy import Idl, Program, Provider, Wallet
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from driftpy.addresses import get_perp_market_public_key
from driftpy.constants.config import DRIFT_PROGRAM_ID

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "drift_paper_state.json")
PNL = os.path.join(HERE, "drift_paper_pnl.csv")
RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com")

K = int(os.environ.get("DR_K", "3"))
ENTRY_ANN = float(os.environ.get("DR_ENTRY_ANN", "0.15"))   # Drift funding runs richer → higher floor
EXIT_ANN = float(os.environ.get("DR_EXIT_ANN", "0.03"))
ROUNDTRIP_BPS = float(os.environ.get("DR_ROUNDTRIP_BPS", "10"))
FUND_CAP = float(os.environ.get("DR_FUND_CAP", "5.0"))      # skip |funding|>500% APY = illiquid noise
N_MARKETS = int(os.environ.get("DR_N_MARKETS", "75"))
HRS_YR = 24 * 365


async def live_funding() -> dict:
    """coin -> annualised funding, from Drift perp-market accounts (1 batched RPC call)."""
    idl = Idl.from_json(open(glob.glob(os.path.dirname(driftpy.__file__) + "/idl/drift.json")[0]).read())
    conn = AsyncClient(RPC)
    try:
        prog = Program(idl, DRIFT_PROGRAM_ID, Provider(conn, Wallet(Keypair())))
        pks = [get_perp_market_public_key(DRIFT_PROGRAM_ID, i) for i in range(N_MARKETS)]
        accts = await prog.account["PerpMarket"].fetch_multiple(pks)
    finally:
        await conn.close()
    out = {}
    for m in accts:
        if m is None:
            continue
        # only fully-active markets (status Initialized=0 excluded; Active enum varies → use twap+status)
        twap = m.amm.historical_oracle_data.last_oracle_price_twap
        if twap == 0:
            continue
        try:
            name = bytes(m.name).decode("utf-8", "ignore").strip()
        except Exception:
            continue
        ann = (m.amm.last_funding_rate / 1e9) / (twap / 1e6) * HRS_YR
        if abs(ann) > FUND_CAP:            # illiquid/new market distortion — skip
            continue
        out[name] = ann
    return out


def _load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


def step(fund: dict):
    now = time.time()
    st = _load(STATE, {"book": {}, "cum_funding": 0.0, "cum_cost": 0.0,
                       "start_ts": now, "last_ts": now})
    book = st["book"]
    dt_h = (now - st["last_ts"]) / 3600 if st["last_ts"] else 0

    # 1) accrue funding earned on held positions since last run
    for coin in book:
        ann = fund.get(coin)
        if ann is not None:
            st["cum_funding"] += (abs(ann) / HRS_YR) * dt_h / K

    # 2) exit decayed / gone
    for coin in list(book):
        ann = fund.get(coin)
        if ann is None or abs(ann) < EXIT_ANN:
            del book[coin]

    # 3) fill free slots with the richest carry above the entry floor
    ranked = sorted(fund.items(), key=lambda kv: -abs(kv[1]))
    opens = 0
    for coin, ann in ranked:
        if len(book) >= K:
            break
        if coin in book or abs(ann) < ENTRY_ANN:
            continue
        book[coin] = {"side": "short" if ann > 0 else "long", "ann_at_entry": round(ann, 3)}
        opens += 1
    st["cum_cost"] += opens * (ROUNDTRIP_BPS / 10_000.0) / K
    st["last_ts"] = now
    json.dump(st, open(STATE, "w"), indent=1)

    net = st["cum_funding"] - st["cum_cost"]
    days = (now - st["start_ts"]) / 86400
    apy = (net / days * 365 * 100) if days > 0.02 else 0.0
    new = not os.path.exists(PNL)
    with open(PNL, "a") as f:
        if new:
            f.write("ts,days,cum_funding_pct,cum_cost_pct,net_pct,apy_est_pct,book\n")
        f.write(f"{int(now)},{days:.3f},{st['cum_funding']*100:.4f},{st['cum_cost']*100:.4f},"
                f"{net*100:.4f},{apy:.1f},{'|'.join(book)}\n")
    print(f"drift_paper: {len(book)} positions | net {net*100:+.3f}% over {days:.2f}d "
          f"(~{apy:+.1f}% APY est) | book: "
          + ", ".join(f"{c}[{book[c]['side'][0]}{book[c]['ann_at_entry']*100:.0f}%]" for c in book))


async def main():
    try:
        fund = await live_funding()
    except Exception as e:  # noqa: BLE001
        print(f"drift_paper: Drift fetch failed ({type(e).__name__}: {str(e)[:60]}) — skip")
        return
    if not fund:
        print("drift_paper: no funding data — skip")
        return
    step(fund)


async def loop():
    """Container mode: run hourly forever (driftpy import is slow, so stay resident)."""
    while True:
        try:
            await main()
        except Exception as e:  # noqa: BLE001
            print(f"drift_paper loop blip: {type(e).__name__}: {str(e)[:60]}", flush=True)
        await asyncio.sleep(int(os.environ.get("DR_INTERVAL_S", "3600")))


if __name__ == "__main__":
    asyncio.run(loop() if os.environ.get("DR_LOOP") == "1" else main())
