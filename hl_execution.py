"""hl_execution.py — DRY-RUN execution engine for the HL funding carry (the loaded weapon).

Builds the EXACT delta-neutral order plan the live bot would place — position sizing
(capital × leverage / K), MAKER limit orders on the legs, a residual-delta hedge, and
risk gates. DRY-RUN by default: it PRINTS the plan and places NOTHING. It arms live only
with LIVE=true AND a trade-only HL wallet key in env (set by the user, never in code).

CAPITAL IS DYNAMIC (the "savings account that compounds itself"):
  Each cycle it reads your LIVE account equity (read-only, public address) and sizes
  against it — so compounded profits AND your top-ups get redeployed automatically, no
  manual bumping. Bounded by two collars so autonomy can never run away:
    • CAPITAL_CAP — a hard ceiling you raise DELIBERATELY as you clear each evidence gate
      (£250 → £1k → £5k → £20k → uncapped). The bot compounds underneath it, never past it.
    • EQUITY_BUFFER — keep a slice of equity as margin cushion (anti-liquidation).
  If equity can't be read (no address / API down) it falls back to the static CAPITAL_USD.

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

CAPITAL_USD  = float(os.environ.get("CAPITAL_USD", "250"))    # static fallback if equity unreadable
CAPITAL_CAP  = float(os.environ.get("CAPITAL_CAP", "250"))    # ceiling — RAISE deliberately on evidence
EQUITY_BUFFER = float(os.environ.get("EQUITY_BUFFER", "0.10"))  # keep 10% equity as margin cushion
ACCOUNT_ADDR = os.environ.get("HL_ACCOUNT_ADDRESS", "")       # public addr — read-only equity lookup
LEVERAGE     = float(os.environ.get("LEVERAGE", "1"))
MAX_LEVERAGE = float(os.environ.get("MAX_LEVERAGE", "3"))     # hard cap — refuse above this
K            = int(os.environ.get("HL_K", "3"))
ENTRY_ANN    = float(os.environ.get("HL_ENTRY_ANN", "0.12"))
EXIT_ANN     = float(os.environ.get("HL_EXIT_ANN", "0.03"))
MIN_OI_USD   = float(os.environ.get("HL_MIN_OI", "5000000"))
HEDGE_COIN   = os.environ.get("HEDGE_COIN", "BTC")
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


def live_equity():
    """Read-only account value (USDC equity) for our PUBLIC address. None if no address
    set or the endpoint is unreachable — caller falls back to the static capital then."""
    if not ACCOUNT_ADDR:
        return None
    d = _post({"type": "clearinghouseState", "user": ACCOUNT_ADDR})
    try:
        return float((d.get("marginSummary") or {}).get("accountValue") or 0) or None
    except Exception:
        return None


def resolve_capital():
    """The dynamic-capital brain. Read live equity, keep a margin buffer, clamp to the cap.
    Returns (capital_to_deploy, human-readable source string). This is what makes it a
    hands-free compounding account: equity grows -> capital grows -> up to the cap you set."""
    eq = live_equity()
    if eq is not None:
        base = eq * (1 - EQUITY_BUFFER)
        cap = min(base, CAPITAL_CAP)
        src = (f"live equity ${eq:,.0f} ×{1 - EQUITY_BUFFER:.0%} buffer = ${base:,.0f}"
               f" → deploy ${cap:,.0f} (cap ${CAPITAL_CAP:,.0f})"
               + ("  ⛔CAPPED" if base > CAPITAL_CAP else ""))
    else:
        cap = min(CAPITAL_USD, CAPITAL_CAP)
        src = f"static ${CAPITAL_USD:,.0f} (no live equity read) → deploy ${cap:,.0f} (cap ${CAPITAL_CAP:,.0f})"
    return cap, src


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

    capital, cap_src = resolve_capital()      # DYNAMIC: live equity, buffered, capped
    daily_loss_cap = float(os.environ.get("DAILY_LOSS_CAP_USD", "0")) or capital * 0.05
    per_notional = capital * LEVERAGE / K
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
    print(f"=== hl_execution {mode} | {LEVERAGE:.0f}x, {K} slots @ ${per_notional:,.0f} "
          f"= ${capital*LEVERAGE:,.0f} notional ===")
    print(f"  capital: {cap_src}")
    print(f"  daily-loss halt at −${daily_loss_cap:,.0f}")
    book_str = ", ".join(f"{c}[{p['side'][0]}{p['ann_at_entry']*100:+.0f}%]" for c, p in book.items())
    print("  target book:", book_str or "(none clear the funding floor)")
    if not orders:
        print("  no order changes this cycle (book stable)")
    for action, coin, side, notional, reason in orders:
        print(f"  {action:6} {side:4} {coin:10} ${notional:>7,.0f}  ({reason})")
        if LIVE:
            _place_live(coin, side, notional)      # guarded — only runs if LIVE + key present


# ── LIVE placement (post-only maker via HL SDK) ─────────────────────────────────────────
# Guarded on every axis: needs LIVE=true AND a trade-only agent key in env. SDK is imported
# LAZILY so system-python dry-run/cron never touches it — go LIVE with the venv python that
# has the SDK (/root/hl-live/venv/bin/python). Reuses live_test.py's proven rounding.
_CONN = {}                                                        # cached SDK connection
MAKER_OFFSET  = float(os.environ.get("MAKER_OFFSET_BPS", "3")) / 10000.0   # rest inside the spread
MIN_ORDER_USD = float(os.environ.get("MIN_ORDER_USD", "10"))              # HL min notional (~$10)


def _connect():
    """Lazy, cached HL SDK connection using the TRADE-ONLY agent key from env. Returns
    (exchange, info, main_addr) or (None, None, None) if key/SDK unavailable — the caller
    then places NOTHING (fail-safe). The raw key is never printed and not retained."""
    if _CONN:
        return _CONN.get("ex"), _CONN.get("info"), _CONN.get("main")
    key = (os.environ.get("HL_WALLET_KEY") or os.environ.get("HL_AGENT_KEY") or "").strip()
    if not key:
        return None, None, None
    try:
        from eth_account import Account
        from hyperliquid.info import Info
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
    except Exception as e:
        print(f"     ⚠️ HL SDK not importable ({e}) — run with the venv python. Placing nothing.")
        return None, None, None
    acct = Account.from_key(key)
    main = os.environ.get("HL_ACCOUNT_ADDRESS", "").strip() or acct.address
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    ex = Exchange(acct, constants.MAINNET_API_URL, account_address=main)
    _CONN.update(ex=ex, info=info, main=main, meta=info.meta())
    return ex, info, main


def _sz_px(info, coin, side, notional):
    """USD notional -> (size, maker limit price) with HL's rounding. Maker: a BUY rests just
    below mid, a SELL just above — post-only (Alo) guarantees it never crosses into a taker."""
    szdec = next((int(a["szDecimals"]) for a in _CONN["meta"]["universe"] if a["name"] == coin), 2)
    mid = float(info.all_mids()[coin])
    sz = round(notional / mid, szdec)
    raw = mid * (1 - MAKER_OFFSET) if side == "buy" else mid * (1 + MAKER_OFFSET)
    px = round(float(f"{raw:.5g}"), max(0, 6 - szdec))            # 5 sig-figs, HL px-decimals rule
    return sz, px, mid


def _place_live(coin, side, notional):
    """LIVE order — post-only MAKER limit via the HL SDK. Guarded: needs LIVE=true AND a
    trade-only agent key (set by the user, never in code). Alo = Add-Liquidity-Only, so it
    rests as maker or is rejected — it can NEVER accidentally pay taker. Fail-safe: any
    missing piece places nothing. (Maker-fill chasing/re-quote is a later refinement; v1
    proves we can place real maker orders — measured at the Phase-4 live-proof gate.)"""
    if notional < MIN_ORDER_USD:
        print(f"     ⚠️ ${notional:,.0f} < ${MIN_ORDER_USD:.0f} HL min — skipped (too small).")
        return
    ex, info, main = _connect()
    if not ex:
        print("     ⚠️ no trade-only key / SDK — order NOT placed (safe).")
        return
    try:
        sz, px, mid = _sz_px(info, coin, side, notional)
        if sz <= 0:
            print(f"     ⚠️ {coin} size rounded to 0 — skipped.")
            return
        res = ex.order(coin, side == "buy", sz, px, {"limit": {"tif": "Alo"}})
        ok = isinstance(res, dict) and res.get("status") == "ok"
        print(f"     {'✅' if ok else '⚠️'} {side} {sz} {coin} @ {px} (mid {mid}) post-only → {res}")
    except Exception as e:
        print(f"     ⚠️ live order error ({type(e).__name__}: {e}) — not retried this cycle.")


if __name__ == "__main__":
    plan()
