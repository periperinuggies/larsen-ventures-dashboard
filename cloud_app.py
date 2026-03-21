"""
Larsen Ventures — Trading Intelligence Dashboard (Cloud Edition)
================================================================
Deployed on Streamlit Community Cloud.
All data sourced from APIs and the committed kb_summary.json.
No local file system dependencies.

Tabs:
  1. Trading Intelligence  — macro, portfolio, signals, watchlist, staged decisions
  2. Ticker Display        — office wall ticker (reads ticker_config.json from repo)
"""

import json, time, os
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import requests

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Larsen Ventures",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Secrets (Streamlit Cloud injects via st.secrets) ─────────────────────────
def get_secret(key, fallback=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, fallback)

FINNHUB_KEY   = get_secret("FINNHUB_API_KEY")
ALPACA_KEY    = get_secret("ALPACA_API_KEY")
ALPACA_SECRET = get_secret("ALPACA_SECRET_KEY")
ALPACA_BASE   = "https://paper-api.alpaca.markets"

HERE = Path(__file__).parent

# ── Load static config files from repo ───────────────────────────────────────
def load_json(path, fallback=None):
    p = HERE / path
    if p.exists():
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    return fallback or {}

kb          = load_json("kb_summary.json")
ticker_cfg  = load_json("ticker_config.json")
TICKERS_DISPLAY = ticker_cfg.get("tickers", [])
DISPLAY_NAME    = ticker_cfg.get("display_name", "Larsen Ventures")

# Trading watchlist (hardcoded — matches paper_trader.py)
TRADING_WATCHLIST = [
    "NVDA","MSFT","AVGO","CRWD","META","GOOGL","AMD",
    "PANW","AMAT","LRCX","ARM","AMZN","ZS","SNOW",
    "LLY","NVO","KLAC","MDB","S",
]
TIERS = {
    "NVDA":"T1","MSFT":"T1","AVGO":"T1","CRWD":"T1","META":"T1","GOOGL":"T1",
    "AMD":"T2","PANW":"T2","AMAT":"T2","LRCX":"T2","ARM":"T2","AMZN":"T2",
    "ZS":"T3","SNOW":"T3","LLY":"T2","NVO":"T2","KLAC":"T2","MDB":"T3","S":"T3",
}

# ── API helpers ───────────────────────────────────────────────────────────────
def alpaca_get(path):
    if not ALPACA_KEY:
        return {}
    try:
        r = requests.get(
            f"{ALPACA_BASE}{path}",
            headers={"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET},
            timeout=8,
        )
        return r.json()
    except Exception:
        return {}

@st.cache_data(ttl=60)
def fetch_quotes_finnhub(tickers: tuple) -> dict:
    quotes = {}
    for t in tickers:
        if not FINNHUB_KEY:
            break
        try:
            r = requests.get(
                f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_KEY}",
                timeout=5,
            )
            d = r.json()
            if d.get("c"):
                quotes[t] = d
        except Exception:
            pass
        time.sleep(0.05)
    return quotes

@st.cache_data(ttl=60)
def fetch_quotes_yfinance(tickers: tuple) -> dict:
    try:
        import yfinance as yf
        data = yf.download(list(tickers), period="2d", progress=False, auto_adjust=True)
        quotes = {}
        close = data.get("Close", data)
        for sym in tickers:
            try:
                prices = close[sym].dropna() if sym in close.columns else close.dropna()
                if len(prices) >= 2:
                    c, pc = float(prices.iloc[-1]), float(prices.iloc[-2])
                    quotes[sym] = {"c": c, "pc": pc, "dp": (c-pc)/pc*100}
                elif len(prices) == 1:
                    c = float(prices.iloc[-1])
                    quotes[sym] = {"c": c, "pc": c, "dp": 0}
            except Exception:
                pass
        return quotes
    except Exception:
        return {}

def get_quotes(tickers):
    us  = tuple(t for t in tickers if not t.endswith(".AX"))
    asx = tuple(t for t in tickers if t.endswith(".AX"))
    out = {}
    if us:  out.update(fetch_quotes_finnhub(us))
    if asx: out.update(fetch_quotes_yfinance(asx))
    return out

def pct_str(v):
    if v is None: return "—"
    return f"+{float(v):.2f}%" if float(v) >= 0 else f"{float(v):.2f}%"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container{padding-top:.5rem;padding-bottom:.5rem}
  div[data-testid="metric-container"]{background:#1a1a2e;border-radius:8px;padding:10px;border:1px solid #16213e}
  h2{font-size:1.05rem!important;border-bottom:1px solid #ffffff22;padding-bottom:3px;margin-top:1rem!important}
  .regime-fail{background:#2d0000;border:1px solid #ff4b4b;border-radius:8px;padding:6px 14px;color:#ff4b4b;font-weight:bold;display:inline-block}
  .regime-pass{background:#002d10;border:1px solid #00d26a;border-radius:8px;padding:6px 14px;color:#00d26a;font-weight:bold;display:inline-block}
  .pill{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:bold;margin:2px}
  .pill-bull{background:#00d26a22;color:#00d26a;border:1px solid #00d26a55}
  .pill-bear{background:#ff4b4b22;color:#ff4b4b;border:1px solid #ff4b4b55}
  .pill-neut{background:#ffffff11;color:#aaa;border:1px solid #ffffff22}
  .ticker-wrap{overflow:hidden;background:#0a0a14;border:1px solid #1a1a2e;border-radius:8px;padding:10px 0;margin-bottom:8px}
  .ticker-scroll{display:flex;gap:0;white-space:nowrap;animation:scroll-left 60s linear infinite}
  .ticker-scroll:hover{animation-play-state:paused}
  @keyframes scroll-left{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
  .tick-item{display:inline-flex;flex-direction:column;align-items:flex-start;padding:4px 24px;border-right:1px solid #1a1a2e;min-width:120px}
  .tick-sym{font-size:14px;font-weight:700;color:#fff;letter-spacing:.5px}
  .tick-price{font-size:13px;color:#ccc}
  .tick-up{font-size:12px;color:#00d26a;font-weight:600}
  .tick-dn{font-size:12px;color:#ff4b4b;font-weight:600}
  .tick-neu{font-size:12px;color:#888}
  .grid-card{background:#111120;border:1px solid #1e1e35;border-radius:10px;padding:14px 16px;text-align:center;margin-bottom:8px}
  .gc-sym{font-size:18px;font-weight:800;color:#fff}
  .gc-label{font-size:11px;color:#888;margin-top:2px}
  .gc-price{font-size:22px;font-weight:700;margin-top:6px}
  .gc-chg{font-size:14px;font-weight:600;margin-top:2px}
  .gc-up{color:#00d26a}.gc-dn{color:#ff4b4b}.gc-neu{color:#888}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
ct, cts = st.columns([5,2])
with ct:  st.markdown("# 🤖  Larsen Ventures — Trading Intelligence")
with cts: st.markdown(f"<p style='color:#555;font-size:12px;margin-top:22px'>Auto-refresh 60s · {datetime.now().strftime('%d %b %Y %H:%M')} AWST</p>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Trading Intelligence", "📺  Ticker Display"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TRADING INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── Macro + Portfolio ──────────────────────────────────────────────────────
    st.markdown("---")
    macro   = kb.get("macro", {})
    account = alpaca_get("/v2/account")
    positions = alpaca_get("/v2/positions") or []
    if isinstance(positions, dict): positions = []

    col_m, col_p = st.columns([1, 2])

    with col_m:
        st.markdown("## Macro Regime")
        gate   = macro.get("gate", False)
        regime = macro.get("regime", "UNKNOWN")
        spy    = macro.get("spy")
        sma200 = macro.get("sma200")
        vix    = macro.get("vix")
        hy     = macro.get("hy_spread")
        fed    = macro.get("fed")
        yc     = macro.get("yc")
        updated= kb.get("_updated", "")

        st.markdown(f"<div class='{'regime-pass' if gate else 'regime-fail'}'>{'GATE: PASS — Trading Enabled' if gate else 'GATE: FAIL — Holding Cash'}</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-top:8px'><b>Regime:</b> <code>{regime}</code><br><span style='color:#555;font-size:11px'>KB updated: {updated[:16]}</span></p>", unsafe_allow_html=True)

        if spy and sma200:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=float(spy),
                delta={"reference": float(sma200), "valueformat": ".2f"},
                title={"text": "SPY vs 200 SMA", "font": {"size": 12}},
                gauge={
                    "axis": {"range": [float(sma200)*.92, float(sma200)*1.08]},
                    "bar": {"color": "#00d26a" if gate else "#ff4b4b"},
                    "threshold": {"line": {"color": "white", "width": 2}, "value": float(sma200)},
                    "bgcolor": "#1a1a2e",
                },
                number={"valueformat": ".2f", "prefix": "$"},
            ))
            fig.update_layout(height=190, margin=dict(l=5,r=5,t=25,b=5), paper_bgcolor="#0e0e1a", font_color="white")
            st.plotly_chart(fig, use_container_width=True)

        m1, m2 = st.columns(2)
        m1.metric("VIX",         f"{float(vix):.1f}"  if vix  else "—")
        m1.metric("Fed Funds",   f"{float(fed):.2f}%" if fed  else "—")
        m2.metric("HY Spread",   f"{float(hy):.2f}%"  if hy   else "—")
        m2.metric("Yield Curve", f"{float(yc):+.2f}%" if yc   else "—")

    with col_p:
        st.markdown("## Portfolio")
        if account and not account.get("code"):
            equity   = float(account.get("equity", 0))
            cash     = float(account.get("cash", 0))
            p_change = float(account.get("change_today", 0) or 0)
            deployed = equity - cash
            BUDGET   = 6300
            p1,p2,p3,p4 = st.columns(4)
            p1.metric("Equity",    f"${equity:,.0f}",   delta=f"${p_change:+,.0f}" if p_change else None)
            p2.metric("Cash",      f"${cash:,.0f}")
            p3.metric("Deployed",  f"${deployed:,.0f}", delta=f"{deployed/equity*100:.0f}%" if equity else None)
            p4.metric("Positions", str(len(positions)))
            st.markdown("**Trial budget** ($6,300 USD cap)")
            bp = min(deployed / BUDGET, 1.0) if BUDGET else 0
            st.progress(bp, text=f"${min(deployed,BUDGET):,.0f} / ${BUDGET:,} ({bp*100:.0f}%)")
        else:
            st.warning("Alpaca API unavailable — check secrets config")

        if positions:
            import pandas as pd
            rows = []
            for p in positions:
                pnl_pct = float(p.get("unrealized_plpc", 0)) * 100
                rows.append({
                    "Ticker": p.get("symbol",""),
                    "Qty":    int(float(p.get("qty",0))),
                    "Entry":  f"${float(p.get('avg_entry_price',0)):.2f}",
                    "Now":    f"${float(p.get('current_price',0)):.2f}",
                    "P&L":    f"${float(p.get('unrealized_pl',0)):+.2f}",
                    "P&L %":  pct_str(pnl_pct),
                    "Value":  f"${float(p.get('market_value',0)):,.0f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No open positions — holding cash")

    st.markdown("---")

    # ── What Chappie Is Learning (from kb_summary.json) ───────────────────────
    st.markdown("## What Chappie Is Learning")
    l1,l2,l3,l4 = st.columns(4)

    with l1:
        fg = kb.get("fear_greed", {})
        fg_val = fg.get("value")
        fg_lbl = fg.get("label", "")
        st.markdown("### Sentiment")
        if fg_val is not None:
            fg_int = int(fg_val)
            clr = ("#ff4b4b" if fg_int<25 else "#ffaa00" if fg_int<45
                   else "#aaa" if fg_int<55 else "#88dd88" if fg_int<75 else "#00d26a")
            fig_fg = go.Figure(go.Indicator(
                mode="gauge+number",
                value=fg_int,
                title={"text": f"Fear & Greed<br><span style='font-size:10px'>{fg_lbl}</span>", "font":{"size":11}},
                gauge={"axis":{"range":[0,100]},"bar":{"color":clr},
                       "steps":[{"range":[0,25],"color":"#2d0000"},{"range":[25,45],"color":"#2d1500"},
                                 {"range":[45,55],"color":"#1a1a1a"},{"range":[55,75],"color":"#002010"},
                                 {"range":[75,100],"color":"#001a08"}],"bgcolor":"#1a1a2e"},
            ))
            fig_fg.update_layout(height=175,margin=dict(l=5,r=5,t=30,b=5),paper_bgcolor="#0e0e1a",font_color="white")
            st.plotly_chart(fig_fg, use_container_width=True)
        for ticker, sig in list(kb.get("reddit_signals", {}).items())[:5]:
            pill = "pill-bull" if "BUY" in sig or "BULLISH" in sig else "pill-bear"
            st.markdown(f"<span class='pill {pill}'>{ticker} {sig.replace('_',' ')}</span>", unsafe_allow_html=True)

    with l2:
        clusters = kb.get("insider_clusters", {})
        st.markdown("### Insider Clusters")
        if clusters:
            for ticker, info in sorted(clusters.items(), key=lambda x: -(x[1].get("count") or 0))[:6]:
                trend = info.get("trend","mixed")
                pill  = "pill-bull" if trend=="buy_heavy" else "pill-bear" if trend=="sell_heavy" else "pill-neut"
                st.markdown(f"<span class='pill {pill}'>{ticker} {info.get('count',0)}x {trend.replace('_',' ')}</span>", unsafe_allow_html=True)
        else:
            st.caption("No clusters detected")

    with l3:
        large = kb.get("large_contracts", {})
        st.markdown("### Govt Contracts")
        if large:
            for ticker, info in large.items():
                st.markdown(f"<span class='pill pill-bull'>{ticker} ${info['amount_m']:.0f}M</span>", unsafe_allow_html=True)
                st.caption(info.get("agency","")[:40])
        else:
            st.caption("No large awards (>$50M) this month")

    with l4:
        urgent = kb.get("urgent_8k", [])
        st.markdown("### 8-K Alerts")
        if urgent:
            st.markdown(f"🔴 **{len(urgent)} urgent**")
            for f in urgent[:4]:
                items = ", ".join(f.get("items", []))
                st.markdown(f"<span class='pill pill-bear'>{f['ticker']} {items}</span>", unsafe_allow_html=True)
        else:
            st.caption("No urgent 8-K filings")
        soon = kb.get("earnings_soon", {})
        if soon:
            st.markdown("### Earnings Soon ⚠️")
            for ticker, v in soon.items():
                st.markdown(f"<span class='pill pill-bear'>{ticker} in {v.get('days_until','?')}d</span>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Live Watchlist ─────────────────────────────────────────────────────────
    st.markdown("## Live Trading Watchlist (NASDAQ)")
    with st.spinner("Fetching prices..."):
        tq = get_quotes(tuple(TRADING_WATCHLIST))
    cols = st.columns(5)
    for i, ticker in enumerate(TRADING_WATCHLIST):
        q = tq.get(ticker, {})
        price = q.get("c")
        chg   = q.get("dp")
        cols[i%5].metric(
            f"{ticker} [{TIERS.get(ticker,'?')}]",
            f"${price:.2f}" if price else "—",
            delta=pct_str(chg) if price else None,
            delta_color="normal" if chg and chg>=0 else "inverse",
        )

    st.markdown("<p style='color:#333;font-size:11px;text-align:center;margin-top:2rem'>Larsen Ventures · Paper trial 21 Mar – 18 Apr 2026 · Built by Chappie 🤖</p>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — TICKER DISPLAY (office wall)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(f"""
    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px'>
      <span style='font-size:22px;font-weight:800;color:#fff;letter-spacing:1px'>{DISPLAY_NAME.upper()}</span>
      <span style='font-size:12px;color:#555'>{datetime.now().strftime('%A %d %b %Y  %H:%M')} AWST</span>
    </div>""", unsafe_allow_html=True)

    if not TICKERS_DISPLAY:
        st.warning("No tickers in ticker_config.json")
    else:
        syms = tuple(t["symbol"] for t in TICKERS_DISPLAY)
        with st.spinner("Loading prices..."):
            quotes = get_quotes(syms)

        # Scrolling tape
        items = []
        for t in TICKERS_DISPLAY:
            sym   = t["symbol"]
            label = t.get("label", sym.replace(".AX",""))
            q     = quotes.get(sym, {})
            price = q.get("c")
            chg   = q.get("dp") or ((q["c"]-q["pc"])/q["pc"]*100 if q.get("c") and q.get("pc") and q["pc"]>0 else None)
            price_s = (f"A${price:,.2f}" if sym.endswith(".AX") else f"${price:,.2f}") if price else "—"
            if chg is None:   chg_cls, chg_s = "tick-neu", "—"
            elif chg >= 0:    chg_cls, chg_s = "tick-up",  f"▲ +{chg:.2f}%"
            else:             chg_cls, chg_s = "tick-dn",  f"▼ {chg:.2f}%"
            items.append(f"<div class='tick-item'><span class='tick-sym'>{label}</span><span class='tick-price'>{price_s}</span><span class='{chg_cls}'>{chg_s}</span></div>")
        content = "".join(items)
        st.markdown(f"<div class='ticker-wrap'><div class='ticker-scroll'>{content}{content}</div></div>", unsafe_allow_html=True)

        # Grid grouped by sector
        groups = {}
        for t in TICKERS_DISPLAY:
            groups.setdefault(t.get("group","Other"), []).append(t)

        for grp, gtickers in groups.items():
            st.markdown(f"<p style='color:#444;font-size:11px;font-weight:600;letter-spacing:1px;margin:12px 0 4px'>{grp.upper()}</p>", unsafe_allow_html=True)
            gcols = st.columns(min(len(gtickers), 6))
            for i, t in enumerate(gtickers):
                sym   = t["symbol"]
                label = t.get("label", sym.replace(".AX",""))
                q     = quotes.get(sym, {})
                price = q.get("c")
                chg   = q.get("dp") or ((q["c"]-q["pc"])/q["pc"]*100 if q.get("c") and q.get("pc") and q["pc"]>0 else None)
                with gcols[i % min(len(gtickers),6)]:
                    if price:
                        clr   = "gc-up" if (chg or 0)>=0 else "gc-dn"
                        arrow = "▲" if (chg or 0)>=0 else "▼"
                        ccy   = "A$" if sym.endswith(".AX") else "$"
                        chg_s = f"{arrow} {abs(chg):.2f}%" if chg is not None else "—"
                        st.markdown(f"<div class='grid-card'><div class='gc-sym'>{sym.replace('.AX','')}</div><div class='gc-label'>{label}</div><div class='gc-price {clr}'>{ccy}{price:,.2f}</div><div class='gc-chg {clr}'>{chg_s}</div></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='grid-card'><div class='gc-sym'>{sym.replace('.AX','')}</div><div class='gc-label'>{label}</div><div class='gc-price gc-neu'>—</div><div class='gc-chg gc-neu'>No data</div></div>", unsafe_allow_html=True)

        st.markdown("<p style='color:#333;font-size:11px;text-align:center;margin-top:1rem'>Edit ticker_config.json in the GitHub repo to add/remove stocks</p>", unsafe_allow_html=True)
