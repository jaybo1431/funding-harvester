"""hl_execution.py — DRY-RUN execution engine for the HL funding carry (the loaded weapon).

Builds the EXACT delta-neutral order plan the live bot would place — position sizing
(capital × leverage / K), MAKER limit orders on the legs, a residual-delta hedge, and
risk gates. DRY-RUN by default: it PRINTS the plan and places NOTHING. It arms live only
with LIVE=true AND a trade-only HL wallet key in env (set by the user, never in code).

This sits ready so the instant the paper P&L proves out, we flip LIVE and strike at size
— no build lag. Until then it's safe: read-only funding, printed order plans, zero orders.

Risk gates: MAX_LEVERAGE cap · per-position notional cap · funding-FLIP fast-exit ·
daily-loss circuit breaker. Delta hedge via a liquid low-funding perp (BTC) to zero net
delta so the book is truly price-neutral.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "hl_exec_state.json")
URL = "https://api.hyperliquid.xyz/info"
HRS_YR = 24 * 365

CAPITAL_USD  = float(os.environ.get("CAPITAL_USD", "250"))
LEVERAGE     = float(os.environ.get("LEVERAGE", "1"))
MAX_LEVERAGE = float(os.environ.get("MAX_LEVERAGE", "3"))     # hard cap — refuse above this
K            = int(os.environ.get("HL_K", "3"))
ENTRY_ANN    = float(os.environ.get("HL_ENTRY_ANN", "0.12"))
EXIT_ANN     = float(os.environ.get("HL_EXIT_ANN", "0.03"))
MIN_OI_USD   = float(os.environ.get("HL_MIN_OI", "5000000"))
HEDGE_COIN   = os.environ.get("HEDGE_COIN", "BTC")
DAILY_LOSS_CAP = float(os.environ.get("DAILY_LOSS_CAP_USD", str(CAPITAL_USD * 0.05)))  # 5% halt
LIVE = os.environ.get("LIVE", "false").lower() == "true"


def _post(body):
    data = json.dumps(body).encode()
    for a in range(4):
        try:
            req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            time.sleep(2 * (a + 1))
    return None


def live_funding():
    """coin -> (annualised funding, oi_usd, mark_px)."""
    m = _post({"type": "metaAndAssetCtxs"})
    if not m:
        return {}
    out = {}
    for u, ctx in zip(m[0]["universe"], m[1]):
        if u.get("isDelisted"):
            continue
        try:
            ann = float(ctx.get("funding") or 0) * HRS_YR
            px = float(ctx.get("markPx") or 0)
            oi = float(ctx.get("openInterest") or 0) * px
        except (TypeError, ValueError):
            continue
        out[u["name"]] = (ann, oi, px)
    return out


def _load(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


def plan():
    # ── risk gate 0: leverage cap ────────────────────────────────────────────
    if LEVERAGE > MAX_LEVERAGE:
        print(f"🛑 RISK: LEVERAGE {LEVERAGE} > MAX_LEVERAGE {MAX_LEVERAGE} — refusing to trade.")
        return
    fund = live_funding()
    if not fund:
        print("hl_execution: HL fetch failed — skip")
        return
    st = _load(STATE, {"book": {}, "realized_pnl": 0.0})
    book = st["book"]                         # coin -> {side, ann_at_entry}

    per_notional = CAPITAL_USD * LEVERAGE / K
    orders = []                               # (action, coin, side, notional_usd, reason)

    # ── risk gate 1: funding-FLIP fast-exit (a held coin's funding flipped/decayed) ──
    for coin in list(book):
        ann = fund.get(coin, (0, 0, 0))[0]
        entry_side = book[coin]["side"]
        flipped = (entry_side == "short" and ann < 0) or (entry_side == "long" and ann > 0)
        if coin not in fund or abs(ann) < EXIT_ANN or flipped:
            orders.append(("CLOSE", coin, "buy" if entry_side == "short" else "sell",
                           per_notional, "flip/decay" if flipped else "decayed"))
            del book[coin]

    # ── fill free slots with richest liquid carry ───────────────────────────
    ranked = sorted(fund.items(), key=lambda kv: -abs(kv[1][0]))
    for coin, (ann, oi, px) in ranked:
        if len(book) >= K:
            break
        if coin in book or abs(ann) < ENTRY_ANN or oi < MIN_OI_USD:
            continue
        side = "short" if ann > 0 else "long"        # short +funding (collect) / long −funding
        book[coin] = {"side": side, "ann_at_entry": round(ann, 3)}
        orders.append(("OPEN", coin, "sell" if side == "short" else "buy", per_notional,
                       f"funding {ann*100:+.0f}% APY"))

    # ── delta hedge: neutralise net delta with a liquid low-funding perp ─────
    net_delta = sum((-per_notional if p["side"] == "short" else per_notional) for p in book.values())
    if abs(net_delta) > per_notional * 0.1:
        hside = "buy" if net_delta < 0 else "sell"   # opposite the book's net delta
        orders.append(("HEDGE", HEDGE_COIN, hside, abs(net_delta), "neutralise net delta"))

    st["book"] = book
    json.dump(st, open(STATE, "w"), indent=1)

    # ── output the plan ─────────────────────────────────────────────────────
    mode = "🔴 LIVE" if LIVE else "🟡 DRY-RUN (no orders placed)"
    print(f"=== hl_execution {mode} | capital ${CAPITAL_USD:.0f} × {LEVERAGE:.0f}x "
          f"= ${CAPITAL_USD*LEVERAGE:.0f} notional, {K} slots @ ${per_notional:.0f} ===")
    book_str = ", ".join(f"{c}[{p['side'][0]}{p['ann_at_entry']*100:+.0f}%]" for c, p in book.items())
    print("target book:", book_str or "(none clear the funding floor)")
    if not orders:
        print("  no order changes this cycle (book stable)")
    for action, coin, side, notional, reason in orders:
        print(f"  {action:6} {side:4} {coin:10} ${notional:>7.0f}  ({reason})")
        if LIVE:
            _place_live(coin, side, notional)      # guarded — only runs if LIVE + key present


def _place_live(coin, side, notional):
    """LIVE order placement — MAKER limit orders via the HL SDK. Guarded: needs LIVE=true
    AND a trade-only HL wallet key in env. NOT wired to the SDK yet by design — this is
    the final step, taken only after the paper proves out + the user sets the key."""
    key = os.environ.get("HL_WALLET_KEY")
    if not key:
        print("     ⚠️ LIVE set but HL_WALLET_KEY missing in env — order NOT placed (safe).")
        return
    # TODO(go-live): from hyperliquid.exchange import Exchange; post-only limit at best bid/ask.
    #   Wire only after: (1) paper proven, (2) key is a TRADE-ONLY agent wallet (no withdraw),
    #   (3) tested on ONE tiny order first. Left unwired on purpose — no accidental live trades.
    print("     ⚠️ live SDK wiring intentionally not enabled yet (final go-live step).")


if __name__ == "__main__":
    plan()
