"""Funding-regime monitor.

The backtest showed delta-neutral funding harvest is REGIME-GATED: it's ~0% in the
current compressed regime, but prints when funding runs hot (15-30%+ APY, like the
2024 bull/ETF stretches). So instead of running a dead strategy, this watches live
funding across venues and ALERTS when the regime turns favourable — then you deploy
the harvester manually.

Watches, per liquid coin:
  * single-venue funding APY on Binance / Bybit / Hyperliquid (collect by shorting the
    high-positive-funding perp, or longing a deeply-negative one)
  * cross-venue spread APY = max(venue) - min(venue)  (long low-funding venue / short
    high-funding venue on the same asset -> price- and venue-neutral spread capture)

Alerts when single-venue |APY| >= HOT_SINGLE or cross-venue spread >= HOT_SPREAD.

Run once (cron-friendly):   python3 monitor.py
Loop every 30 min:          python3 monitor.py --loop 30
Telegram alerts (optional): export FUNDING_TG_TOKEN=... FUNDING_TG_CHAT=...
"""
from __future__ import annotations

import csv
import json as _json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_CSV = os.environ.get("HISTORY_CSV", os.path.join(HERE, "regime_history.csv"))


def _http(url: str, *, params: dict | None = None, body: dict | None = None, timeout: int = 15):
    """Stdlib GET/POST returning parsed JSON. Zero deps so it runs on a bare VPS."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = _json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": "funding-monitor/0.1",
                 **({"Content-Type": "application/json"} if data else {})},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read().decode())

# Liquid, tradable universe (illiquid alt funding is untradeable, so excluded).
COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC",
    "TRX", "DOT", "NEAR", "SUI", "APT", "ARB", "OP", "INJ", "TIA", "SEI",
    "WLD", "AAVE", "UNI", "ATOM", "FIL", " ETC".strip(), "HBAR", "RENDER",
    "FTM", "PEPE", "WIF", "ENA", "ORDI", "JUP", "PYTH",
]
HOT_SINGLE = float(os.environ.get("HOT_SINGLE_APY", 15.0))   # % APY
HOT_SPREAD = float(os.environ.get("HOT_SPREAD_APY", 10.0))   # % APY
BINS_8H = 365 * 3     # 8h funding intervals / year
BINS_1H = 365 * 24    # 1h (Hyperliquid) intervals / year


def _num(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def binance() -> dict[str, float]:
    """coin -> annualised funding APY (%). Binance USD-M, 8h assumed."""
    out = {}
    for row in _http("https://fapi.binance.com/fapi/v1/premiumIndex"):
        s = row.get("symbol", "")
        if s.endswith("USDT"):
            fr = _num(row.get("lastFundingRate"))
            if fr is not None:
                out[s[:-4]] = fr * BINS_8H * 100
    return out


def bybit() -> dict[str, float]:
    data = _http("https://api.bybit.com/v5/market/tickers", params={"category": "linear"})
    out = {}
    for row in data.get("result", {}).get("list", []):
        s = row.get("symbol", "")
        if s.endswith("USDT"):
            fr = _num(row.get("fundingRate"))
            if fr is not None:
                out[s[:-4]] = fr * BINS_8H * 100
    return out


def hyperliquid() -> dict[str, float]:
    """coin -> APY (%). Hyperliquid funding is HOURLY."""
    meta, ctxs = _http("https://api.hyperliquid.xyz/info", body={"type": "metaAndAssetCtxs"})
    out = {}
    for u, ctx in zip(meta["universe"], ctxs):
        fr = _num(ctx.get("funding"))
        if fr is not None:
            out[u["name"]] = fr * BINS_1H * 100
    return out


def snapshot() -> list[dict]:
    venues = {}
    for name, fn in (("binance", binance), ("bybit", bybit), ("hyperliquid", hyperliquid)):
        try:
            venues[name] = fn()
        except Exception as e:  # noqa: BLE001
            print(f"  ! {name} fetch failed: {e}")
            venues[name] = {}
    rows = []
    for coin in COINS:
        vals = {v: venues[v][coin] for v in venues if coin in venues[v]}
        if not vals:
            continue
        best_single = max(vals.values(), key=abs)
        spread = (max(vals.values()) - min(vals.values())) if len(vals) >= 2 else 0.0
        rows.append({"coin": coin, "vals": vals, "single": best_single, "spread": spread})
    rows.sort(key=lambda r: max(abs(r["single"]), r["spread"]), reverse=True)
    return rows


def log_history(rows: list[dict]) -> None:
    """Append one structured row per coin per snapshot, building a queryable
    regime dataset over time (how often/where/how long funding runs hot)."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = not os.path.exists(HISTORY_CSV)
    with open(HISTORY_CSV, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "coin", "binance", "bybit", "hyperliquid",
                        "best_single", "spread", "hot"])
        for r in rows:
            v = r["vals"]
            hot = int(abs(r["single"]) >= HOT_SINGLE or r["spread"] >= HOT_SPREAD)
            w.writerow([
                ts, r["coin"],
                round(v["binance"], 2) if "binance" in v else "",
                round(v["bybit"], 2) if "bybit" in v else "",
                round(v["hyperliquid"], 2) if "hyperliquid" in v else "",
                round(r["single"], 2), round(r["spread"], 2), hot,
            ])


def notify(msg: str) -> None:
    token, chat = os.environ.get("FUNDING_TG_TOKEN"), os.environ.get("FUNDING_TG_CHAT")
    if token and chat:
        try:
            _http(f"https://api.telegram.org/bot{token}/sendMessage",
                  body={"chat_id": chat, "text": msg}, timeout=10)
        except Exception as e:  # noqa: BLE001
            print(f"  ! telegram failed: {e}")
    # macOS desktop notification fallback
    if sys.platform == "darwin":
        os.system(f"""osascript -e 'display notification "{msg[:200]}" with title "Funding HOT"' 2>/dev/null""")


def report(rows: list[dict]) -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== Funding regime @ {now}  (hot: single>={HOT_SINGLE}% | spread>={HOT_SPREAD}% APY) ===")
    print(f"{'coin':>7} {'binance':>9} {'bybit':>9} {'hyperliq':>9} {'spread':>8}  flag")
    hot = []
    for r in rows[:20]:
        v = r["vals"]
        b = f"{v.get('binance'):+.1f}" if 'binance' in v else "   -"
        y = f"{v.get('bybit'):+.1f}" if 'bybit' in v else "   -"
        h = f"{v.get('hyperliquid'):+.1f}" if 'hyperliquid' in v else "   -"
        is_hot = abs(r["single"]) >= HOT_SINGLE or r["spread"] >= HOT_SPREAD
        flag = "🔥" if is_hot else ""
        if is_hot:
            hot.append(r)
        print(f"{r['coin']:>7} {b:>9} {y:>9} {h:>9} {r['spread']:>7.1f}%  {flag}")
    if hot:
        lines = [f"{r['coin']}: single {r['single']:+.0f}% / spread {r['spread']:.0f}% APY" for r in hot[:8]]
        msg = "🔥 FUNDING HOT — deploy harvester:\n" + "\n".join(lines)
        print("\n" + msg)
        notify(msg)
    else:
        print("\n  regime COLD — nothing above threshold. Harvester stays idle (correct).")


def main() -> None:
    loop_min = 0
    if "--loop" in sys.argv:
        loop_min = int(sys.argv[sys.argv.index("--loop") + 1])
    while True:
        try:
            rows = snapshot()
            report(rows)
            log_history(rows)
        except Exception as e:  # noqa: BLE001
            print(f"  ! snapshot failed: {e}")
        if loop_min <= 0:
            break
        time.sleep(loop_min * 60)


if __name__ == "__main__":
    main()
