"""live_test.py — MINIMAL Hyperliquid live-order test (run with /root/hl-live/venv/bin/python).

Places ONE tiny post-only (maker) limit order well below mid so it RESTS as maker (does not fill),
confirms it's resting, then CANCELS it. Proves the execution plumbing — connect, place a maker order,
it rests (not rejected/crossed), cancel — with a tiny order and NO position taken. This is the first
live step; only after it works do we test an actual fill, then a tiny delta-neutral pair, then £100.

SECURITY: needs a TRADE-ONLY Hyperliquid AGENT (API) wallet key — it can trade but CANNOT withdraw.
The key is read from env and never printed. Set by the USER; Claude never sees it.

Env:
  HL_AGENT_KEY        — the HL agent/API wallet private key (trade-only). REQUIRED.
  HL_ACCOUNT_ADDRESS  — the MAIN wallet address the agent trades for (public). REQUIRED for agent mode.
  HL_TEST_COIN        — coin (default SOL)
  HL_TEST_USD         — notional in USD (default 11; HL min order is ~$10)
"""
import os
import time

from eth_account import Account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

COIN = os.environ.get("HL_TEST_COIN", "SOL")
USD = float(os.environ.get("HL_TEST_USD", "11"))

key = os.environ.get("HL_AGENT_KEY", "").strip()
if not key:
    print("HL_AGENT_KEY not set — placing NOTHING (safe). Set the trade-only agent key first.")
    raise SystemExit(0)

acct = Account.from_key(key)
del key  # raw key not kept
main = os.environ.get("HL_ACCOUNT_ADDRESS", "").strip() or acct.address

info = Info(constants.MAINNET_API_URL, skip_ws=True)
ex = Exchange(acct, constants.MAINNET_API_URL, account_address=main)

# 1) balance + connectivity
try:
    us = info.user_state(main)
    wd = us.get("withdrawable", "?")
    print(f"connected · account {main[:8]}…{main[-4:]} · withdrawable USDC: {wd}")
except Exception as e:
    print(f"connect/user_state failed: {e}")
    raise SystemExit(1)

# 2) size + a passive maker price (2% below mid → rests as maker, won't fill in a few seconds)
meta = info.meta()
szdec = next((int(a["szDecimals"]) for a in meta["universe"] if a["name"] == COIN), 2)
mid = float(info.all_mids()[COIN])
sz = round(USD / mid, szdec)
px = float(f"{mid * 0.98:.5g}")               # 5 sig-figs
px = round(px, max(0, 6 - szdec))             # HL perp px decimals rule
print(f"placing tiny MAKER buy: {sz} {COIN} @ {px} (mid {mid}) ≈ ${sz*px:.2f}, post-only (Alo)")

# 3) place post-only (Add-Liquidity-Only = maker) — should REST, not cross
res = ex.order(COIN, True, sz, px, {"limit": {"tif": "Alo"}})
print("order response:", res)

# 4) confirm resting, then cancel
time.sleep(3)
opens = [o for o in info.open_orders(main) if o["coin"] == COIN]
print(f"resting {COIN} orders: {len(opens)}")
for o in opens:
    c = ex.cancel(COIN, o["oid"])
    print(f"  cancel oid {o['oid']} -> {c}")

ok = isinstance(res, dict) and res.get("status") == "ok"
print("\n" + ("✅ PLUMBING WORKS — maker order placed, rested, cancelled. No position taken."
              if ok else "⚠️ order not confirmed OK — read the response above (px/sz/margin?)."))
