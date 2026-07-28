"""dashboard.py — unified PrimeHaul PAPER-trading dashboard (the new stack, one screen).

Pure stdlib. Serves http://<host>:3040. Two decks:
  🟢 FUNDING MACHINE  — the positive-sum core (HL flat, HL concentrated, Drift). Market-
     neutral funding carry. net = cum_funding − cum_cost, annualised. This is the real edge.
  🎯 SIGNAL BOTS       — paper experiments proving forward BEFORE any real money: Overdose
     caller copy (t=0 vs t+10 A/B) + wallet-cluster (≥3 vetted winners in one coin). Each
     runs a +40% take-profit on a compounding £1k paper bankroll.

Everything here is PAPER. No keys, no orders, no money. Auto-refresh 60s.
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 3040
FH = "/root/funding-harvester"
RR = "/root/robinhood-runner"
HRS_YR = 24 * 365
START_BANK = 1000.0


def _load(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d if d is not None else {}


def _fund(name, sub, path):
    """Card data for a funding book: net%, APY, days, current short book."""
    st = _load(path)
    if not st:
        return {"name": name, "sub": sub, "dead": True}
    net = st.get("cum_funding", 0) - st.get("cum_cost", 0)
    days = (time.time() - st.get("start_ts", time.time())) / 86400
    apy = (net / days * 365 * 100) if days > 0.02 else 0
    book = st.get("book", {})
    legs = [f"{c} {v.get('side','')[0].upper()}{abs(v.get('ann_at_entry',0))*100:.0f}%"
            for c, v in book.items()]
    return {"name": name, "sub": sub, "net": net * 100, "apy": apy, "days": days,
            "legs": legs, "n": len(book), "dead": False}


def _bot(name, sub, path, start=START_BANK):
    """Card data for a signal bot: bankroll, hit rate, avg/call, open positions."""
    st = _load(path)
    pos = (st or {}).get("positions", {})
    pend = len((st or {}).get("pending", {}))
    closed = [p for p in pos.values() if str(p.get("status", "")).startswith("closed")]
    opens = [p for p in pos.values() if p.get("status") == "open"]
    wins = [p for p in closed if p.get("ret_pct", 0) > 0]
    bank = start + sum(p.get("pnl_gbp", 0) for p in closed)
    avg = sum(p.get("ret_pct", 0) for p in closed) / len(closed) if closed else 0
    hit = 100 * len(wins) / len(closed) if closed else 0
    op = []
    for p in sorted(opens, key=lambda x: -(x.get("peak", 0) / (x.get("entry", 1) or 1))):
        entry = p.get("entry", 1) or 1
        op.append({"sym": p.get("symbol", "?"),
                   "peak": (p.get("peak", entry) / entry - 1) * 100,
                   "gated": p.get("gated", False),
                   "np": p.get("n_proven", 0)})
    return {"name": name, "sub": sub, "bank": bank, "ret": (bank / start - 1) * 100,
            "closed": len(closed), "open": len(opens), "pending": pend,
            "hit": hit, "avg": avg, "opens": op, "seeded": st.get("seed_max")}


def _sign(v):
    return "pos" if v >= 0 else "neg"


def fund_card(d):
    if d.get("dead"):
        return f'<div class="card dead"><div class="cn">{d["name"]}</div><div class="muted">no data yet</div></div>'
    legs = "".join(f'<span class="leg">{l}</span>' for l in d["legs"]) or '<span class="muted">flat — nothing clears the funding floor</span>'
    return f'''<div class="card">
      <div class="cn">{d["name"]} <span class="sub">{d["sub"]}</span></div>
      <div class="big {_sign(d["net"])}">{d["net"]:+.3f}%</div>
      <div class="row"><span>~{d["apy"]:+.0f}% APY est</span><span class="muted">{d["days"]:.1f}d · {d["n"]} legs</span></div>
      <div class="legs">{legs}</div>
    </div>'''


def bot_card(d):
    op = "".join(
        f'<div class="pos"><span class="sym">{o["sym"]}</span>'
        f'<span class="{_sign(o["peak"])}">peak {o["peak"]:+.0f}%</span>'
        + (f'<span class="tag gate">gated</span>' if o["gated"] else "")
        + (f'<span class="tag win">{o["np"]}🐋</span>' if o["np"] else "")
        + '</div>'
        for o in d["opens"]) or '<div class="muted">no open positions</div>'
    armed = f'armed #{d["seeded"]}' if d.get("seeded") else "warming up"
    return f'''<div class="card">
      <div class="cn">{d["name"]} <span class="sub">{d["sub"]}</span></div>
      <div class="big {_sign(d["ret"])}">£{d["bank"]:.0f} <span class="pct {_sign(d["ret"])}">{d["ret"]:+.1f}%</span></div>
      <div class="row"><span>hit {d["hit"]:.0f}% · avg {d["avg"]:+.1f}%/call</span>
        <span class="muted">{d["closed"]}✓ {d["open"]}◷ {d["pending"]}⏳</span></div>
      <div class="poslist">{op}</div>
      <div class="muted sm">{armed} · +40% TP · £100 clips · paper</div>
    </div>'''


def page():
    funds = [
        _fund("HL Flat", "equal-weight carry", f"{FH}/hl_paper_state.json"),
        _fund("HL Concentrated", "α=1 fat-funding tilt", f"{FH}/hl_paper_conc_state.json"),
        _fund("Drift", "Solana on-chain carry", f"{FH}/drift_paper_state.json"),
        _fund("Lighter", "zk-rollup carry · incl RWA perps", f"{FH}/lighter_paper_state.json"),
        _fund("Aster", "Binance-style perp DEX carry", f"{FH}/aster_paper_state.json"),
    ]
    bots = [
        _bot("Overdose t=0", "caller copy · buy now", f"{RR}/overdose_state.json"),
        _bot("Overdose t+10", "caller copy · wait 10m", f"{RR}/overdose_d10_state.json"),
        _bot("Wallet-Cluster", "≥3 vetted winners", f"{RR}/cluster_state.json"),
    ]
    tot_fund = sum(f.get("net", 0) for f in funds if not f.get("dead"))
    tot_bot = sum(b["bank"] - START_BANK for b in bots)
    fc = "".join(fund_card(f) for f in funds)
    bc = "".join(bot_card(b) for b in bots)
    return f'''<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<meta http-equiv=refresh content=60><title>PrimeHaul · Paper Desk</title>
<style>
:root{{--bg:#0b0e14;--card:#151a23;--line:#232a36;--tx:#e6edf3;--mut:#7d8896;--pos:#3fb950;--neg:#f85149;--acc:#58a6ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font:14px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:22px 16px 60px}}
.hd{{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:4px}}
h1{{font-size:20px;margin:0;letter-spacing:.3px}}
.paper{{font-size:11px;color:#d29922;border:1px solid #d2992244;background:#d299220f;padding:3px 9px;border-radius:20px;font-weight:600}}
.sect{{margin:26px 0 12px;font-size:12px;letter-spacing:1.5px;color:var(--mut);text-transform:uppercase;display:flex;align-items:center;gap:8px}}
.sect .t{{flex:1}}.sect .tot{{color:var(--tx);font-weight:600;letter-spacing:0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:15px 16px}}
.card.dead{{opacity:.5}}
.cn{{font-weight:600;font-size:15px;margin-bottom:8px}}.sub{{font-weight:400;font-size:12px;color:var(--mut)}}
.big{{font-size:26px;font-weight:700;letter-spacing:-.5px}}
.big .pct{{font-size:15px;font-weight:600;margin-left:6px}}
.pos{{display:flex;align-items:center;gap:8px;padding:4px 0;border-top:1px solid var(--line);font-size:13px}}
.pos:first-child{{border-top:0}}.sym{{flex:1;font-weight:600}}
.row{{display:flex;justify-content:space-between;margin:7px 0;font-size:12.5px}}
.pos,.neg,.pct.pos{{}}.pos.pos{{}}
.pos-{{}}.pos > .pos{{}}
.poslist{{margin-top:9px}}.legs{{margin-top:9px;display:flex;flex-wrap:wrap;gap:5px}}
.leg{{font-size:11px;background:#1f6feb22;color:#79c0ff;padding:2px 7px;border-radius:5px}}
.tag{{font-size:10px;padding:1px 6px;border-radius:5px}}.tag.gate{{background:#f8514922;color:#ff7b72}}.tag.win{{background:#3fb95022;color:#56d364}}
.muted{{color:var(--mut)}}.sm{{font-size:11px;margin-top:9px}}
span.pos,.big.pos{{color:var(--pos)}}span.neg,.big.neg,.pct.neg{{color:var(--neg)}}
.pct.pos{{color:var(--pos)}}
.foot{{margin-top:30px;color:var(--mut);font-size:11.5px;line-height:1.7}}
</style></head><body><div class=wrap>
<div class=hd><h1>🦅 PrimeHaul · Paper Desk</h1><span class=paper>PAPER ONLY · no keys · no money</span></div>
<div class=muted style="font-size:12px">forward-proving before a penny moves · auto-refresh 60s</div>

<div class=sect><span class=t>🟢 Funding Machine — positive-sum core</span><span class=tot>Σ net {tot_fund:+.3f}%</span></div>
<div class=grid>{fc}</div>

<div class=sect><span class=t>🎯 Signal Bots — proving forward (+40% TP)</span><span class="tot {_sign(tot_bot)}">Σ £{tot_bot:+.0f}</span></div>
<div class=grid>{bc}</div>

<div class=foot>
🟢 <b>Funding</b> = market-neutral carry, the validated edge (OOS-held). 🎯 <b>Signal bots</b> = unproven, paper-only, counting rugs from t=0 (no survivorship). Overdose t=0 vs t+10 tests whether waiting beats sniping. Wallet-cluster fires only when ≥3 vetted winners hold the same fresh coin. <b>Nothing gets funded until a scoreboard proves out.</b>
<br><br>📋 <b>Funding Bot</b> — full continuation/handoff prompt saved to <code>~/Desktop/FUNDING BOT.md</code> · repos private (jaybo1431/funding-harvester + robinhood-runner) · roadmap in <code>EXPANSION_ROADMAP.md</code>
</div>
</div></body></html>'''


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body = page().encode()
        except Exception as e:  # never let the desk go dark on one bad file
            body = f"<pre>dashboard error: {e}</pre>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"PrimeHaul paper desk on :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
