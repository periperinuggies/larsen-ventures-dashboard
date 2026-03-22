"""
Runs locally via cron. Reads latest KB outputs, writes a
condensed kb_summary.json that gets committed to GitHub.
The Streamlit Cloud app reads this file for intelligence signals.
"""
import json, glob, os
from pathlib import Path
from datetime import datetime

KB = Path(__file__).parent.parent / "knowledge_base"

def latest(subdir):
    files = sorted(glob.glob(str(KB / subdir / "*.json")))
    if not files: return {}
    try:
        with open(files[-1]) as f: return json.load(f)
    except: return {}

macro    = latest("macro_data")
sent     = latest("sentiment")
insider  = latest("insider_trades")
contracts= latest("govt_contracts")
sec      = latest("sec_filings")
earnings = latest("earnings_calendar")

summary = {
    "_updated": datetime.now().isoformat(),
    "macro": {
        "regime":   macro.get("regime", "UNKNOWN"),
        "gate":     macro.get("macro_gate", False),
        "spy":      macro.get("spy_price"),
        "sma200":   macro.get("spy_sma200"),
        "vix":      macro.get("vix"),
        "hy_spread":macro.get("hy_spread"),
        "fed":      macro.get("fed_funds_rate"),
        "yc":       macro.get("yield_curve_10y2y"),
    },
    "fear_greed":   sent.get("fear_greed_index", {}),
    "reddit_signals": {k: v.get("signal") for k, v in sent.get("signals", {}).items()
                       if "CONTRARIAN" in v.get("signal","") or "BULLISH" in v.get("signal","") or "BEARISH" in v.get("signal","")},
    "insider_clusters": {k: {"count": v.get("count"), "trend": v.get("trend")}
                         for k, v in insider.get("clusters", {}).items()},
    "large_contracts": {k: {"amount_m": round(v["largest"]["amount"]/1e6,1), "agency": v["largest"]["agency"][:50]}
                        for k, v in contracts.get("large_awards", {}).items() if v.get("largest") and v["largest"].get("agency")},
    "urgent_8k":    [{"ticker": f["ticker"], "items": f.get("form_items",[])} for f in sec.get("urgent", [])],
    "earnings_soon": {k: v for k, v in earnings.get("must_exit", {}).items()},
}

out = Path(__file__).parent / "kb_summary.json"
with open(out, "w") as f:
    json.dump(summary, f, indent=2, default=str)
print(f"kb_summary.json written ({out.stat().st_size} bytes)")

# ── Sync Betfair ledger ───────────────────────────────────────────────────────
betfair_src = Path(__file__).parent.parent / "betfair" / "paper_ledger.json"
betfair_dst = Path(__file__).parent / "betfair_ledger.json"
if betfair_src.exists():
    try:
        with open(betfair_src) as f:
            betfair_data = json.load(f)
        betfair_data["_synced"] = datetime.now().isoformat()
        with open(betfair_dst, "w") as f:
            json.dump(betfair_data, f, indent=2, default=str)
        print(f"betfair_ledger.json synced ({betfair_dst.stat().st_size} bytes)")
    except Exception as e:
        print(f"betfair sync error: {e}")
else:
    print("betfair/paper_ledger.json not found — skipping sync")
