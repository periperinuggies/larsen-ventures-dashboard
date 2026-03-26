import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json, os, sys, time, requests
from pathlib import Path
from datetime import datetime, timezone

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
SECTOR_MAP = {
    "NVDA":"Semis","MSFT":"Cloud","AVGO":"Semis","CRWD":"Security",
    "META":"Social","GOOGL":"Cloud","AMD":"Semis","PANW":"Security",
    "AMAT":"Semis EQ","LRCX":"Semis EQ","ARM":"Semis","AMZN":"Cloud",
    "ZS":"Security","SNOW":"Data","LLY":"Pharma","NVO":"Pharma",
    "KLAC":"Semis EQ","MDB":"Data","S":"Security",
}

KB_MODULES = [
    ("macro_data",          "Macro & Rates",        "FRED / yfinance",     "https://fred.stlouisfed.org",             "[M]"),
    ("sentiment",           "Fear & Greed + Trends","CNN / Google Trends", "https://money.cnn.com/data/fear-and-greed/","[S]"),
    ("insider_trades",      "Insider Form 4",       "SEC EDGAR",           "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4", "[I]"),
    ("options_flow",        "Options Flow",         "Unusual Whales",      "https://unusualwhales.com",               "[O]"),
    ("earnings_calendar",   "Earnings Calendar",    "Finnhub",             "https://finance.yahoo.com/calendar/earnings","[E]"),
    ("govt_contracts",      "Govt Contracts",       "USASpending.gov",     "https://sam.gov/search/?index=opp",       "[G]"),
    ("sec_filings",         "SEC 8-K Filings",      "SEC EDGAR",           "https://efts.house.gov/LATEST/search-index","[8K]"),
    ("dart_filings",        "DART Korea Filings",   "FSS DART",            "https://dart.fss.or.kr",                 "[KR]"),
    ("dart_battery",        "DART Battery Co",      "FSS DART",            "https://dart.fss.or.kr",                 "[KR]"),
    ("news_cn",             "China Tech News",      "36Kr / Caixin",       "https://36kr.com",                       "[CN]"),
    ("caixin_news",         "Caixin Financial",     "Caixin Global",       "https://www.caixinglobal.com",            "[CN]"),
    ("reservoir",           "Taiwan Reservoir",     "WRA Taiwan",          "https://www.wra.gov.tw",                 "[TW]"),
    ("seismic",             "USGS Seismic",         "USGS",                "https://earthquake.usgs.gov",            "[GE]"),
    ("ferc_queue",          "FERC / EIA Grid",      "EIA API",             "https://www.eia.gov/opendata/",          "[EL]"),
    ("kepco",               "Korea Electricity",    "EMBER Climate",       "https://ember-climate.org/data/",        "[KR]"),
    ("reddit_velocity",     "Reddit Velocity",      "Reddit API",          "https://www.reddit.com/r/wallstreetbets","[SO]"),
    ("arxiv_papers",        "arXiv Papers",         "arXiv.org",           "https://arxiv.org/list/cs.AI/recent",   "[AR]"),
    ("biorxiv_preprints",   "BioRxiv Preprints",    "bioRxiv",             "https://www.biorxiv.org",               "[BIO]"),
    ("pypi_stats",          "PyPI Downloads",       "PyPI Stats",          "https://pypistats.org",                 "[PY]"),
    ("github_velocity",     "GitHub Velocity",      "GitHub API",          "https://github.com/trending",           "[GH]"),
    ("dutch_cbs",           "Dutch CBS (ASML)",     "CBS Netherlands",     "https://www.cbs.nl/en-gb",              "[NL]"),
    ("short_interest",      "Short Interest",       "FINRA",               "https://finra-markets.morningstar.com/ShortInterest.jsp","[SI]"),
    ("sec_13f",             "Hedge Fund 13F",       "SEC EDGAR",           "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F","[13F]"),
    ("trendforce",          "TrendForce Reports",   "TrendForce",          "https://www.trendforce.com",            "[TF]"),
    ("etnews",              "ETNews Korea",         "ETNews",              "https://www.etnews.com",                "[KR]"),
    ("calcalist",           "Calcalist Israel",     "Calcalist",           "https://www.calcalist.co.il",           "[IL]"),
    ("lme_metals",          "LME Metals",           "yfinance",            "https://www.lme.com/en/metals",         "[LM]"),
    ("cftc_cot",            "CFTC CoT",             "CFTC",                "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm","[CF]"),
    ("gacc_customs",        "GACC Customs",         "MOFCOM / NBS",        "http://www.customs.gov.cn",             "[CN]"),
    ("huggingface_trends",  "HuggingFace Trends",   "HuggingFace",         "https://huggingface.co/models?sort=trending","[HF]"),
    ("ecb_signals",         "ECB Signals",          "ECB RSS",             "https://www.ecb.europa.eu/press/pr",    "[EU]"),
    ("boj_signals",         "BOJ Signals",          "BOJ RSS",             "https://www.boj.or.jp/en",              "[JP]"),
    ("msia_semi",           "Malaysia Semi",        "MSIA",                "https://www.sia.org",                   "[MY]"),
    ("cpca_ev",             "China EV Sales",       "CPCA",                "https://www.cpca.org.cn",               "[CN]"),
    ("specialty_gas",       "Specialty Gas",        "ChemAnalyst",         "https://www.chemanalyst.com",           "[GS]"),
    ("israel_ia",           "Israel Innovation",    "IIA",                 "https://innovationisrael.org.il/en",    "[IL]"),
    ("pmda_japan",          "PMDA Japan",           "PMDA",                "https://www.pmda.go.jp/english",        "[JP]"),
    ("mfds_approvals",      "MFDS Korea",           "MFDS",                "https://www.mfds.go.kr/eng",            "[KR]"),
    ("app_store",           "App Store Trends",     "Apple",               "https://developer.apple.com/app-store", "[AP]"),
    ("fed_speeches",        "Fed Speeches",         "Federal Reserve",     "https://www.federalreserve.gov/newsevents/speeches.htm","[FD]"),
    ("eurlex",              "EU Lex / Chips Act",   "EUR-Lex",             "https://eur-lex.europa.eu",             "[EU]"),
    ("opec_news",           "OPEC News",            "OPEC",                "https://www.opec.org/opec_web/en/press_room/","[OP]"),
    ("hedge_fund_holdings", "Hedge Fund Holdings",  "Whale Wisdom / 13F",  "https://whalewisdom.com",               "[HF]"),
    ("congressional_trades","Congressional Trades", "FMP / House Disc.",   "https://efts.house.gov/LATEST/search-index?q=%22%22&type=DV","[DC]"),
]

TICKER_LINKS = {
    "yahoo":    lambda t: f"https://finance.yahoo.com/quote/{t}",
    "finviz":   lambda t: f"https://finviz.com/quote.ashx?t={t}",
    "sec":      lambda t: f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={t}&type=8-K",
    "stockanalysis": lambda t: f"https://stockanalysis.com/stocks/{t.lower()}/",
    "wsj":      lambda t: f"https://www.wsj.com/market-data/quotes/{t}",
    "seekingalpha": lambda t: f"https://seekingalpha.com/symbol/{t}",
    "tipranks":  lambda t: f"https://www.tipranks.com/stocks/{t.lower()}/forecast",
    "unusualwhales": lambda t: f"https://unusualwhales.com/stocks/{t.lower()}",
    "alpaca":    "https://app.alpaca.markets/paper/dashboard/overview",
}

try:
    from dotenv import load_dotenv
    load_dotenv(TRADING_DIR / "TradingAgents" / ".env")
except Exception:
    pass

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
/* Reset & base */
.stApp { background: #0d1117; }
.main .block-container {
    padding: 1.5rem 2rem 2rem 2rem;
    max-width: 100%;
    background: #0d1117;
}
/* Metrics */
div[data-testid="metric-container"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px;
    padding: 14px 16px !important;
}
div[data-testid="metric-container"] label {
    color: #8b949e !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="metric-container"] div[data-testid="metric-value"] {
    color: #c9d1d9 !important;
    font-size: 20px !important;
    font-weight: 600;
}
/* Tabs */
div[data-baseweb="tab-list"] {
    background: #161b22 !important;
    border-radius: 8px;
    padding: 4px;
    gap: 2px;
    border: 1px solid #30363d;
    margin-bottom: 16px;
}
div[data-baseweb="tab"] {
    background: transparent !important;
    color: #8b949e !important;
    border-radius: 6px !important;
    padding: 8px 18px !important;
    font-size: 13px !important;
    font-weight: 500;
    border: none !important;
}
div[aria-selected="true"][data-baseweb="tab"] {
    background: #21262d !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
}
/* Expanders */
details[data-testid="stExpander"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
}
/* Tables */
thead tr th {
    background: #21262d !important;
    color: #58a6ff !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
tbody tr { background: #161b22 !important; }
tbody tr:hover { background: #1c2128 !important; }
/* Typography */
h1, h2, h3 { color: #c9d1d9 !important; }
p, li { color: #c9d1d9; }
hr { border-color: #30363d; }
/* Select widgets */
div[data-baseweb="select"] > div {
    background: #161b22 !important;
    border-color: #30363d !important;
    color: #c9d1d9 !important;
}
</style>""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

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

def freshness_badge(mtime, warn_h=2, crit_h=24):
    c = freshness_colour(mtime, warn_h, crit_h)
    lbl = freshness_label(mtime)
    return f'<span style="color:{c};font-size:13px">●</span> <span style="color:{c};font-size:11px">{lbl}</span>'

@st.cache_data(ttl=60)
def get_signals():
    try:
        from aggregate_signals import aggregate
        return aggregate(TICKERS)
    except Exception as e:
        return {"error": str(e), "macro":{}, "tickers":{}, "global_alerts":[], "ranked":[], "source_coverage":{}}

@st.cache_data(ttl=30)
def get_alpaca_account():
    key, secret = os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY")
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
    key, secret = os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY")
    if not key:
        return {}
    try:
        h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        r = requests.get(
            f"https://data.alpaca.markets/v2/stocks/trades/latest?symbols={','.join(TICKERS)}&feed=iex",
            headers=h, timeout=8
        ).json()
        return {t: v["p"] for t, v in r.get("trades", {}).items()}
    except Exception:
        return {}

@st.cache_data(ttl=60)
def get_finnhub_prices():
    token = os.getenv("FINNHUB_API_KEY", "d6vbmq1r01qiiutb7gegd6vbmq1r01qiiutb7gf0")
    prices, changes = {}, {}
    for t in TICKERS:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={t}&token={token}", timeout=3).json()
            if r.get("c"):
                prices[t] = r["c"]
                changes[t] = r.get("dp", 0)  # % change
        except Exception:
            pass
        time.sleep(0.07)
    return prices, changes

def rec_colour(rec):
    rec = (rec or "").upper()
    if "BUY" in rec:  return "#3fb950"
    if "SELL" in rec: return "#f85149"
    if "HOLD" in rec: return "#d29922"
    return "#8b949e"

def score_to_pct(score):
    return max(0, min(100, int((float(score or 0) + 1) * 50)))

def pipe_box(label, sublabel, mtime, warn_h=2, crit_h=24):
    c   = freshness_colour(mtime, warn_h, crit_h)
    age = freshness_label(mtime)
    return (
        f'<div style="background:#21262d;border:1px solid #30363d;border-radius:6px;'
        f'padding:14px 16px;min-width:130px;text-align:center;flex-shrink:0">'
        f'<div style="color:#58a6ff;font-size:11px;font-weight:700;letter-spacing:0.5px">{label}</div>'
        f'<div style="color:#8b949e;font-size:10px;margin:2px 0">{sublabel}</div>'
        f'<div style="color:{c};font-size:10px;margin-top:6px">● {age}</div>'
        f'</div>'
    )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════════════
now_str = datetime.now().strftime("%a %d %b %Y  %H:%M AWST")
st.markdown(f"""
<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;
            padding:16px 24px;margin-bottom:16px;
            display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:16px">
    <span style="color:#58a6ff;font-size:26px;font-weight:700;letter-spacing:1.5px">◈ LARSEN VENTURES</span>
    <span style="color:#30363d;font-size:20px">|</span>
    <span style="color:#8b949e;font-size:14px">Trading Intelligence</span>
  </div>
  <div style="text-align:right">
    <div style="color:#c9d1d9;font-size:13px;font-weight:500">{now_str}</div>
    <div style="color:#8b949e;font-size:11px;margin-top:2px">Auto-refresh every 60s</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load core data ────────────────────────────────────────────────────────────
fx      = get_fx_rate()
signals = get_signals()
prices_alpaca = get_alpaca_prices()

# ══════════════════════════════════════════════════════════════════════════════
# STATUS STRIP (always visible, above tabs)
# ══════════════════════════════════════════════════════════════════════════════
macro_data, macro_mtime = load_latest_kb("macro_data")
gate_val = "—"; regime = ""; spy_price = spy_sma = vix_val = None
if macro_data and isinstance(macro_data, dict):
    gate_raw  = macro_data.get("macro_gate", macro_data.get("gate"))
    gate_val  = "PASS" if gate_raw else "FAIL"
    regime    = macro_data.get("regime", "")
    ind       = macro_data.get("indicators", {})
    spy_price = ind.get("SPY", {}).get("price")
    spy_sma   = ind.get("SPY", {}).get("sma_200")
    vix_val   = ind.get("VIX", {}).get("current")

fg_score, fg_label = None, "—"
sent_dir = KB_DIR / "sentiment"
if sent_dir.exists():
    for f in sorted(sent_dir.glob("*.json"), reverse=True):
        try:
            d = json.loads(f.read_text())
            fg = d.get("fear_greed", {})
            if isinstance(fg, dict) and fg:
                fg_score = fg.get("value") or fg.get("score")
                fg_label = fg.get("classification", "—")
                break
        except Exception:
            pass

all_module_mtimes = [newest_mtime_in_dir(KB_DIR / m[0]) for m in KB_MODULES]
valid_mtimes = [m for m in all_module_mtimes if m]
last_refresh = max(valid_mtimes) if valid_mtimes else None

gate_col   = "#3fb950" if gate_val == "PASS" else ("#f85149" if gate_val == "FAIL" else "#8b949e")
fg_col     = "#f85149" if fg_score and fg_score < 25 else ("#3fb950" if fg_score and fg_score > 60 else "#d29922")

s1,s2,s3,s4,s5,s6,s7 = st.columns(7)
s1.metric("Macro Gate",      gate_val, delta=regime or None)
s2.metric("Fear & Greed",    str(int(fg_score)) if fg_score else "—", delta=fg_label)
spy_str = f"${spy_price*fx:,.0f}" if spy_price else "—"
spy_gap = f"{((spy_price-spy_sma)/spy_sma*100):+.1f}% vs 200SMA" if spy_price and spy_sma else None
s3.metric("SPY (AUD)",       spy_str, delta=spy_gap)
s4.metric("VIX",             f"{vix_val:.1f}" if vix_val else "—", delta="Elevated" if vix_val and vix_val>20 else "Normal")
fresh = sum(1 for m in all_module_mtimes if m and (time.time()-m)/3600 < 2)
s5.metric("KB Sources",      f"{fresh}/{len(KB_MODULES)} fresh")
s6.metric("Last Refresh",    freshness_label(last_refresh))
s7.metric("Active Cron Jobs","57")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABBED NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════
tab_signals, tab_watchlist, tab_portfolio, tab_market, tab_pipeline, tab_kb = st.tabs([
    "Signal Intelligence",
    "Watchlist",
    "Portfolio",
    "Market Data",
    "Pipeline",
    "Knowledge Base",
])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1 — SIGNAL INTELLIGENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_signals:
    # Global alerts
    alerts = signals.get("global_alerts", [])
    if alerts:
        for alert in alerts:
            col = "#f85149" if any(k in alert.upper() for k in ("GATE","MACRO","CRITICAL")) else "#d29922"
            st.markdown(
                f'<div style="background:#1c0f0f;border-left:3px solid {col};padding:10px 16px;'
                f'border-radius:4px;margin:4px 0;color:{col};font-size:13px">⚠ {alert}</div>',
                unsafe_allow_html=True,
            )

    ranked     = signals.get("ranked", [])
    tdata      = signals.get("tickers", {})
    src_cov    = signals.get("source_coverage", {})

    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown("##### Signal Rankings")
        if ranked and tdata:
            rows = []
            for i, ticker in enumerate(ranked):
                td = tdata.get(ticker, {})
                score = float(td.get("score", 0) or 0)
                rows.append({
                    "Rank":          i + 1,
                    "Ticker":        ticker,
                    "Company":       COMPANY_NAMES.get(ticker, ""),
                    "Sector":        SECTOR_MAP.get(ticker, ""),
                    "Tier":          f"T{TIER_MAP.get(ticker,3)}",
                    "Score":         round(score, 3),
                    "Conviction":    td.get("conviction", "—"),
                    "Recommendation":td.get("recommendation", "—"),
                    "Sources":       td.get("source_count", 0),
                    "Signals":       len(td.get("signals", [])),
                })
            df = pd.DataFrame(rows)

            def colour_rec(val):
                return f"color: {rec_colour(val)}"
            def colour_score(val):
                if val > 0.1:  return "color: #3fb950; font-weight: 600"
                if val < -0.1: return "color: #f85149; font-weight: 600"
                return "color: #d29922"

            st.dataframe(
                df.style.applymap(colour_rec, subset=["Recommendation"])
                        .applymap(colour_score, subset=["Score"]),
                use_container_width=True, hide_index=True,
            )

        st.markdown("##### Signal Detail — Top Tickers")
        for ticker in ranked[:6]:
            td     = tdata.get(ticker, {})
            sigs   = td.get("signals", [])
            score  = float(td.get("score", 0) or 0)
            score_pct = score_to_pct(score)
            score_col = "#3fb950" if score > 0.05 else ("#f85149" if score < -0.05 else "#d29922")
            rec       = td.get("recommendation","—")
            with st.expander(f"{ticker}  ·  {COMPANY_NAMES.get(ticker,'')}  ·  score {score:+.3f}  ·  {rec}"):
                for sig in sigs:
                    direction = sig.get("direction", 0)
                    dcol = "#3fb950" if direction > 0 else ("#f85149" if direction < 0 else "#8b949e")
                    dstr = "▲" if direction > 0 else ("▼" if direction < 0 else "—")
                    st.markdown(
                        f'<div style="display:flex;gap:12px;padding:4px 0;border-bottom:1px solid #21262d">'
                        f'<span style="color:#58a6ff;font-size:11px;min-width:100px">{sig.get("source","")}</span>'
                        f'<span style="color:{dcol};font-size:11px">{dstr} {sig.get("note","")}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    with col_r:
        # F&G gauge
        if fg_score is not None:
            fig_fg = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=fg_score,
                delta={"reference": 50, "valueformat": ".0f"},
                title={"text": "Fear & Greed Index", "font": {"color":"#8b949e","size":13}},
                number={"font": {"color":"#c9d1d9","size":36}},
                gauge={
                    "axis": {"range":[0,100], "tickcolor":"#8b949e", "tickfont":{"color":"#8b949e","size":10}},
                    "bar":  {"color":"#58a6ff", "thickness":0.25},
                    "bgcolor": "#161b22",
                    "bordercolor": "#30363d",
                    "steps": [
                        {"range":[0,25],   "color":"#2d1515"},
                        {"range":[25,45],  "color":"#2d2015"},
                        {"range":[45,55],  "color":"#21262d"},
                        {"range":[55,75],  "color":"#152d15"},
                        {"range":[75,100], "color":"#0f2d0f"},
                    ],
                    "threshold": {"line":{"color":"#ffffff","width":2}, "thickness":0.8, "value":fg_score},
                },
            ))
            fig_fg.update_layout(
                paper_bgcolor="#161b22", font_color="#c9d1d9",
                height=240, margin=dict(l=20,r=20,t=40,b=20),
            )
            st.plotly_chart(fig_fg, use_container_width=True)

        # Source coverage chart
        st.markdown("##### Source Coverage")
        if src_cov:
            active = {k: v for k, v in src_cov.items() if v > 0}
            if active:
                src_df = pd.DataFrame(
                    sorted(active.items(), key=lambda x: x[1], reverse=True),
                    columns=["Source", "Tickers"]
                )
                fig_src = px.bar(
                    src_df, x="Tickers", y="Source", orientation="h",
                    color="Tickers", color_continuous_scale=["#21262d","#1f6feb","#58a6ff"],
                )
                fig_src.update_layout(
                    paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                    font_color="#c9d1d9", height=280,
                    margin=dict(l=0,r=0,t=0,b=0),
                    showlegend=False, coloraxis_showscale=False,
                    xaxis=dict(gridcolor="#30363d", title=""),
                    yaxis=dict(gridcolor="#30363d", title="", tickfont={"size":10}),
                )
                st.plotly_chart(fig_src, use_container_width=True)

        # Conviction heatmap
        st.markdown("##### Conviction Map")
        if tdata:
            heat_tickers = [t for t in ranked]
            heat_sources = ["macro","fear_greed","insider","options_flow","reservoir","trendforce","news_cn","pypi","reddit","govt_contracts","kepco"]
            z = []
            for src in heat_sources:
                row = []
                for t in heat_tickers:
                    sig_for_src = next((s["direction"] for s in tdata.get(t,{}).get("signals",[]) if s.get("source")==src), 0)
                    row.append(sig_for_src)
                z.append(row)
            fig_heat = go.Figure(go.Heatmap(
                z=z, x=heat_tickers, y=heat_sources,
                colorscale=[[0,"#2d1515"],[0.5,"#21262d"],[1,"#152d15"]],
                zmid=0, zmin=-1, zmax=1,
                text=[[f"{v:+.1f}" if v!=0 else "" for v in row] for row in z],
                texttemplate="%{text}", textfont={"size":9,"color":"#c9d1d9"},
                showscale=False,
            ))
            fig_heat.update_layout(
                paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                font_color="#8b949e", height=300,
                margin=dict(l=0,r=0,t=0,b=0),
                xaxis=dict(tickfont={"size":10}),
                yaxis=dict(tickfont={"size":10}),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2 — WATCHLIST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_watchlist:
    wl_col, ctrl_col = st.columns([5, 1])
    with ctrl_col:
        view_mode = st.selectbox("View", ["Cards", "Table", "Compact List"], label_visibility="collapsed")
        tier_filter = st.multiselect("Tiers", [1, 2, 3], default=[1,2,3], label_visibility="collapsed",
                                     format_func=lambda x: f"Tier {x}")

    tickers_show = [t for t in TICKERS if TIER_MAP.get(t,3) in tier_filter]
    prices       = prices_alpaca or {}
    tdata        = signals.get("tickers", {})

    if view_mode == "Cards":
        cols_per_row = 3
        for i in range(0, len(tickers_show), cols_per_row):
            batch = tickers_show[i:i+cols_per_row]
            cols  = st.columns(cols_per_row)
            for col, ticker in zip(cols, batch):
                td        = tdata.get(ticker, {})
                score     = float(td.get("score", 0) or 0)
                rec       = td.get("recommendation","—")
                sigs      = [s.get("source","") for s in td.get("signals",[]) if s.get("source")][:5]
                tier      = TIER_MAP.get(ticker,3)
                price_usd = prices.get(ticker)
                price_str = f"${price_usd*fx:,.2f} AUD" if price_usd else "— AUD"
                score_pct = score_to_pct(score)
                score_col = "#3fb950" if score>0.05 else ("#f85149" if score<-0.05 else "#d29922")
                tier_col  = {1:"#58a6ff",2:"#d29922",3:"#8b949e"}.get(tier,"#8b949e")

                sig_tags  = "".join(
                    f'<span style="background:#21262d;color:#8b949e;font-size:9px;padding:2px 5px;border-radius:3px">{s}</span>'
                    for s in sigs
                )

                # Multi-link row
                links = (
                    f'<a href="{TICKER_LINKS["yahoo"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;text-decoration:none">Yahoo</a> · '
                    f'<a href="{TICKER_LINKS["finviz"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;text-decoration:none">Finviz</a> · '
                    f'<a href="{TICKER_LINKS["stockanalysis"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;text-decoration:none">Analysis</a> · '
                    f'<a href="{TICKER_LINKS["tipranks"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;text-decoration:none">TipRanks</a>'
                )

                col.markdown(f"""
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
    <a href="{TICKER_LINKS["yahoo"](ticker)}" target="_blank" style="color:#c9d1d9;font-weight:700;font-size:16px;text-decoration:none">{ticker}</a>
    <span style="background:#21262d;color:{tier_col};font-size:9px;padding:2px 7px;border-radius:3px;font-weight:700">T{tier}</span>
  </div>
  <div style="color:#8b949e;font-size:11px;margin-bottom:6px">{COMPANY_NAMES.get(ticker,"")} &nbsp;·&nbsp; {SECTOR_MAP.get(ticker,"")}</div>
  <div style="color:#c9d1d9;font-size:18px;font-weight:600;margin:6px 0">{price_str}</div>
  <div style="margin:8px 0;height:4px;background:#21262d;border-radius:2px">
    <div style="height:4px;background:{score_col};border-radius:2px;width:{score_pct}%"></div>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span style="color:#8b949e;font-size:10px">Signal: {score:+.3f}</span>
    <span style="color:{rec_colour(rec)};font-size:10px;font-weight:700">{rec}</span>
  </div>
  <div style="display:flex;gap:3px;flex-wrap:wrap;margin-bottom:8px">{sig_tags}</div>
  <div style="border-top:1px solid #30363d;padding-top:6px">{links}</div>
</div>""", unsafe_allow_html=True)

    elif view_mode == "Table":
        rows = []
        for ticker in tickers_show:
            td        = tdata.get(ticker, {})
            score     = float(td.get("score", 0) or 0)
            price_usd = prices.get(ticker)
            rows.append({
                "Ticker":    ticker,
                "Company":   COMPANY_NAMES.get(ticker,""),
                "Sector":    SECTOR_MAP.get(ticker,""),
                "Tier":      f"T{TIER_MAP.get(ticker,3)}",
                "Price AUD": f"${price_usd*fx:,.2f}" if price_usd else "—",
                "Score":     round(score,3),
                "Conviction":td.get("conviction","—"),
                "Rec":       td.get("recommendation","—"),
                "Sources":   td.get("source_count",0),
                "Yahoo":     TICKER_LINKS["yahoo"](ticker),
                "Finviz":    TICKER_LINKS["finviz"](ticker),
                "Analysis":  TICKER_LINKS["stockanalysis"](ticker),
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.applymap(rec_colour, subset=["Rec"])
                    .applymap(lambda v: f"color: {'#3fb950' if isinstance(v,float) and v>0.1 else '#f85149' if isinstance(v,float) and v<-0.1 else '#d29922'}", subset=["Score"]),
            use_container_width=True, hide_index=True,
        )

    else:  # Compact List
        header = (
            '<div style="display:grid;grid-template-columns:80px 160px 80px 90px 120px 120px 1fr;'
            'gap:8px;padding:6px 10px;background:#21262d;border-radius:6px;margin-bottom:4px;'
            'color:#58a6ff;font-size:10px;font-weight:700;letter-spacing:0.5px">'
            '<span>TICKER</span><span>COMPANY</span><span>TIER</span>'
            '<span>PRICE AUD</span><span>SCORE</span><span>REC</span><span>LINKS</span>'
            '</div>'
        )
        rows_html = header
        for ticker in tickers_show:
            td        = tdata.get(ticker,{})
            score     = float(td.get("score",0) or 0)
            price_usd = prices.get(ticker)
            pstr      = f"${price_usd*fx:,.2f}" if price_usd else "—"
            rec       = td.get("recommendation","—")
            sc        = "#3fb950" if score>0.05 else ("#f85149" if score<-0.05 else "#d29922")
            rc        = rec_colour(rec)
            tier_col  = {1:"#58a6ff",2:"#d29922",3:"#8b949e"}.get(TIER_MAP.get(ticker,3),"#8b949e")
            link_row  = (
                f'<a href="{TICKER_LINKS["yahoo"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;margin-right:6px;text-decoration:none">Yahoo</a>'
                f'<a href="{TICKER_LINKS["finviz"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;margin-right:6px;text-decoration:none">Finviz</a>'
                f'<a href="{TICKER_LINKS["stockanalysis"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;margin-right:6px;text-decoration:none">Analysis</a>'
                f'<a href="{TICKER_LINKS["unusualwhales"](ticker)}" target="_blank" style="color:#58a6ff;font-size:10px;text-decoration:none">Options</a>'
            )
            rows_html += (
                f'<div style="display:grid;grid-template-columns:80px 160px 80px 90px 120px 120px 1fr;'
                f'gap:8px;padding:7px 10px;border-bottom:1px solid #21262d;align-items:center">'
                f'<span style="color:#c9d1d9;font-weight:600;font-size:13px">{ticker}</span>'
                f'<span style="color:#8b949e;font-size:11px">{COMPANY_NAMES.get(ticker,"")}</span>'
                f'<span style="color:{tier_col};font-size:11px">T{TIER_MAP.get(ticker,3)}</span>'
                f'<span style="color:#c9d1d9;font-size:12px">{pstr}</span>'
                f'<span style="color:{sc};font-size:12px;font-weight:600">{score:+.3f}</span>'
                f'<span style="color:{rc};font-size:11px;font-weight:600">{rec}</span>'
                f'<span>{link_row}</span>'
                f'</div>'
            )
        st.markdown(f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px">{rows_html}</div>', unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3 — PORTFOLIO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_portfolio:
    STARTING_AUD = 10_000.0
    acct, positions = get_alpaca_account()

    if acct:
        equity_usd   = float(acct.get("equity", 0))
        cash_usd     = float(acct.get("cash", 0))
        equity_aud   = equity_usd * fx
        cash_aud     = cash_usd * fx
        pnl_aud      = equity_aud - STARTING_AUD
        pnl_pct      = (pnl_aud / STARTING_AUD) * 100
        deployed_aud = equity_aud - cash_aud
        deployed_pct = (deployed_aud / equity_aud * 100) if equity_aud else 0

        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("Portfolio Value",    f"${equity_aud:,.0f}", delta=f"{pnl_pct:+.2f}%")
        m2.metric("Cash",               f"${cash_aud:,.0f}")
        m3.metric("Deployed",           f"${deployed_aud:,.0f}", delta=f"{deployed_pct:.1f}%")
        m4.metric("P&L vs Benchmark",   f"${pnl_aud:+,.0f}", delta=f"{pnl_pct:+.2f}%")
        m5.metric("Open Positions",     str(len(positions)))

        # Portfolio donut chart
        fig_port = go.Figure(go.Pie(
            labels=["Cash", "Deployed"],
            values=[cash_aud, max(0, deployed_aud)],
            hole=0.65,
            marker_colors=["#21262d","#58a6ff"],
            textinfo="label+percent",
            textfont={"color":"#c9d1d9","size":12},
        ))
        fig_port.update_layout(
            paper_bgcolor="#161b22", font_color="#c9d1d9",
            height=250, margin=dict(l=0,r=0,t=20,b=0),
            showlegend=False,
            annotations=[{"text":f"${equity_aud:,.0f}","font":{"size":18,"color":"#c9d1d9"},"showarrow":False}],
        )
        p_col, h_col = st.columns([1,2])
        p_col.plotly_chart(fig_port, use_container_width=True)

        with h_col:
            macro_m = signals.get("macro", {})
            cash_rule = int(macro_m.get("cash_reserve", 0.8) * 100)
            max_dep   = int(macro_m.get("max_deployed", 0.2) * 100)
            st.markdown(f"""
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-top:8px">
  <div style="color:#8b949e;font-size:11px;font-weight:700;letter-spacing:0.5px;margin-bottom:10px">POSITION RULES</div>
  <div style="color:#c9d1d9;font-size:13px;margin:6px 0">Entry gates: Fundamental + Technical + Sentiment + Macro</div>
  <div style="color:#c9d1d9;font-size:13px;margin:6px 0">Stop-loss: <span style="color:#f85149">-5%</span> hard stop</div>
  <div style="color:#c9d1d9;font-size:13px;margin:6px 0">Take-profit 1: <span style="color:#3fb950">+8%</span> (50% exit)</div>
  <div style="color:#c9d1d9;font-size:13px;margin:6px 0">Take-profit 2: <span style="color:#3fb950">+15%</span> (full exit)</div>
  <div style="color:{'#f85149' if gate_val=='FAIL' else '#3fb950'};font-size:13px;margin:10px 0;font-weight:600">
    Macro Gate {gate_val} → Cash reserve: {cash_rule}% · Max deployed: {max_dep}%</div>
  <div style="color:#8b949e;font-size:11px">Model: claude-opus-4-6 (PREPARE) · claude-sonnet-4-6 (EXECUTE)</div>
</div>""", unsafe_allow_html=True)

    if positions:
        st.markdown("##### Open Positions")
        rows = []
        for p in positions:
            ticker = p.get("symbol","")
            qty    = float(p.get("qty",0))
            entry  = float(p.get("avg_entry_price",0))
            curr   = float(p.get("current_price",0))
            unreal = float(p.get("unrealized_pl",0))
            plpc   = float(p.get("unrealized_plpc",0)) * 100
            rows.append({
                "Ticker":     ticker,
                "Qty":        qty,
                "Entry AUD":  f"${entry*fx:,.2f}",
                "Current AUD":f"${curr*fx:,.2f}",
                "Market Val": f"${curr*qty*fx:,.0f}",
                "P&L AUD":    f"${unreal*fx:+,.0f}",
                "P&L %":      f"{plpc:+.2f}%",
                "Stop":       f"${entry*0.95*fx:,.2f}",
                "T1 +8%":     f"${entry*1.08*fx:,.2f}",
                "T2 +15%":    f"${entry*1.15*fx:,.2f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.markdown(
            f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;color:#8b949e;text-align:center">'
            f'Macro gate <span style="color:#f85149;font-weight:600">FAIL</span> — holding cash. No positions open.</div>',
            unsafe_allow_html=True,
        )

    # Trade history
    st.markdown("##### Trade History")
    th_path = TRADING_DIR / "TradingAgents" / "trade_history.json"
    if th_path.exists():
        try:
            trades = json.loads(th_path.read_text())
            if trades:
                rows = []
                for t in reversed(trades[-50:]):
                    rows.append({
                        "Date":      t.get("date",""),
                        "Ticker":    t.get("ticker",""),
                        "Action":    t.get("action",""),
                        "Qty":       t.get("qty",""),
                        "Price AUD": f"${float(t.get('price',0))*fx:.2f}" if t.get("price") else "—",
                        "P&L AUD":   f"${float(t.get('pnl',0))*fx:.0f}" if t.get("pnl") else "—",
                        "Reason":    t.get("reason","")[:60],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No closed trades — paper trial in progress.")
        except Exception as e:
            st.caption(f"Could not load: {e}")
    else:
        st.caption("No closed trades — paper trial in progress.")

    # Feedback loop
    st.markdown("##### Feedback Loop")
    fb_l, fb_m, fb_r = st.columns(3)
    dec_dir = FEEDBACK_DIR / "decisions"
    out_dir = FEEDBACK_DIR / "outcomes"
    cf_dir  = FEEDBACK_DIR / "counterfactuals"
    fb_l.metric("Decisions Logged",  str(len(list(dec_dir.glob("*.json")))) if dec_dir.exists() else "0")
    fb_m.metric("Outcomes Resolved", str(len(list(out_dir.glob("*.json")))) if out_dir.exists() else "0")
    fb_r.metric("Counterfactuals",   str(len(list(cf_dir.glob("*.json")))) if cf_dir.exists() else "0")

    acc_file = FEEDBACK_DIR / "accuracy_scores.json"
    if acc_file.exists():
        try:
            acc = json.loads(acc_file.read_text())
            rows = []
            for src, d in sorted(acc.items(), key=lambda x: -(x[1].get("hit_rate") or 0)):
                calls    = d.get("total_calls", 0)
                hit_rate = d.get("hit_rate")
                weight   = d.get("current_weight", d.get("default_weight","—"))
                locked   = calls < 5
                rows.append({
                    "Source":   src,
                    "Calls":    calls,
                    "Hit Rate": f"{hit_rate:.1%}" if hit_rate is not None else "—",
                    "Weight":   f"{weight:.3f}" if isinstance(weight,float) else str(weight),
                    "Status":   "🔒 locked" if locked else "● live",
                })
            if rows:
                with st.expander("Source Accuracy Scores"):
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except Exception:
            pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4 — MARKET DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_market:
    md_l, md_r = st.columns(2)

    # Options flow — P/C ratio chart
    with md_l:
        st.markdown("##### Options Flow — Put/Call Ratios")
        of_data, of_mtime = load_latest_kb("options_flow")
        if of_data and of_data.get("tickers"):
            of_tickers = of_data["tickers"]
            of_rows = []
            for sym, vals in of_tickers.items():
                if sym in TICKERS:
                    pcr = vals.get("put_call_ratio")
                    if pcr is not None:
                        of_rows.append({"Ticker": sym, "P/C Ratio": float(pcr)})
            if of_rows:
                of_df = pd.DataFrame(of_rows).sort_values("P/C Ratio", ascending=True)
                fig_of = px.bar(
                    of_df, x="P/C Ratio", y="Ticker", orientation="h",
                    color="P/C Ratio",
                    color_continuous_scale=[[0,"#3fb950"],[0.5,"#d29922"],[1,"#f85149"]],
                    color_continuous_midpoint=1.0,
                )
                fig_of.add_vline(x=1.0, line_color="#8b949e", line_dash="dash", line_width=1)
                fig_of.update_layout(
                    paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                    font_color="#c9d1d9", height=280,
                    margin=dict(l=0,r=0,t=0,b=0),
                    showlegend=False, coloraxis_showscale=False,
                    xaxis=dict(gridcolor="#30363d", title="P/C Ratio (>1 = bearish)"),
                    yaxis=dict(gridcolor="#30363d", title=""),
                )
                st.plotly_chart(fig_of, use_container_width=True)
            if of_data.get("alerts"):
                for a in of_data["alerts"][:5]:
                    st.markdown(f'<div style="color:#d29922;font-size:12px;padding:2px 0">⚡ {a}</div>', unsafe_allow_html=True)
        else:
            st.caption("No options flow data")

        # Short interest
        st.markdown("##### Short Interest")
        si_data, si_mtime = load_latest_kb("short_interest")
        if si_data and si_data.get("tickers"):
            si_rows = []
            for sym, vals in si_data["tickers"].items():
                if sym in TICKERS:
                    si_rows.append({
                        "Ticker":     sym,
                        "Short %Float": float(vals.get("short_pct_float",0)),
                        "Days to Cover":float(vals.get("short_ratio_days",0)),
                        "Shares Short": int(vals.get("shares_short",0)),
                    })
            if si_rows:
                si_df = pd.DataFrame(si_rows).sort_values("Short %Float", ascending=False)
                fig_si = px.bar(
                    si_df, x="Short %Float", y="Ticker", orientation="h",
                    color="Short %Float",
                    color_continuous_scale=[[0,"#21262d"],[0.5,"#d29922"],[1,"#f85149"]],
                )
                fig_si.update_layout(
                    paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                    font_color="#c9d1d9", height=260,
                    margin=dict(l=0,r=0,t=0,b=0),
                    showlegend=False, coloraxis_showscale=False,
                    xaxis=dict(gridcolor="#30363d", title="% of Float Short"),
                    yaxis=dict(gridcolor="#30363d", title=""),
                )
                st.plotly_chart(fig_si, use_container_width=True)
        else:
            st.caption("No short interest data")

    with md_r:
        # Insider cluster heatmap
        st.markdown("##### Insider Cluster Signals (7-day)")
        ins_data, _ = load_latest_kb("insider_trades")
        if ins_data and ins_data.get("clusters_7d"):
            clusters = ins_data["clusters_7d"]
            cluster_tickers = [t for t in TICKERS if t in clusters]
            if cluster_tickers:
                fig_ins = go.Figure(go.Bar(
                    x=[clusters[t] for t in cluster_tickers],
                    y=cluster_tickers,
                    orientation="h",
                    marker_color=["#3fb950" if clusters[t]>=3 else "#d29922" for t in cluster_tickers],
                    text=[f"{clusters[t]} filings" for t in cluster_tickers],
                    textposition="outside",
                    textfont={"color":"#c9d1d9","size":10},
                ))
                fig_ins.update_layout(
                    paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                    font_color="#c9d1d9", height=260,
                    margin=dict(l=0,r=0,t=0,b=0),
                    xaxis=dict(gridcolor="#30363d", title="Insider Buys (7d)"),
                    yaxis=dict(gridcolor="#30363d", title=""),
                )
                st.plotly_chart(fig_ins, use_container_width=True)
        else:
            st.caption("No insider cluster data")

        # LME metals + CFTC
        st.markdown("##### Commodities — LME & CFTC")
        lme_data, _ = load_latest_kb("lme_metals")
        cftc_data, _ = load_latest_kb("cftc_cot")
        metals_rows = []
        if lme_data and lme_data.get("metals"):
            for sym, vals in lme_data["metals"].items():
                name = {"HG=F":"Copper","GC=F":"Gold","SI=F":"Silver","PA=F":"Palladium"}.get(sym, sym)
                chg30 = vals.get("change_30d_pct")
                metals_rows.append({
                    "Metal":     name,
                    "Price USD": f"${vals.get('price',0):,.2f}" if vals.get("price") else "—",
                    "30d Chg":   f"{chg30:+.1f}%" if chg30 else "—",
                    "CFTC Net":  "",
                })
        if cftc_data and cftc_data.get("commodities"):
            for com, vals in cftc_data["commodities"].items():
                net  = vals.get("mm_net")
                dirn = vals.get("mm_net_direction","")
                col  = "#3fb950" if dirn=="LONG" else "#f85149"
                match_row = next((r for r in metals_rows if com.lower() in r["Metal"].lower()), None)
                if match_row:
                    match_row["CFTC Net"] = f"{'▲' if dirn=='LONG' else '▼'} {net:+,}" if net else "—"
        if metals_rows:
            metals_df = pd.DataFrame(metals_rows)
            st.dataframe(metals_df, use_container_width=True, hide_index=True)
        if lme_data and lme_data.get("alerts"):
            for a in lme_data["alerts"][:4]:
                col = "#3fb950" if "+" in a else "#f85149"
                st.markdown(f'<div style="color:{col};font-size:12px">● {a}</div>', unsafe_allow_html=True)

        # Macro indicators
        st.markdown("##### Macro Indicators")
        if macro_data and isinstance(macro_data, dict):
            ind = macro_data.get("indicators", {})
            macro_rows = []
            for sym, name in [("SPY","S&P 500"),("VIX","VIX"),("TLT","10yr Bond"),("DXY_proxy","DXY")]:
                vals = ind.get(sym, {})
                price = vals.get("price") or vals.get("current")
                macro_rows.append({
                    "Indicator": name,
                    "Price":     f"${price:,.2f}" if price else "—",
                    "Signal":    vals.get("signal","—") if isinstance(vals, dict) else "—",
                })
            if macro_rows:
                st.dataframe(pd.DataFrame(macro_rows), use_container_width=True, hide_index=True)

        # FERC grid demand
        st.markdown("##### EIA Grid Demand (WoW)")
        ferc_data, _ = load_latest_kb("ferc_queue")
        if ferc_data and ferc_data.get("regions"):
            ferc_rows = []
            for reg, vals in ferc_data["regions"].items():
                if isinstance(vals, dict):
                    wow = vals.get("wow_pct")
                    ferc_rows.append({
                        "Region": reg,
                        "WoW %":  f"{wow:+.1f}%" if wow is not None else "—",
                        "Demand": f"{vals.get('current_gw',0):.1f} GW" if vals.get("current_gw") else "—",
                        "Signal": "▲ Bullish" if wow and wow > 3 else ("▼ Bearish" if wow and wow < -3 else "Neutral"),
                    })
            if ferc_rows:
                st.dataframe(pd.DataFrame(ferc_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No grid data")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 5 — PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_pipeline:
    today = datetime.now().strftime("%Y-%m-%d")
    now_h = datetime.now().hour + datetime.now().minute / 60

    # Pipeline architecture diagram
    l1_mt = last_refresh
    l3_mt = l1_mt
    l4_mt = newest_mtime_in_dir(KB_DIR / "dart_filings")
    l5_mt = Path(f"/tmp/trading_prepare_{today}.log").stat().st_mtime if Path(f"/tmp/trading_prepare_{today}.log").exists() else None
    l6_mt = Path("/tmp/trading_execute.log").stat().st_mtime if Path("/tmp/trading_execute.log").exists() else None
    l7_mt = newest_mtime_in_dir(FEEDBACK_DIR / "decisions")
    l2_mt = newest_mtime_in_dir(KB_DIR / "sec_filings")

    st.markdown("##### Architecture")
    arrow = '<div style="color:#30363d;font-size:22px;flex-shrink:0;align-self:center">→</div>'
    pipe_html = f"""<div style="display:flex;align-items:stretch;gap:8px;padding:20px;
        background:#161b22;border-radius:8px;overflow-x:auto;margin:8px 0">
  {pipe_box("L1 · DATA", "44 KB modules", l1_mt, warn_h=4, crit_h=12)}
  {arrow}
  {pipe_box("L3 · AGGREGATE", "Signal scoring", l3_mt, warn_h=4, crit_h=12)}
  {arrow}
  {pipe_box("L4 · RAG", "Supabase pgvector", l4_mt, warn_h=2, crit_h=6)}
  {arrow}
  {pipe_box("L5 · PREPARE", "6pm AWST", l5_mt, warn_h=20, crit_h=26)}
  {arrow}
  {pipe_box("L6 · EXECUTE", "9:30pm open", l6_mt, warn_h=20, crit_h=26)}
  {arrow}
  {pipe_box("L7 · FEEDBACK", "Nightly scorer", l7_mt, warn_h=24, crit_h=48)}
  <div style="margin-left:16px;border-left:1px solid #30363d;padding-left:16px;display:flex;align-items:center">
    {pipe_box("L2 · EDGE", "SEC 8-K 5-min", l2_mt, warn_h=1, crit_h=3)}
  </div>
</div>"""
    st.markdown(pipe_html, unsafe_allow_html=True)

    # Today's timeline
    st.markdown("##### Today's Session")
    def tl_step(tstr, name, status, detail=""):
        cols = {"done":"#3fb950","running":"#58a6ff","missed":"#f85149","pending":"#6e7681"}
        icons= {"done":"✓","running":"⟳","missed":"✗","pending":"○"}
        c, i = cols.get(status,"#6e7681"), icons.get(status,"○")
        return (f'<div style="text-align:center;min-width:110px;flex-shrink:0">'
                f'<div style="color:{c};font-size:20px">{i}</div>'
                f'<div style="color:#58a6ff;font-size:10px;font-weight:700">{tstr}</div>'
                f'<div style="color:#c9d1d9;font-size:11px;margin:2px 0">{name}</div>'
                f'<div style="color:#8b949e;font-size:10px">{detail}</div></div>')
    def tl_line(done=False):
        c = "#3fb950" if done else "#30363d"
        return f'<div style="flex:1;height:2px;background:{c};align-self:center;margin-bottom:18px"></div>'

    kb_done  = last_refresh and (time.time()-last_refresh) < 7200
    prep_done= l5_mt is not None
    brief_done= Path(f"/tmp/analysis_status_{today}.txt").exists()
    exec_done= l6_mt is not None
    mid_done = now_h > 23.5
    aft_done = now_h > 4.5

    tl = f"""<div style="display:flex;align-items:center;padding:20px;background:#161b22;border-radius:8px;overflow-x:auto;margin:8px 0">
  {tl_step("5:00pm","KB Refresh","done" if kb_done else "pending")}
  {tl_line(kb_done and prep_done)}
  {tl_step("6:00pm","PREPARE","done" if prep_done else "pending","TradingAgents")}
  {tl_line(prep_done and brief_done)}
  {tl_step("9:00pm","Brief","done" if brief_done else "pending","Pre-trade review")}
  {tl_line(brief_done and exec_done)}
  {tl_step("9:30pm","EXECUTE","done" if exec_done else "pending","Market open")}
  {tl_line(exec_done and mid_done)}
  {tl_step("11:30pm","Midday","done" if mid_done else "pending","Position check")}
  {tl_line(mid_done and aft_done)}
  {tl_step("4:30am","After-hours","done" if aft_done else "pending","Earnings review")}
</div>"""
    st.markdown(tl, unsafe_allow_html=True)

    # Cron health summary
    st.markdown("##### Cron Health")
    st.markdown(
        '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;color:#8b949e;font-size:13px">'
        '57 active cron jobs · Use <code>openclaw cron list</code> in terminal for full status · '
        f'System monitors: health_monitor.py + trading_monitor.py (pure Python, no LLM)</div>',
        unsafe_allow_html=True,
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 6 — KNOWLEDGE BASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_kb:
    # Summary stats
    fresh_count = sum(1 for m in all_module_mtimes if m and (time.time()-m)/3600 < 2)
    stale_count = sum(1 for m in all_module_mtimes if m and 2 <= (time.time()-m)/3600 < 24)
    old_count   = sum(1 for m in all_module_mtimes if m and (time.time()-m)/3600 >= 24)
    miss_count  = sum(1 for m in all_module_mtimes if not m)

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Fresh (<2h)",  str(fresh_count))
    k2.metric("Stale (<24h)", str(stale_count))
    k3.metric("Old (>24h)",   str(old_count))
    k4.metric("Missing",      str(miss_count))

    # Freshness timeline chart
    plot_rows = []
    for (mod_name, label, provider, url, icon), mt in zip(KB_MODULES, all_module_mtimes):
        age_h = (time.time()-mt)/3600 if mt else 999
        col   = "#3fb950" if age_h < 2 else ("#d29922" if age_h < 24 else "#f85149" if age_h < 999 else "#6e7681")
        plot_rows.append({"Module": f"{icon} {mod_name}", "Age (h)": min(age_h,48), "Colour": col})

    plot_df = pd.DataFrame(plot_rows).sort_values("Age (h)")
    fig_kb = px.bar(
        plot_df, x="Age (h)", y="Module", orientation="h",
        color="Colour", color_discrete_map="identity",
    )
    fig_kb.add_vline(x=2, line_color="#3fb950", line_dash="dash", line_width=1, annotation_text="2h", annotation_font_color="#3fb950")
    fig_kb.add_vline(x=24, line_color="#d29922", line_dash="dash", line_width=1, annotation_text="24h", annotation_font_color="#d29922")
    fig_kb.update_layout(
        paper_bgcolor="#161b22", plot_bgcolor="#161b22",
        font_color="#c9d1d9", height=900,
        margin=dict(l=0,r=40,t=10,b=0),
        showlegend=False,
        xaxis=dict(gridcolor="#30363d", title="Age in hours (capped at 48h)"),
        yaxis=dict(gridcolor="#30363d", title="", tickfont={"size":9}),
    )
    st.plotly_chart(fig_kb, use_container_width=True)

    # Full detail table
    st.markdown("##### Module Details")
    kb_rows = []
    for (mod_name, label, provider, url, icon), mt in zip(KB_MODULES, all_module_mtimes):
        d = KB_DIR / mod_name
        files = sorted(d.glob("*.json")) if d.exists() else []
        age_h = round((time.time()-mt)/3600, 1) if mt else None
        status = "fresh" if age_h and age_h < 2 else ("stale" if age_h and age_h < 24 else ("old" if age_h else "missing"))
        status_col = {"fresh":"#3fb950","stale":"#d29922","old":"#f85149","missing":"#6e7681"}[status]

        # Peek at latest data for summary
        summary = "—"
        if files:
            try:
                ld = json.loads(files[-1].read_text())
                if isinstance(ld, dict):
                    for k in ("regime","alert_count","total_filings","papers_found","articles_found","total_relevant","notes"):
                        if k in ld:
                            summary = f"{k}: {ld[k]}"
                            break
                    if summary == "—":
                        first_key = next(iter(ld), None)
                        if first_key:
                            summary = f"{len(ld)} keys"
            except Exception:
                pass

        kb_rows.append({
            "": f'<span style="color:{status_col}">●</span>',
            "Module":    f'{icon} {mod_name}',
            "Label":     label,
            "Provider":  f'<a href="{url}" target="_blank" style="color:#58a6ff;font-size:11px;text-decoration:none">{provider} ↗</a>',
            "Status":    status,
            "Age (h)":   f"{age_h:.1f}h" if age_h else "never",
            "Files":     len(files),
            "Last File": files[-1].name if files else "—",
            "Data":      summary,
        })

    # Render as HTML table
    header_cells = ["","Module","Label","Provider","Status","Age","Files","Last File","Data"]
    header_html = "".join(f'<th style="background:#21262d;color:#58a6ff;font-size:10px;padding:6px 8px;text-align:left;white-space:nowrap">{h}</th>' for h in header_cells)

    rows_html = ""
    for r in kb_rows:
        sc = {"fresh":"#3fb950","stale":"#d29922","old":"#f85149","missing":"#6e7681"}.get(r["Status"],"#6e7681")
        cells = [
            r[""],
            f'<span style="color:#c9d1d9;font-size:11px;font-weight:500">{r["Module"]}</span>',
            f'<span style="color:#8b949e;font-size:11px">{r["Label"]}</span>',
            r["Provider"],
            f'<span style="color:{sc};font-size:11px">{r["Status"]}</span>',
            f'<span style="color:#8b949e;font-size:11px">{r["Age (h)"]}</span>',
            f'<span style="color:#8b949e;font-size:11px">{r["Files"]}</span>',
            f'<span style="color:#6e7681;font-size:10px">{r["Last File"]}</span>',
            f'<span style="color:#8b949e;font-size:10px">{r["Data"]}</span>',
        ]
        rows_html += "<tr>" + "".join(f'<td style="padding:6px 8px;border-bottom:1px solid #21262d">{c}</td>' for c in cells) + "</tr>"

    st.markdown(
        f'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">'
        f'<thead><tr>{header_html}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="color:#6e7681;font-size:10px;text-align:center;margin-top:20px;'
    f'padding-top:8px;border-top:1px solid #30363d">'
    f'Larsen Ventures Trading Intelligence &nbsp;·&nbsp; '
    f'<a href="https://trading.larsenfamily.com.au" style="color:#58a6ff">trading.larsenfamily.com.au</a>'
    f' &nbsp;·&nbsp; '
    f'<a href="https://alpaca.markets/paper" style="color:#58a6ff">Alpaca Paper</a>'
    f' &nbsp;·&nbsp; '
    f'FX 1 USD = {fx:.4f} AUD &nbsp;·&nbsp; {datetime.now().strftime("%H:%M:%S")}'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Auto-refresh ──────────────────────────────────────────────────────────────
time.sleep(60)
st.rerun()
