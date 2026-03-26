"""
Larsen Ventures — Betfair Prediction Markets Dashboard
Standalone: bankroll, P&L, open bets, calibration, history.
"""
import json, time
from datetime import datetime
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Prediction Markets — Larsen Ventures", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

BASE           = Path(__file__).parent.parent
BETFAIR_LEDGER = BASE / "betfair" / "paper_ledger.json"

st.markdown("""
<style>
  .block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; }
  div[data-testid="metric-container"] { background:#1a1a2e; border-radius:8px; padding:10px; border:1px solid #16213e; overflow:hidden; }
  div[data-testid="metric-container"] > div { overflow:hidden; }
  div[data-testid="stMetricValue"] { font-size:1.1rem !important; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  div[data-testid="stMetricLabel"] { font-size:0.75rem !important; }
  h2 { font-size:1.05rem !important; border-bottom:1px solid #ffffff22; padding-bottom:3px; margin-top:1rem !important; }
  .pill { display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:bold; margin:2px; }
  .pill-bull { background:#00d26a22; color:#00d26a; border:1px solid #00d26a55; }
  .pill-bear { background:#ff4b4b22; color:#ff4b4b; border:1px solid #ff4b4b55; }
  .pill-neut { background:#ffffff11; color:#aaa; border:1px solid #ffffff22; }
</style>""", unsafe_allow_html=True)

col_t, col_ts = st.columns([5, 2])
with col_t:
    st.markdown("# 🎯 Larsen Ventures — Prediction Markets")
with col_ts:
    st.markdown(f"<p style='color:#666;font-size:12px;margin-top:22px'>Betfair Exchange · Paper Mode · {datetime.now().strftime('%d %b %Y %H:%M')}</p>", unsafe_allow_html=True)

st.markdown("---")

def load_ledger():
    if BETFAIR_LEDGER.exists():
        try:
            with open(BETFAIR_LEDGER) as f: return json.load(f)
        except Exception: pass
    return None

ledger = load_ledger()
if ledger is None:
    st.info("Prediction engine is live but no bets placed yet. The scanner runs every 4 hours and will record opportunities here automatically.")
    ledger = {"bankroll_gbp": 250.0, "bankroll_aud": 500.0, "bets": [],
              "stats": {"total_bets":0,"wins":0,"losses":0,"total_staked":0,"total_profit":0,"roi_pct":0},
              "started": datetime.now().isoformat()}

bets       = ledger.get("bets", [])
stats      = ledger.get("stats", {})
open_bets  = [b for b in bets if b.get("status") == "OPEN"]
settled    = [b for b in bets if b.get("status") == "SETTLED"]
wins       = [b for b in settled if b.get("result") == "WIN"]
bankroll   = ledger.get("bankroll_gbp", 250.0)
start_br   = 250.0
total_pnl  = bankroll - start_br
roi_pct    = (total_pnl / stats.get("total_staked", 1)) * 100 if stats.get("total_staked", 0) > 0 else 0
win_rate   = (len(wins) / len(settled) * 100) if settled else 0
avg_edge   = (sum(b.get("edge", 0) for b in bets) / len(bets) * 100) if bets else 0
avg_odds   = (sum(b.get("back_price", 0) for b in bets) / len(bets)) if bets else 0

# ROW 1: Bankroll
st.markdown("## Bankroll & P&L")
b1, b2, b3, b4, b5 = st.columns(5)
b1.metric("Bankroll",  f"£{bankroll:,.2f}", delta=f"£{total_pnl:+.2f}" if bets else None)
b2.metric("Starting",  f"£{start_br:,.2f}")
b3.metric("Total P&L", f"£{total_pnl:+.2f}")
b4.metric("ROI",       f"{roi_pct:.1f}%" if bets else "—")
b5.metric("Paper Mode","✅ Active")
if bets:
    br_pct = bankroll / start_br
    st.progress(min(br_pct, 1.5) / 1.5, text=f"£{bankroll:.2f} / £{start_br:.2f}  ({br_pct*100:.1f}% of starting)")

st.markdown("---")

# ROW 2: Performance
st.markdown("## Performance")
p1, p2, p3, p4, p5, p6 = st.columns(6)
p1.metric("Total Bets", str(stats.get("total_bets", 0)))
p2.metric("Open",       str(len(open_bets)))
p3.metric("Settled",    str(len(settled)))
p4.metric("Win Rate",   f"{win_rate:.0f}%" if settled else "—")
p5.metric("Avg Edge",   f"{avg_edge:.1f}%" if bets else "—")
p6.metric("Avg Odds",   f"{avg_odds:.2f}" if bets else "—")

if settled:
    st.markdown("**Go / No-Go Criteria** (4-week paper trial)")
    g1, g2, g3 = st.columns(3)
    with g1:
        roi_ok = roi_pct > 0
        st.markdown(f"{'✅' if roi_ok else '🔴'} **Positive ROI**  \n`{roi_pct:.1f}%` (target: > 0%)")
    with g2:
        wr_ok = win_rate >= 52
        st.markdown(f"{'✅' if wr_ok else '🔴'} **Win Rate**  \n`{win_rate:.1f}%` (target: ≥ 52%)")
    with g3:
        min_bets = len(settled) >= 20
        st.markdown(f"{'✅' if min_bets else '⏳'} **Sample Size**  \n`{len(settled)} settled` (target: ≥ 20)")

st.markdown("---")

# ROW 3: Open Bets
st.markdown(f"## Open Bets  `{len(open_bets)}`")
if open_bets:
    import pandas as pd
    rows = []
    for b in open_bets:
        agent_p  = b.get("agent_prob", 0) or 0
        mkt_p    = b.get("market_prob", 0) or 0
        edge_pct = (b.get("edge", 0) or 0) * 100
        rows.append({"Event": b.get("event",""), "Market": b.get("market",""),
            "Selection": b.get("selection",""), "Odds": f"{b.get('back_price',0):.2f}",
            "Stake": f"£{b.get('stake_gbp',0):.2f}", "To Win": f"£{b.get('potential_profit',0):.2f}",
            "Our Prob": f"{agent_p*100:.0f}%", "Mkt Prob": f"{mkt_p*100:.0f}%",
            "Edge": f"+{edge_pct:.1f}%", "Type": b.get("event_type","")})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown("**Signal Reasoning**")
    for b in open_bets:
        edge_pct = (b.get("edge", 0) or 0) * 100
        with st.expander(f"{b.get('event','')} — {b.get('selection','')} @ {b.get('back_price','')} | edge {edge_pct:.1f}%"):
            c1, c2 = st.columns([1, 3])
            with c1:
                st.metric("Our Prob",  f"{(b.get('agent_prob',0) or 0)*100:.0f}%")
                st.metric("Mkt Prob",  f"{(b.get('market_prob',0) or 0)*100:.0f}%")
                st.metric("Stake",     f"£{b.get('stake_gbp',0):.2f}")
                st.metric("Edge",      f"{edge_pct:.1f}%")
            with c2:
                st.markdown(f"**Reasoning:** {b.get('reasoning','No reasoning captured')}")
else:
    st.info("No open bets. Scanner runs every 4h and places bets when Kelly edge > 3%.")

st.markdown("---")

# ROW 4: Calibration
if settled:
    st.markdown("## Probability Calibration")
    buckets = {}
    for b in settled:
        ap = b.get("agent_prob", 0) or 0
        bucket = round(ap * 10) / 10
        if bucket not in buckets: buckets[bucket] = {"count": 0, "wins": 0}
        buckets[bucket]["count"] += 1
        if b.get("result") == "WIN": buckets[bucket]["wins"] += 1
    if buckets:
        xs, ys, sizes = [], [], []
        for prob, data in sorted(buckets.items()):
            if data["count"] > 0:
                xs.append(prob); ys.append(data["wins"]/data["count"]); sizes.append(data["count"]*15)
        fig_cal = go.Figure()
        fig_cal.add_trace(go.Scatter(x=[0,1], y=[0,1], mode="lines", name="Perfect calibration",
            line=dict(dash="dash", color="#555555")))
        fig_cal.add_trace(go.Scatter(x=xs, y=ys, mode="markers+lines", name="Agent calibration",
            marker=dict(size=sizes, color="#00d26a"), line=dict(color="#00d26a")))
        fig_cal.update_layout(height=300, margin=dict(l=10,r=10,t=20,b=10),
            paper_bgcolor="#0e0e1a", plot_bgcolor="#0e0e1a", font_color="white",
            xaxis_title="Predicted Probability", yaxis_title="Actual Win Rate",
            xaxis=dict(range=[0,1], gridcolor="#1a1a2e"), yaxis=dict(range=[0,1], gridcolor="#1a1a2e"))
        st.plotly_chart(fig_cal, use_container_width=True)
    st.markdown("---")

# ROW 5: Settled History
st.markdown("## Settled History")
if settled:
    import pandas as pd
    rows = []
    for b in reversed(settled[-50:]):
        rows.append({"Date": b.get("timestamp","")[:10], "Event": b.get("event",""),
            "Selection": b.get("selection",""), "Odds": f"{b.get('back_price',0):.2f}",
            "Stake": f"£{b.get('stake_gbp',0):.2f}", "Result": b.get("result",""),
            "P&L": f"£{b.get('profit',0) or 0:+.2f}", "Edge": f"{(b.get('edge',0) or 0)*100:.1f}%"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    # P&L chart
    cumulative, running = [], 0
    for b in settled:
        running += b.get("profit", 0) or 0
        cumulative.append(running)
    fig_pnl = go.Figure()
    fig_pnl.add_trace(go.Scatter(y=cumulative, mode="lines+markers",
        line=dict(color="#00d26a" if running >= 0 else "#ff4b4b", width=2),
        fill="tozeroy", fillcolor="rgba(0,210,106,0.1)" if running >= 0 else "rgba(255,75,75,0.1)"))
    fig_pnl.add_hline(y=0, line_dash="dash", line_color="#555555")
    fig_pnl.update_layout(height=220, margin=dict(l=10,r=10,t=20,b=10),
        paper_bgcolor="#0e0e1a", plot_bgcolor="#0e0e1a", font_color="white",
        yaxis_title="Cumulative P&L (£)", xaxis_title="Bet Number",
        xaxis=dict(gridcolor="#1a1a2e"), yaxis=dict(gridcolor="#1a1a2e"))
    st.plotly_chart(fig_pnl, use_container_width=True)
else:
    st.info("No settled bets yet — open bets settle automatically when events complete.")

st.markdown("---")

# ROW 6: System Health
st.markdown("## System Health")
h1, h2, h3, h4 = st.columns(4)
ledger_age = "⚫ No data"
if BETFAIR_LEDGER.exists():
    age_h = (time.time() - BETFAIR_LEDGER.stat().st_mtime) / 3600
    ledger_age = f"✅ {int(age_h*60)}m ago" if age_h < 1 else f"🟡 {int(age_h)}h ago" if age_h < 24 else f"🔴 {int(age_h/24)}d ago"
bf_log = Path("/tmp/betfair_paper.log")
log_age = "⚫ Not yet run"
if bf_log.exists():
    age_h = (time.time() - bf_log.stat().st_mtime) / 3600
    log_age = f"✅ {int(age_h*60)}m ago" if age_h < 2 else f"🟡 {int(age_h)}h ago"
with h1: st.markdown(f"**Ledger**<br>{ledger_age}", unsafe_allow_html=True)
with h2: st.markdown(f"**Last Scan**<br>{log_age}", unsafe_allow_html=True)
with h3: st.markdown("**Mode**<br>✅ Paper (safe)", unsafe_allow_html=True)
with h4:
    started = ledger.get("started","")[:10] if ledger.get("started") else "—"
    st.markdown(f"**Trial Start**<br>{started}", unsafe_allow_html=True)
if bf_log.exists():
    with st.expander("View scanner log"):
        st.code(bf_log.read_text()[-2000:], language="text")

st.markdown("<p style='color:#333;font-size:11px;text-align:center;margin-top:1rem'>Larsen Ventures · Betfair Prediction Engine · Paper Mode · <a href='https://chappie.larsenfamily.com.au' style='color:#333'>Home</a></p>", unsafe_allow_html=True)




# Manual refresh
st.markdown("---")
col_r1, col_r2, col_r3 = st.columns([3,1,3])
with col_r2:
    if st.button("⟳ Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
from datetime import datetime
st.markdown(f"<p style='color:#333;font-size:11px;text-align:center'>Last loaded: {datetime.now().strftime('%d %b %Y %H:%M:%S')} · Data cached 60s</p>", unsafe_allow_html=True)
