import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Larsen Ventures — Trading Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TRADING_DIR  = Path("/Users/chappie/.openclaw/workspace/trading")
KB_DIR       = TRADING_DIR / "knowledge_base"
FEEDBACK_DIR = TRADING_DIR / "feedback"
sys.path.insert(0, str(TRADING_DIR))

TICKERS = ["NVDA","MSFT","AVGO","CRWD","META","GOOGL",
           "AMD","PANW","AMAT","LRCX","ARM","AMZN",
           "ZS","SNOW","LLY","NVO","KLAC","MDB","S"]

COMPANY_NAMES = {
    "NVDA":"Nvidia","MSFT":"Microsoft","AVGO":"Broadcom","CRWD":"CrowdStrike",
    "META":"Meta","GOOGL":"Alphabet","AMD":"AMD","PANW":"Palo Alto Networks",
    "AMAT":"Applied Materials","LRCX":"Lam Research","ARM":"Arm Holdings",
    "AMZN":"Amazon","ZS":"Zscaler","SNOW":"Snowflake","LLY":"Eli Lilly",
    "NVO":"Novo Nordisk","KLAC":"KLA Corp","MDB":"MongoDB","S":"SentinelOne",
}
TIER_MAP = {
    "NVDA":1,"MSFT":1,"AVGO":1,"CRWD":1,"META":1,"GOOGL":1,
    "AMD":2,"PANW":2,"AMAT":2,"LRCX":2,"ARM":2,"AMZN":2,
    "ZS":3,"SNOW":3,"LLY":3,"NVO":3,"KLAC":3,"MDB":3,"S":3,
}

KB_MODULES = [
    "macro_data","sentiment","insider_trades","options_flow","earnings_calendar",
    "govt_contracts","sec_filings","dart_filings","news_cn","reservoir","seismic",
    "ferc_queue","kepco","reddit_velocity","arxiv_papers","biorxiv_preprints",
    "pypi_stats","github_velocity","dutch_cbs","short_interest","sec_13f",
    "trendforce","etnews","calcalist","lme_metals","cftc_cot","gacc_customs",
    "caixin_news","huggingface_trends","ecb_signals","boj_signals","msia_semi",
    "cpca_ev","specialty_gas","dart_battery","israel_ia","pmda_japan",
    "mfds_approvals","app_store","fed_speeches","eurlex","opec_news",
    "hedge_fund_holdings","congressional_trades",
]

KB_MODULE_URLS = {
    "macro_data": "https://fred.stlouisfed.org",
    "sentiment": "https://money.cnn.com/data/fear-and-greed/",
    "insider_trades": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4",
    "options_flow": "https://unusualwhales.com",
    "earnings_calendar": "https://finance.yahoo.com/calendar/earnings",
    "govt_contracts": "https://sam.gov/search/?index=opp",
    "sec_filings": "https://www.sec.gov/cgi-bin/browse-edgar",
    "dart_filings": "https://dart.fss.or.kr",
    "dart_battery": "https://dart.fss.or.kr",
    "news_cn": "https://www.scmp.com",
    "reservoir": "https://www.wra.gov.tw",
    "seismic": "https://earthquake.usgs.gov/earthquakes/map/",
    "ferc_queue": "https://www.ferc.gov/industries-data/electric/electric-power-markets/electric-queue",
    "kepco": "https://ember-climate.org/data/data-tools/data-explorer/",
    "reddit_velocity": "https://www.reddit.com/r/wallstreetbets",
    "arxiv_papers": "https://arxiv.org/list/cs.AI/recent",
    "biorxiv_preprints": "https://www.biorxiv.org",
    "pypi_stats": "https://pypistats.org",
    "github_velocity": "https://github.com/trending",
    "dutch_cbs": "https://www.cbs.nl/en-gb/figures/detail/84378ENG",
    "short_interest": "https://finra-markets.morningstar.com/ShortInterest.jsp",
    "sec_13f": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F",
    "trendforce": "https://www.trendforce.com",
    "etnews": "https://www.etnews.com",
    "calcalist": "https://www.calcalist.co.il",
    "lme_metals": "https://www.lme.com/en/metals",
    "cftc_cot": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
    "gacc_customs": "http://www.customs.gov.cn/customs/302249/302274/302277/index.html",
    "caixin_news": "https://www.caixinglobal.com",
    "huggingface_trends": "https://huggingface.co/models?sort=trending",
    "ecb_signals": "https://www.ecb.europa.eu/press/pr/date",
    "boj_signals": "https://www.boj.or.jp/en/mopo/mpmdeci/index.htm",
    "msia_semi": "https://www.sia.org/research-resources/annual-silicon-cycle/",
    "cpca_ev": "https://www.cpca.org.cn",
    "specialty_gas": "https://www.chemanalyst.com/industry-report",
    "israel_ia": "https://innovationisrael.org.il/en",
    "pmda_japan": "https://www.pmda.go.jp/english/review-services/reviews/approved-information/drugs/0001.html",
    "mfds_approvals": "https://www.mfds.go.kr/eng/brd/m_18/list.do",
    "app_store": "https://developer.apple.com/app-store/trends/",
    "fed_speeches": "https://www.federalreserve.gov/newsevents/speeches.htm",
    "eurlex": "https://eur-lex.europa.eu/search.html",
    "opec_news": "https://www.opec.org/opec_web/en/press_room/press_releases.htm",
    "hedge_fund_holdings": "https://whalewisdom.com",
    "congressional_trades": "https://efts.house.gov/LATEST/search-index?q=%22%22&type=DV",
}

try:
    from dotenv import load_dotenv
    load_dotenv(TRADING_DIR / "TradingAgents" / ".env")
except Exception:
    pass

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
.main { background: #0d1117; color: #c9d1d9; }
.block-container { padding-top: 1rem; max-width: 100%; }
div[data-testid="metric-container"] {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 8px; padding: 12px;
}
div[data-testid="metric-container"] label { color: #8b949e !important; }
div[data-testid="metric-container"] div[data-testid="metric-value"] { color: #c9d1d9 !important; }
.stExpander { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
h1, h2, h3 { color: #c9d1d9; }
.stDivider { border-color: #30363d; }
hr { border-color: #30363d; }
thead tr th { background: #21262d !important; color: #58a6ff !important; font-size: 12px; }
tbody tr:hover { background: #1c2128 !important; }
.section-header {
    color: #8b949e; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    border-bottom: 1px solid #30363d; padding-bottom: 6px; margin: 16px 0 12px 0;
}
</style>""", unsafe_allow_html=True)

# ── Helper functions ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_fx_rate():
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=AUD", timeout=5)
        return r.json()["rates"]["AUD"]
    except Exception:
        return 1.585

@st.cache_data(ttl=60)
def load_latest_kb(module_name):
    d = KB_DIR / module_name
    if not d.exists():
        return None, None
    files = sorted(d.glob("*.json"))
    if not files:
        return None, None
    f = files[-1]
    try:
        return json.loads(f.read_text()), f.stat().st_mtime
    except Exception:
        return None, None

def newest_mtime_in_dir(d: Path):
    if not d.exists():
        return None
    mtimes = [f.stat().st_mtime for f in d.rglob("*") if f.is_file()]
    return max(mtimes) if mtimes else None

def freshness_colour(mtime, warn_h=2, crit_h=24):
    if mtime is None:
        return "#6e7681"
    age_h = (time.time() - mtime) / 3600
    if age_h < warn_h:
        return "#3fb950"
    if age_h < crit_h:
        return "#d29922"
    return "#f85149"

def freshness_label(mtime):
    if mtime is None:
        return "never"
    age_s = time.time() - mtime
    if age_s < 60:
        return "just now"
    if age_s < 3600:
        return f"{int(age_s/60)}m ago"
    if age_s < 86400:
        return f"{int(age_s/3600)}h ago"
    return f"{int(age_s/86400)}d ago"

@st.cache_data(ttl=60)
def get_signals():
    try:
        from aggregate_signals import aggregate
        return aggregate(TICKERS)
    except Exception as e:
        return {
            "error": str(e), "macro": {}, "tickers": {},
            "global_alerts": [], "ranked": [], "source_coverage": {},
        }

@st.cache_data(ttl=30)
def get_alpaca_account():
    key    = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key:
        return None, []
    try:
        base = "https://paper-api.alpaca.markets"
        h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        acct = requests.get(f"{base}/v2/account", headers=h, timeout=6).json()
        pos  = requests.get(f"{base}/v2/positions", headers=h, timeout=6).json()
        return acct, (pos if isinstance(pos, list) else [])
    except Exception:
        return None, []

@st.cache_data(ttl=30)
def get_alpaca_prices():
    key    = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key:
        return {}
    try:
        base = "https://data.alpaca.markets"
        h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        syms = ",".join(TICKERS)
        r = requests.get(
            f"{base}/v2/stocks/trades/latest?symbols={syms}&feed=iex",
            headers=h, timeout=8
        ).json()
        return {t: v["p"] for t, v in r.get("trades", {}).items()}
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_finnhub_prices():
    token = os.getenv("FINNHUB_API_KEY", "d6vbmq1r01qiiutb7gegd6vbmq1r01qiiutb7gf0")
    if not token:
        return {}
    prices = {}
    for t in TICKERS[:6]:  # rate limit — only top tier
        try:
            r = requests.get(
                f"https://finnhub.io/api/v1/quote?symbol={t}&token={token}",
                timeout=3
            ).json()
            if r.get("c"):
                prices[t] = r["c"]
        except Exception:
            pass
    return prices

def score_to_pct(score):
    # score range approximately -1 to +1, map to 0-100
    return max(0, min(100, int((score + 1) * 50)))

def rec_colour(rec):
    rec = (rec or "").upper()
    if "BUY" in rec:    return "#3fb950"
    if "SELL" in rec:   return "#f85149"
    if "HOLD" in rec:   return "#d29922"
    return "#8b949e"

def pipe_box(label, sublabel, mtime, warn_h=2, crit_h=24):
    c = freshness_colour(mtime, warn_h, crit_h)
    age = freshness_label(mtime)
    return f"""<div style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:14px 16px;min-width:130px;text-align:center;flex-shrink:0">
  <div style="color:#58a6ff;font-size:11px;font-weight:700;letter-spacing:0.5px">{label}</div>
  <div style="color:#8b949e;font-size:10px;margin:2px 0">{sublabel}</div>
  <div style="color:{c};font-size:10px;margin-top:6px">● {age}</div>
</div>"""

def arrow():
    return '<div style="color:#30363d;font-size:22px;font-weight:300;flex-shrink:0;align-self:center">→</div>'

# ── Page header ───────────────────────────────────────────────────────────────
now_str = datetime.now().strftime("%a %d %b %Y  %H:%M AWST")
st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;padding:8px 0">
  <div>
    <span style="color:#58a6ff;font-size:20px;font-weight:700;letter-spacing:1px">◈ LARSEN VENTURES</span>
    <span style="color:#8b949e;font-size:13px;margin-left:12px">Trading Intelligence</span>
  </div>
  <div style="color:#8b949e;font-size:12px">{now_str} &nbsp;·&nbsp; Auto-refresh 60s</div>
</div>""", unsafe_allow_html=True)

fx = get_fx_rate()
signals = get_signals()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — STATUS BAR
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">System Status</div>', unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)

# Macro gate
macro_data, macro_mtime = load_latest_kb("macro_data")
gate_val = "—"
regime = ""
spy_price = vix_val = None
if macro_data and isinstance(macro_data, dict):
    gate_raw = macro_data.get("macro_gate", macro_data.get("gate"))
    gate_val = "PASS" if gate_raw else "FAIL"
    regime   = macro_data.get("regime", "")
    ind = macro_data.get("indicators", {})
    spy_price = ind.get("SPY", {}).get("price") if ind else macro_data.get("SPY_price")
    spy_sma   = ind.get("SPY", {}).get("sma_200") if ind else None
    vix_val   = ind.get("VIX", {}).get("current") if ind else None
c1.metric("Macro Gate", gate_val, delta=regime or None)

# Fear & Greed
fg_score, fg_label = None, "—"
sent_dir = KB_DIR / "sentiment"
if sent_dir.exists():
    for f in sorted(sent_dir.glob("*.json"), reverse=True):
        try:
            d = json.loads(f.read_text())
            fg = d.get("fear_greed", {})
            if isinstance(fg, dict) and fg:
                fg_score = fg.get("value") or fg.get("score")
                fg_label = fg.get("classification", fg.get("label", "—"))
                break
            elif isinstance(fg, (int, float)):
                fg_score = fg
                break
        except Exception:
            pass
c2.metric("Fear & Greed", str(int(fg_score)) if fg_score is not None else "—", delta=fg_label if fg_label not in ("—", str(fg_score)) else None)

# SPY
if spy_price and spy_sma:
    gap = ((spy_price - spy_sma) / spy_sma) * 100
    c3.metric("SPY", f"${spy_price * fx:,.0f}", delta=f"{gap:+.1f}% vs 200SMA")
elif spy_price:
    c3.metric("SPY", f"${spy_price * fx:,.0f}")
else:
    c3.metric("SPY", "—")

# VIX
if vix_val:
    vix_label = "Elevated" if vix_val > 20 else "Normal"
    c4.metric("VIX", f"{vix_val:.1f}", delta=vix_label)
else:
    c4.metric("VIX", "—")

# Active cron jobs
c5.metric("Active Cron Jobs", "57")

# Last KB refresh
all_mtimes = [
    newest_mtime_in_dir(KB_DIR / m) for m in KB_MODULES
]
valid_mtimes = [m for m in all_mtimes if m]
last_refresh = max(valid_mtimes) if valid_mtimes else None
c6.metric("Last KB Refresh", freshness_label(last_refresh))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PIPELINE ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Data Pipeline</div>', unsafe_allow_html=True)

# Pipeline step freshness
today = datetime.now().strftime("%Y-%m-%d")
l1_mtime = last_refresh
l3_mtime = newest_mtime_in_dir(KB_DIR)   # aggregate runs after KB
l4_mtime = newest_mtime_in_dir(KB_DIR / "dart_filings")  # proxy for RAG ingest
l5_mtime = Path(f"/tmp/trading_prepare_{today}.log").stat().st_mtime if Path(f"/tmp/trading_prepare_{today}.log").exists() else None
l6_mtime = Path("/tmp/trading_execute.log").stat().st_mtime if Path("/tmp/trading_execute.log").exists() else None
l7_mtime = newest_mtime_in_dir(FEEDBACK_DIR / "decisions")

edge_mtime = newest_mtime_in_dir(KB_DIR / "sec_filings")

pipe_html = f"""<div style="display:flex;align-items:stretch;gap:8px;padding:20px;background:#161b22;border-radius:8px;overflow-x:auto;margin:8px 0">
  {pipe_box("L1 · DATA SOURCES", "44 KB modules", l1_mtime, warn_h=3, crit_h=12)}
  {arrow()}
  {pipe_box("L3 · AGGREGATE", "Signal scoring", l3_mtime, warn_h=3, crit_h=12)}
  {arrow()}
  {pipe_box("L4 · RAG INGEST", "Supabase pgvector", l4_mtime, warn_h=2, crit_h=6)}
  {arrow()}
  {pipe_box("L5 · PREPARE", "6pm AWST analysis", l5_mtime, warn_h=20, crit_h=26)}
  {arrow()}
  {pipe_box("L6 · EXECUTE", "9:30pm at market open", l6_mtime, warn_h=20, crit_h=26)}
  {arrow()}
  {pipe_box("L7 · FEEDBACK", "Decisions + scoring", l7_mtime, warn_h=24, crit_h=48)}
  <div style="margin-left:16px;border-left:1px solid #30363d;padding-left:16px;display:flex;flex-direction:column;gap:8px;justify-content:center">
    {pipe_box("L2 · EDGE ALERTS", "SEC 8-K 5-min", edge_mtime, warn_h=1, crit_h=3)}
  </div>
</div>"""

st.markdown(pipe_html, unsafe_allow_html=True)

# Expander: data source detail
with st.expander("Data Sources Detail — all 44 modules"):
    fresh_count   = sum(1 for m in all_mtimes if m and (time.time()-m)/3600 < 2)
    stale_count   = sum(1 for m in all_mtimes if m and 2 <= (time.time()-m)/3600 < 24)
    old_count     = sum(1 for m in all_mtimes if m and (time.time()-m)/3600 >= 24)
    missing_count = sum(1 for m in all_mtimes if not m)
    st.markdown(
        f'<span style="color:#3fb950">● {fresh_count} fresh</span> &nbsp; '
        f'<span style="color:#d29922">● {stale_count} stale</span> &nbsp; '
        f'<span style="color:#f85149">● {old_count} old</span> &nbsp; '
        f'<span style="color:#6e7681">● {missing_count} missing</span>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — GLOBAL ALERTS + SIGNAL RANKINGS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Signal Intelligence</div>', unsafe_allow_html=True)

# Global alerts
alerts = signals.get("global_alerts", [])
if alerts:
    for alert in alerts:
        colour = "#f85149" if "GATE" in alert.upper() or "MACRO" in alert.upper() or "CRITICAL" in alert.upper() else "#d29922"
        st.markdown(
            f'<div style="background:#1c0f0f;border-left:3px solid {colour};padding:10px 14px;border-radius:4px;margin:4px 0;color:{colour};font-size:13px">'
            f'⚠ {alert}</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown('<div style="color:#8b949e;font-size:13px;padding:8px 0">No active alerts</div>', unsafe_allow_html=True)

col_left, col_right = st.columns([3, 2])

with col_left:
    st.markdown("**Signal Rankings**")
    ranked = signals.get("ranked", [])
    tickers_data = signals.get("tickers", {})
    if ranked and tickers_data:
        rows = []
        for ticker in ranked:
            td = tickers_data.get(ticker, {})
            score = td.get("score", 0) or 0
            rows.append({
                "Ticker": ticker,
                "Company": COMPANY_NAMES.get(ticker, ""),
                "Tier": f"T{TIER_MAP.get(ticker,3)}",
                "Score": round(score, 3),
                "Conviction": td.get("conviction", "—"),
                "Recommendation": td.get("recommendation", "—"),
                "Sources": td.get("source_count", 0),
            })
        df = pd.DataFrame(rows)

        def colour_rec(val):
            c = rec_colour(val)
            return f"color: {c}"
        def colour_score(val):
            if val > 0.1: return "color: #3fb950"
            if val < -0.1: return "color: #f85149"
            return "color: #d29922"

        st.dataframe(
            df.style
              .applymap(colour_rec, subset=["Recommendation"])
              .applymap(colour_score, subset=["Score"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Signal aggregation loading…")

with col_right:
    st.markdown("**Source Coverage**")
    src_cov = signals.get("source_coverage", {})
    if src_cov:
        src_df = pd.DataFrame(
            sorted(src_cov.items(), key=lambda x: x[1], reverse=True),
            columns=["Source", "Tickers"]
        )
        fig = px.bar(
            src_df, x="Tickers", y="Source", orientation="h",
            color="Tickers",
            color_continuous_scale=["#21262d","#58a6ff"],
        )
        fig.update_layout(
            paper_bgcolor="#161b22", plot_bgcolor="#161b22",
            font_color="#c9d1d9", height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=False, coloraxis_showscale=False,
            xaxis=dict(gridcolor="#30363d"),
            yaxis=dict(gridcolor="#30363d"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # F&G gauge
    if fg_score is not None:
        fig2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=fg_score,
            title={"text": "Fear & Greed", "font": {"color": "#8b949e", "size": 12}},
            number={"font": {"color": "#c9d1d9", "size": 28}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#8b949e"},
                "bar": {"color": "#58a6ff"},
                "bgcolor": "#161b22",
                "bordercolor": "#30363d",
                "steps": [
                    {"range": [0, 25],  "color": "#2d1515"},
                    {"range": [25, 45], "color": "#2d2015"},
                    {"range": [45, 55], "color": "#21262d"},
                    {"range": [55, 75], "color": "#152d15"},
                    {"range": [75, 100],"color": "#0f2d0f"},
                ],
                "threshold": {"line": {"color": "#f85149", "width": 2}, "value": fg_score},
            },
        ))
        fig2.update_layout(
            paper_bgcolor="#161b22", font_color="#c9d1d9",
            height=200, margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — WATCHLIST GRID
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Watchlist</div>', unsafe_allow_html=True)

prices = get_alpaca_prices()
if not prices:
    prices = get_finnhub_prices()

tickers_data = signals.get("tickers", {})
cards_per_row = 3
rows_html = []
for i in range(0, len(TICKERS), cards_per_row):
    batch = TICKERS[i:i+cards_per_row]
    row_cards = []
    for ticker in batch:
        td     = tickers_data.get(ticker, {})
        score  = td.get("score", 0) or 0
        rec    = td.get("recommendation", "—")
        sigs   = [s.get("source","") for s in td.get("signals", []) if s.get("source")][:5]
        tier   = TIER_MAP.get(ticker, 3)
        price_usd = prices.get(ticker)
        price_str = f"${price_usd * fx:,.2f} AUD" if price_usd else "— AUD"
        score_pct = score_to_pct(score)
        score_col = "#3fb950" if score > 0.05 else ("#f85149" if score < -0.05 else "#d29922")
        rec_col   = rec_colour(rec)
        tier_cols = {1: "#58a6ff", 2: "#d29922", 3: "#8b949e"}
        tier_col  = tier_cols.get(tier, "#8b949e")

        sig_tags = "".join(
            f'<span style="background:#21262d;color:#8b949e;font-size:9px;padding:2px 5px;border-radius:3px;margin:1px">{s}</span>'
            for s in sigs
        )

        card = f"""<a href="https://finance.yahoo.com/quote/{ticker}" target="_blank" style="text-decoration:none;display:block;flex:1">
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin:4px;transition:border-color 0.2s;cursor:pointer"
     onmouseover="this.style.borderColor='#58a6ff'" onmouseout="this.style.borderColor='#30363d'">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2px">
    <span style="color:#c9d1d9;font-weight:600;font-size:15px">{ticker}</span>
    <span style="background:#21262d;color:{tier_col};font-size:9px;padding:2px 6px;border-radius:3px;font-weight:600">T{tier}</span>
  </div>
  <div style="color:#8b949e;font-size:11px;margin-bottom:6px">{COMPANY_NAMES.get(ticker,"")}</div>
  <div style="color:#c9d1d9;font-size:17px;font-weight:600;margin:4px 0">{price_str}</div>
  <div style="margin:8px 0;height:4px;background:#21262d;border-radius:2px">
    <div style="height:4px;background:{score_col};border-radius:2px;width:{score_pct}%"></div>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span style="color:#8b949e;font-size:10px">Score: {score:+.3f}</span>
    <span style="color:{rec_col};font-size:10px;font-weight:600">{rec}</span>
  </div>
  <div style="display:flex;gap:3px;flex-wrap:wrap">{sig_tags}</div>
</div></a>"""
        row_cards.append(card)

    # pad row if needed
    while len(row_cards) < cards_per_row:
        row_cards.append('<div style="flex:1;margin:4px"></div>')

    rows_html.append(
        f'<div style="display:flex;gap:0;margin-bottom:4px">'
        + "".join(row_cards)
        + "</div>"
    )

st.markdown("".join(rows_html), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — TRADING PIPELINE TIMELINE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Today\'s Pipeline</div>', unsafe_allow_html=True)

def tl_step(time_str, name, status, detail=""):
    if status == "done":
        col, icon = "#3fb950", "✓"
    elif status == "running":
        col, icon = "#58a6ff", "⟳"
    elif status == "missed":
        col, icon = "#f85149", "✗"
    else:
        col, icon = "#6e7681", "○"
    return f"""<div style="text-align:center;min-width:110px;flex-shrink:0">
  <div style="color:{col};font-size:18px">{icon}</div>
  <div style="color:#58a6ff;font-size:10px;font-weight:600">{time_str}</div>
  <div style="color:#c9d1d9;font-size:11px;margin:2px 0">{name}</div>
  <div style="color:#8b949e;font-size:10px">{detail}</div>
</div>"""

def tl_line(done=False):
    c = "#3fb950" if done else "#30363d"
    return f'<div style="flex:1;height:2px;background:{c};align-self:center;margin:0 4px;margin-bottom:18px"></div>'

now_h = datetime.now().hour + datetime.now().minute / 60
kb_done      = last_refresh and (time.time() - last_refresh) < 7200
prepare_done = l5_mtime is not None
brief_done   = Path(f"/tmp/analysis_status_{today}.txt").exists()
execute_done = l6_mtime is not None
midday_done  = now_h > 23.5
afterh_done  = now_h > 4.5

tl_html = f"""<div style="display:flex;align-items:center;padding:20px;background:#161b22;border-radius:8px;overflow-x:auto;margin:8px 0">
  {tl_step("5:00pm", "KB Refresh", "done" if kb_done else "pending")}
  {tl_line(kb_done and prepare_done)}
  {tl_step("6:00pm", "PREPARE", "done" if prepare_done else "pending", "TradingAgents")}
  {tl_line(prepare_done and brief_done)}
  {tl_step("9:00pm", "Brief", "done" if brief_done else "pending", "Pre-trade review")}
  {tl_line(brief_done and execute_done)}
  {tl_step("9:30pm", "EXECUTE", "done" if execute_done else "pending", "Market open")}
  {tl_line(execute_done and midday_done)}
  {tl_step("11:30pm", "Midday", "done" if midday_done else "pending", "Position check")}
  {tl_line(midday_done and afterh_done)}
  {tl_step("4:30am", "After-hours", "done" if afterh_done else "pending", "Earnings review")}
</div>"""
st.markdown(tl_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Portfolio</div>', unsafe_allow_html=True)

acct, positions = get_alpaca_account()
STARTING_AUD = 10_000.0

if acct:
    equity_usd = float(acct.get("equity", 0))
    cash_usd   = float(acct.get("cash", 0))
    equity_aud = equity_usd * fx
    cash_aud   = cash_usd   * fx
    pnl_aud    = equity_aud - STARTING_AUD
    pnl_pct    = (pnl_aud / STARTING_AUD) * 100

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Portfolio Value",  f"${equity_aud:,.0f} AUD", delta=f"{pnl_pct:+.2f}% vs benchmark")
    m2.metric("Cash",             f"${cash_aud:,.0f} AUD")
    m3.metric("Open Positions",   str(len(positions)))
    deployed_pct = ((equity_aud - cash_aud) / equity_aud * 100) if equity_aud else 0
    m4.metric("Deployed",         f"{deployed_pct:.1f}%", delta="Max 20% (gate FAIL)" if gate_val == "FAIL" else "Gate PASS")

if positions:
    rows = []
    for p in positions:
        ticker = p.get("symbol","")
        qty    = float(p.get("qty", 0))
        entry  = float(p.get("avg_entry_price", 0))
        curr   = float(p.get("current_price", 0))
        unreal = float(p.get("unrealized_pl", 0))
        pnl_p  = float(p.get("unrealized_plpc", 0)) * 100
        stop   = entry * 0.95
        t1     = entry * 1.08
        t2     = entry * 1.15
        rows.append({
            "Ticker":     ticker,
            "Qty":        qty,
            "Entry AUD":  f"${entry*fx:,.2f}",
            "Current AUD":f"${curr*fx:,.2f}",
            "Unreal P&L": f"${unreal*fx:,.0f}",
            "P&L %":      f"{pnl_p:+.2f}%",
            "Stop":       f"${stop*fx:,.2f}",
            "T1 (+8%)":   f"${t1*fx:,.2f}",
            "T2 (+15%)":  f"${t2*fx:,.2f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    macro = signals.get("macro", {})
    cash_pct = int((macro.get("cash_reserve", 0.8)) * 100)
    st.markdown(
        f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;color:#8b949e">'
        f'Macro gate <span style="color:#f85149">FAIL</span> — holding {cash_pct}% cash. '
        f'Max deployed: {100-cash_pct}%. No positions open.</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — KB HEALTH
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("Knowledge Base — 44 Modules"):
    kb_rows = []
    for mod in KB_MODULES:
        d = KB_DIR / mod
        files = sorted(d.glob("*.json")) if d.exists() else []
        mtime  = files[-1].stat().st_mtime if files else None
        colour = freshness_colour(mtime, warn_h=2, crit_h=24)
        url    = KB_MODULE_URLS.get(mod, "")
        link   = f'<a href="{url}" target="_blank" style="color:#58a6ff;font-size:10px">↗</a>' if url else ""
        kb_rows.append({
            "": f'<span style="color:{colour}">●</span>',
            "Module": f'{mod} {link}',
            "Files": len(files),
            "Last Updated": freshness_label(mtime),
        })

    # Render as HTML table
    rows_html = ""
    for r in kb_rows:
        rows_html += f'<tr><td style="text-align:center">{r[""]}</td><td style="font-size:12px">{r["Module"]}</td><td style="text-align:center;color:#8b949e;font-size:12px">{r["Files"]}</td><td style="color:#8b949e;font-size:12px">{r["Last Updated"]}</td></tr>'

    st.markdown(f"""<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="width:30px;background:#21262d;color:#58a6ff;font-size:11px;padding:6px"> </th>
  <th style="background:#21262d;color:#58a6ff;font-size:11px;padding:6px;text-align:left">Module</th>
  <th style="background:#21262d;color:#58a6ff;font-size:11px;padding:6px">Files</th>
  <th style="background:#21262d;color:#58a6ff;font-size:11px;padding:6px;text-align:left">Last Updated</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — FEEDBACK LOOP
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("Feedback Loop — Signal Accuracy"):
    dec_dir  = FEEDBACK_DIR / "decisions"
    out_dir  = FEEDBACK_DIR / "outcomes"
    cf_dir   = FEEDBACK_DIR / "counterfactuals"
    n_dec    = len(list(dec_dir.glob("*.json")))  if dec_dir.exists()  else 0
    n_out    = len(list(out_dir.glob("*.json")))  if out_dir.exists()  else 0
    n_cf     = len(list(cf_dir.glob("*.json")))   if cf_dir.exists()   else 0

    fa, fb, fc = st.columns(3)
    fa.metric("Decisions Logged",     str(n_dec))
    fb.metric("Outcomes Resolved",    str(n_out))
    fc.metric("Counterfactuals",      str(n_cf))

    acc_file = FEEDBACK_DIR / "accuracy_scores.json"
    if acc_file.exists():
        try:
            acc = json.loads(acc_file.read_text())
            rows = []
            MIN_TRADES = 5
            for src, d in sorted(acc.items(), key=lambda x: -(x[1].get("hit_rate") or 0)):
                calls    = d.get("total_calls", 0)
                hit_rate = d.get("hit_rate")
                weight   = d.get("current_weight", d.get("default_weight", "—"))
                locked   = calls < MIN_TRADES
                rows.append({
                    "Source":    src,
                    "Calls":     calls,
                    "Hit Rate":  f"{hit_rate:.1%}" if hit_rate is not None else "—",
                    "Weight":    f"{weight:.3f}" if isinstance(weight, float) else str(weight),
                    "Status":    "locked" if locked else "live",
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No accuracy data yet — accumulating signal history.")
        except Exception as e:
            st.caption(f"Could not load accuracy scores: {e}")
    else:
        st.caption("accuracy_scores.json not found.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — TRADE HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("Trade History"):
    th_path = TRADING_DIR / "TradingAgents" / "trade_history.json"
    if th_path.exists():
        try:
            trades = json.loads(th_path.read_text())
            if trades:
                rows = []
                for t in reversed(trades[-50:]):
                    rows.append({
                        "Date":     t.get("date",""),
                        "Ticker":   t.get("ticker",""),
                        "Action":   t.get("action",""),
                        "Qty":      t.get("qty",""),
                        "Price AUD":f"${float(t.get('price',0))*fx:.2f}" if t.get("price") else "—",
                        "P&L AUD":  f"${float(t.get('pnl',0))*fx:.0f}" if t.get("pnl") else "—",
                        "Reason":   t.get("reason",""),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("No closed trades yet — paper trial in progress.")
        except Exception as e:
            st.caption(f"Could not load trade history: {e}")
    else:
        st.info("No closed trades yet — paper trial in progress.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="color:#6e7681;font-size:10px;text-align:center;margin-top:16px;padding-top:8px;border-top:1px solid #30363d">'
    f'Larsen Ventures Trading Intelligence &nbsp;·&nbsp; '
    f'<a href="https://trading.larsenfamily.com.au" style="color:#58a6ff">trading.larsenfamily.com.au</a> &nbsp;·&nbsp; '
    f'<a href="https://chappie.larsenfamily.com.au" style="color:#8b949e">chappie.larsenfamily.com.au</a> &nbsp;·&nbsp; '
    f'FX: 1 USD = {fx:.4f} AUD &nbsp;·&nbsp; '
    f'Loaded: {datetime.now().strftime("%H:%M:%S")}'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Auto-refresh ──────────────────────────────────────────────────────────────
time.sleep(60)
st.rerun()
