"""
Larsen Ventures — Trading Intelligence Dashboard
=================================================
Two tabs:
  1. Trading Intelligence — full agent monitor (what Chappie is learning/thinking/doing)
  2. Ticker Display     — clean live ticker for the office wall

Ticker config loaded from Dropbox:
  ~/Dropbox/Chappie Share/ticker_config.json
  Edit that file to change what appears. Updates within 60 seconds.
"""

import os, json, glob, time
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

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE         = Path(__file__).parent.parent
KB           = BASE / "knowledge_base"
TRADER       = BASE / "TradingAgents"
ENV          = TRADER / ".env"
DROPBOX_CFG  = Path.home() / "Dropbox" / "Chappie Share" / "ticker_config.json"
BETFAIR_DIR  = BASE / "betfair"
BETFAIR_LEDGER = BETFAIR_DIR / "paper_ledger.json"

def load_env():
    env = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

ENV_VARS      = load_env()
FINNHUB_KEY   = ENV_VARS.get("FINNHUB_API_KEY", "")
ALPACA_KEY    = ENV_VARS.get("ALPACA_API_KEY", "")
ALPACA_SECRET = ENV_VARS.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE   = "https://paper-api.alpaca.markets"

# ── Load trading watchlist ────────────────────────────────────────────────────
WATCHLIST_PATH = BASE / "watchlist.json"
with open(WATCHLIST_PATH) as f:
    _wl = json.load(f)
TRADING_WATCHLIST = _wl["watchlist_flat"]
TIERS = {}
for t, tickers in _wl.get("tiers", {}).items():
    for ticker in tickers:
        TIERS[ticker] = t

# ── Load Dropbox ticker config ────────────────────────────────────────────────
def load_ticker_config():
    if DROPBOX_CFG.exists():
        try:
            with open(DROPBOX_CFG) as f:
                return json.load(f)
        except Exception:
            pass
    return {"display_name": "Larsen Ventures", "tickers": []}

# ── API helpers ───────────────────────────────────────────────────────────────
def alpaca_get(path):
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
    """Fetch live quotes from Finnhub. 60s cache."""
    quotes = {}
    for t in tickers:
        if not FINNHUB_KEY:
            break
        try:
            r = requests.get(
                f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_KEY}",
                timeout=5,
            )
            data = r.json()
            if data.get("c"):
                quotes[t] = data
        except Exception:
            pass
        time.sleep(0.05)
    return quotes

@st.cache_data(ttl=60)
def fetch_quotes_yfinance(tickers: tuple) -> dict:
    """Fallback: yfinance for ASX and any non-Finnhub tickers."""
    try:
        import yfinance as yf
        symbols = list(tickers)
        data = yf.download(symbols, period="2d", progress=False, auto_adjust=True)
        quotes = {}
        if "Close" in data.columns:
            for sym in symbols:
                try:
                    prices = data["Close"][sym].dropna()
                    if len(prices) >= 2:
                        c = float(prices.iloc[-1])
                        pc = float(prices.iloc[-2])
                        quotes[sym] = {"c": c, "pc": pc, "dp": (c - pc) / pc * 100}
                    elif len(prices) == 1:
                        c = float(prices.iloc[-1])
                        quotes[sym] = {"c": c, "pc": c, "dp": 0}
                except Exception:
                    pass
        return quotes
    except Exception:
        return {}

def get_all_quotes(tickers):
    """Get quotes — Finnhub for US tickers, yfinance for ASX (.AX) tickers."""
    us_tickers  = tuple(t for t in tickers if not t.endswith(".AX"))
    asx_tickers = tuple(t for t in tickers if t.endswith(".AX"))
    quotes = {}
    if us_tickers:
        quotes.update(fetch_quotes_finnhub(us_tickers))
    if asx_tickers:
        quotes.update(fetch_quotes_yfinance(asx_tickers))
    return quotes

def latest_kb(subdir):
    files = sorted(glob.glob(str(KB / subdir / "*.json")))
    if not files:
        return {}
    try:
        with open(files[-1]) as f:
            return json.load(f)
    except Exception:
        return {}

def color_class(val):
    if val is None:
        return "neutral"
    return "up" if float(val) >= 0 else "down"

def pct_str(val):
    if val is None:
        return "—"
    v = float(val)
    return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; }
  div[data-testid="metric-container"] {
    background: #1a1a2e; border-radius: 8px; padding: 10px;
    border: 1px solid #16213e;
  }
  h2 { font-size: 1.05rem !important; border-bottom: 1px solid #ffffff22; padding-bottom: 3px; margin-top: 1rem !important; }
  .regime-fail { background:#2d0000; border:1px solid #ff4b4b; border-radius:8px; padding:6px 14px; color:#ff4b4b; font-weight:bold; display:inline-block; }
  .regime-pass { background:#002d10; border:1px solid #00d26a; border-radius:8px; padding:6px 14px; color:#00d26a; font-weight:bold; display:inline-block; }
  .pill { display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:bold; margin:2px; }
  .pill-bull  { background:#00d26a22; color:#00d26a; border:1px solid #00d26a55; }
  .pill-bear  { background:#ff4b4b22; color:#ff4b4b; border:1px solid #ff4b4b55; }
  .pill-neut  { background:#ffffff11; color:#aaa;    border:1px solid #ffffff22; }

  /* ── Ticker tape ── */
  .ticker-wrap {
    overflow: hidden; background: #0a0a14; border: 1px solid #1a1a2e;
    border-radius: 8px; padding: 10px 0; margin-bottom: 8px;
  }
  .ticker-scroll {
    display: flex; gap: 0; white-space: nowrap;
    animation: scroll-left 60s linear infinite;
  }
  .ticker-scroll:hover { animation-play-state: paused; }
  @keyframes scroll-left {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }
  .tick-item {
    display: inline-flex; flex-direction: column; align-items: flex-start;
    padding: 4px 24px; border-right: 1px solid #1a1a2e; min-width: 120px;
  }
  .tick-sym  { font-size: 14px; font-weight: 700; color: #ffffff; letter-spacing: 0.5px; }
  .tick-price{ font-size: 13px; color: #cccccc; }
  .tick-chg-up  { font-size: 12px; color: #00d26a; font-weight: 600; }
  .tick-chg-dn  { font-size: 12px; color: #ff4b4b; font-weight: 600; }
  .tick-chg-neu { font-size: 12px; color: #888888; }

  /* ── Ticker grid cards ── */
  .grid-card {
    background: #111120; border: 1px solid #1e1e35; border-radius: 10px;
    padding: 14px 16px; text-align: center; margin-bottom: 8px;
  }
  .gc-sym   { font-size: 18px; font-weight: 800; color: #fff; }
  .gc-label { font-size: 11px; color: #888; margin-top: 2px; }
  .gc-price { font-size: 22px; font-weight: 700; margin-top: 6px; }
  .gc-chg   { font-size: 14px; font-weight: 600; margin-top: 2px; }
  .gc-up    { color: #00d26a; }
  .gc-dn    { color: #ff4b4b; }
  .gc-neu   { color: #888888; }
</style>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🤖  Trading Intelligence", "🎯  Prediction Markets", "📺  Ticker Display"])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — TRADING INTELLIGENCE
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    col_t, col_ts = st.columns([5, 2])
    with col_t:
        st.markdown("# Larsen Ventures — Trading Intelligence")
    with col_ts:
        st.markdown(f"<p style='color:#666;font-size:12px;margin-top:22px'>Auto-refreshes every 60s · {datetime.now().strftime('%d %b %Y %H:%M')}</p>", unsafe_allow_html=True)

    st.markdown("---")

    # ── ROW 1: Macro + Portfolio ──────────────────────────────────────────────
    macro   = latest_kb("macro_data")
    account = alpaca_get("/v2/account")
    positions = alpaca_get("/v2/positions") or []
    if isinstance(positions, dict):
        positions = []

    col_macro, col_port = st.columns([1, 2])

    with col_macro:
        st.markdown("## Macro Regime")
        gate    = macro.get("macro_gate", False)
        regime  = macro.get("regime", "UNKNOWN")
        spy     = macro.get("spy_price")
        sma200  = macro.get("spy_sma200")
        vix     = macro.get("vix")
        hy      = macro.get("hy_spread")
        fed     = macro.get("fed_funds_rate")
        yc      = macro.get("yield_curve_10y2y")

        gate_text = "MACRO GATE: PASS — Trading Enabled" if gate else "MACRO GATE: FAIL — Holding Cash"
        st.markdown(f"<div class='{'regime-pass' if gate else 'regime-fail'}'>{gate_text}</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-top:8px'><b>Regime:</b> <code>{regime}</code></p>", unsafe_allow_html=True)

        if spy and sma200:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=float(spy),
                delta={"reference": float(sma200), "valueformat": ".2f"},
                title={"text": "SPY vs 200 SMA", "font": {"size": 12}},
                gauge={
                    "axis": {"range": [float(sma200) * 0.92, float(sma200) * 1.08]},
                    "bar": {"color": "#00d26a" if gate else "#ff4b4b"},
                    "threshold": {"line": {"color": "white", "width": 2}, "value": float(sma200)},
                    "bgcolor": "#1a1a2e",
                },
                number={"valueformat": ".2f", "prefix": "$"},
            ))
            fig.update_layout(height=190, margin=dict(l=5, r=5, t=25, b=5),
                              paper_bgcolor="#0e0e1a", font_color="white")
            st.plotly_chart(fig, use_container_width=True)

        m1, m2 = st.columns(2)
        m1.metric("VIX",         f"{float(vix):.1f}"  if vix  else "—")
        m1.metric("Fed Funds",   f"{float(fed):.2f}%" if fed  else "—")
        m2.metric("HY Spread",   f"{float(hy):.2f}%"  if hy   else "—")
        m2.metric("Yield Curve", f"{float(yc):+.2f}%" if yc   else "—")

    with col_port:
        st.markdown("## Portfolio")
        if account:
            equity   = float(account.get("equity", 0))
            cash     = float(account.get("cash", 0))
            p_change = float(account.get("change_today", 0) or 0)
            deployed = equity - cash
            BUDGET   = 6300

            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Equity",    f"${equity:,.0f}",   delta=f"${p_change:+,.0f}" if p_change else None)
            p2.metric("Cash",      f"${cash:,.0f}")
            p3.metric("Deployed",  f"${deployed:,.0f}", delta=f"{deployed/equity*100:.0f}%" if equity else None)
            p4.metric("Positions", str(len(positions)))

            st.markdown("**Trial budget** ($6,300 USD cap)")
            budget_pct = min(deployed / BUDGET, 1.0) if BUDGET else 0
            st.progress(budget_pct, text=f"${min(deployed,BUDGET):,.0f} / ${BUDGET:,} ({budget_pct*100:.0f}%)")
        else:
            st.warning("Cannot reach Alpaca API")

        if positions:
            import pandas as pd
            rows = []
            for p in positions:
                pnl_pct = float(p.get("unrealized_plpc", 0)) * 100
                rows.append({
                    "Ticker": p.get("symbol", ""),
                    "Qty":    int(float(p.get("qty", 0))),
                    "Entry":  f"${float(p.get('avg_entry_price',0)):.2f}",
                    "Now":    f"${float(p.get('current_price',0)):.2f}",
                    "P&L":    f"${float(p.get('unrealized_pl',0)):+.2f}",
                    "P&L %":  pct_str(pnl_pct),
                    "Value":  f"${float(p.get('market_value',0)):,.0f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No open positions — holding cash (macro gate FAIL)")

    st.markdown("---")

    # ── ROW 2: What Chappie Is Learning ───────────────────────────────────────
    st.markdown("## What Chappie Is Learning")
    l1, l2, l3, l4 = st.columns(4)

    with l1:
        sent   = latest_kb("sentiment")
        fg     = sent.get("fear_greed_index", {})
        fg_val = fg.get("value")
        fg_lbl = fg.get("label", "")
        st.markdown("### Sentiment")
        if fg_val is not None:
            fg_int = int(fg_val)
            clr = ("#ff4b4b" if fg_int < 25 else "#ffaa00" if fg_int < 45
                   else "#aaaaaa" if fg_int < 55 else "#88dd88" if fg_int < 75 else "#00d26a")
            fig_fg = go.Figure(go.Indicator(
                mode="gauge+number",
                value=fg_int,
                title={"text": f"Fear & Greed<br><span style='font-size:10px'>{fg_lbl}</span>", "font": {"size": 11}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": clr},
                    "steps": [
                        {"range": [0, 25],   "color": "#2d0000"},
                        {"range": [25, 45],  "color": "#2d1500"},
                        {"range": [45, 55],  "color": "#1a1a1a"},
                        {"range": [55, 75],  "color": "#002010"},
                        {"range": [75, 100], "color": "#001a08"},
                    ],
                    "bgcolor": "#1a1a2e",
                },
            ))
            fig_fg.update_layout(height=175, margin=dict(l=5, r=5, t=30, b=5),
                                 paper_bgcolor="#0e0e1a", font_color="white")
            st.plotly_chart(fig_fg, use_container_width=True)
        signals = sent.get("signals", {})
        for ticker, sig in list(signals.items())[:4]:
            s = sig.get("signal", "")
            if "CONTRARIAN" in s or "BULLISH" in s or "BEARISH" in s:
                pill = "pill-bull" if "BUY" in s or "BULLISH" in s else "pill-bear"
                st.markdown(f"<span class='pill {pill}'>{ticker} {s.replace('_',' ')}</span>", unsafe_allow_html=True)

    with l2:
        insider  = latest_kb("insider_trades")
        clusters = insider.get("clusters", {})
        st.markdown("### Insider Clusters")
        if clusters:
            for ticker, info in sorted(clusters.items(), key=lambda x: -x[1].get("count", 0))[:6]:
                cnt   = info.get("count", 0)
                trend = info.get("trend", "mixed")
                pill  = "pill-bull" if trend == "buy_heavy" else "pill-bear" if trend == "sell_heavy" else "pill-neut"
                st.markdown(f"<span class='pill {pill}'>{ticker} {cnt}x {trend.replace('_',' ')}</span>", unsafe_allow_html=True)
        else:
            st.caption("No clusters (2+ filings / 7 days)")
        if insider.get("_saved_at"):
            st.caption(f"Updated: {insider['_saved_at'][:16]}")

    with l3:
        contracts = latest_kb("govt_contracts")
        large     = contracts.get("large_awards", {})
        all_c     = contracts.get("contracts", {})
        st.markdown("### Govt Contracts")
        if large:
            for ticker, info in large.items():
                amt = info["largest"]["amount"] / 1e6
                st.markdown(f"<span class='pill pill-bull'>{ticker} ${amt:.0f}M</span>", unsafe_allow_html=True)
                st.caption(info["largest"]["agency"][:38])
        elif all_c:
            for ticker in list(all_c.keys())[:4]:
                st.markdown(f"<span class='pill pill-neut'>{ticker} active</span>", unsafe_allow_html=True)
        else:
            st.caption("No federal contracts this month")

    with l4:
        sec    = latest_kb("sec_filings")
        urgent = sec.get("urgent", [])
        new_f  = sec.get("new_filings", [])
        st.markdown("### 8-K Alerts")
        if urgent:
            st.markdown(f"🔴 **{len(urgent)} urgent**")
            for f in urgent[:4]:
                items = ", ".join(f.get("form_items", []))
                st.markdown(f"<span class='pill pill-bear'>{f['ticker']} Items {items}</span>", unsafe_allow_html=True)
        elif new_f:
            st.markdown(f"🟡 {len(new_f)} new (non-urgent)")
        else:
            st.caption("No new 8-K filings since last scan")
        if sec.get("_saved_at"):
            st.caption(f"Scanned: {sec['_saved_at'][:16]}")

    st.markdown("---")

    # ── ROW 3: Live Trading Watchlist ─────────────────────────────────────────
    st.markdown("## Live Trading Watchlist")
    with st.spinner("Fetching prices..."):
        tq = get_all_quotes(tuple(TRADING_WATCHLIST))

    ticker_cols = st.columns(5)
    for i, ticker in enumerate(TRADING_WATCHLIST):
        q       = tq.get(ticker, {})
        price   = q.get("c")
        prev    = q.get("pc")
        chg     = q.get("dp") or ((price - prev) / prev * 100 if price and prev and prev > 0 else None)
        tier    = TIERS.get(ticker, "?")
        tier_lbl = {"tier_1_core": "T1", "tier_2_growth": "T2", "tier_3_speculative": "T3"}.get(tier, "?")
        col = ticker_cols[i % 5]
        if price:
            col.metric(
                f"{ticker} [{tier_lbl}]",
                f"${price:.2f}",
                delta=pct_str(chg),
                delta_color="normal" if chg and chg >= 0 else "inverse",
            )
        else:
            col.metric(f"{ticker} [{tier_lbl}]", "—")

    st.markdown("---")

    # ── ROW 4: Staged Decisions ───────────────────────────────────────────────
    st.markdown("## What Chappie Is Thinking")
    staged_path = Path(f"/tmp/staged_decisions_{datetime.now().strftime('%Y-%m-%d')}.json")
    if not staged_path.exists():
        staged_path = Path(f"/tmp/staged_decisions_{(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')}.json")

    if staged_path.exists():
        try:
            with open(staged_path) as f:
                staged = json.load(f)
            decisions = staged.get("decisions", [])
            st.caption(f"Analysis prepared: {staged.get('prepared_at', '')}")
            if decisions:
                for d in decisions:
                    action = d.get("action", "")
                    pill   = "pill-bull" if action == "BUY" else "pill-bear" if action == "SELL" else "pill-neut"
                    with st.expander(f"{action} {d.get('ticker','')} — Confidence {d.get('confidence',0)}/10"):
                        st.markdown(f"<span class='pill {pill}'>{action}</span>", unsafe_allow_html=True)
                        st.write(d.get("rationale", d.get("reason", "")))
            else:
                st.info("No trades staged — macro gate FAIL or no high-conviction setups found")
        except Exception as e:
            st.error(f"Could not parse staged decisions: {e}")
    else:
        st.info("No staged decisions yet today. PREPARE job runs at 8pm AWST.")

    st.markdown("---")

    # ── ROW 5: Trade History ──────────────────────────────────────────────────
    st.markdown("## Trade History")
    history_path = BASE / "trade_history.json"
    if history_path.exists():
        try:
            import pandas as pd
            with open(history_path) as f:
                history = json.load(f)
            trades = history if isinstance(history, list) else history.get("trades", [])
            if trades:
                rows = []
                for t in reversed(trades[-50:]):
                    rows.append({
                        "Date":   t.get("date", t.get("timestamp", ""))[:10],
                        "Action": t.get("action", ""),
                        "Ticker": t.get("ticker", ""),
                        "Qty":    t.get("quantity", t.get("qty", "")),
                        "Price":  f"${float(t.get('price',0)):.2f}" if t.get("price") else "—",
                        "P&L":    f"${float(t.get('pnl',0)):+.2f}" if t.get("pnl") is not None else "—",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                closed = [t for t in trades if t.get("action") == "SELL" and t.get("pnl") is not None]
                if closed:
                    wins      = [t for t in closed if float(t.get("pnl", 0)) > 0]
                    total_pnl = sum(float(t.get("pnl", 0)) for t in closed)
                    s1, s2, s3 = st.columns(3)
                    s1.metric("Closed Trades", len(closed))
                    s2.metric("Win Rate",      f"{len(wins)/len(closed)*100:.0f}%")
                    s3.metric("Total P&L",     f"${total_pnl:+,.2f}")
            else:
                st.info("No trades yet — trial started 21 March 2026")
        except Exception as e:
            st.error(f"Could not load trade history: {e}")
    else:
        st.info("No trades yet — trial started 21 March 2026")

    st.markdown("---")

    # ── ROW 6: System Health ──────────────────────────────────────────────────
    st.markdown("## System Health")

    def freshness(kb_dir, max_hours=2):
        files = sorted(glob.glob(str(KB / kb_dir / "*.json")))
        if not files:
            return "⚫ No data", False
        age_h = (time.time() - os.path.getmtime(files[-1])) / 3600
        if age_h < max_hours:
            return f"✅ {int(age_h*60)}m ago", True
        elif age_h < 24:
            return f"🟡 {int(age_h)}h ago", False
        return f"🔴 {int(age_h/24)}d ago", False

    checks = [
        ("Sentiment",      "sentiment",        1),
        ("Insider Trades", "insider_trades",   26),
        ("Macro Data",     "macro_data",       26),
        ("Govt Contracts", "govt_contracts",   26),
        ("Earnings Cal",   "earnings_calendar",26),
        ("8-K Monitor",    "sec_filings",       1),
    ]
    hcols = st.columns(6)
    for (label, subdir, max_h), col in zip(checks, hcols):
        status, _ = freshness(subdir, max_h)
        col.markdown(f"**{label}**<br>{status}", unsafe_allow_html=True)

    prepare_log = Path("/tmp/trading_prepare.log")
    execute_log = Path("/tmp/trading_execute.log")
    lg1, lg2 = st.columns(2)
    with lg1:
        if prepare_log.exists():
            age = (time.time() - prepare_log.stat().st_mtime) / 3600
            st.markdown(f"**PREPARE** — {'✅' if age < 26 else '🔴'} {int(age)}h ago")
            with st.expander("View log"):
                st.code(prepare_log.read_text()[-2000:], language="text")
        else:
            st.markdown("**PREPARE** — ⚫ Not yet run")
    with lg2:
        if execute_log.exists():
            age = (time.time() - execute_log.stat().st_mtime) / 3600
            st.markdown(f"**EXECUTE** — {'✅' if age < 26 else '🔴'} {int(age)}h ago")
            with st.expander("View log"):
                st.code(execute_log.read_text()[-2000:], language="text")
        else:
            st.markdown("**EXECUTE** — ⚫ Not yet run")

    st.markdown("<p style='color:#333;font-size:11px;text-align:center;margin-top:1rem'>Larsen Ventures · Paper trial 21 Mar – 18 Apr 2026 · Built by Chappie</p>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — PREDICTION MARKETS (Betfair Engine)
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    col_t2, col_ts2 = st.columns([5, 2])
    with col_t2:
        st.markdown("# Larsen Ventures — Prediction Markets")
    with col_ts2:
        st.markdown(f"<p style='color:#666;font-size:12px;margin-top:22px'>Betfair Exchange · Paper Mode · {datetime.now().strftime('%d %b %Y %H:%M')}</p>", unsafe_allow_html=True)

    # ── Load ledger ───────────────────────────────────────────────────────────
    def load_betfair_ledger():
        if BETFAIR_LEDGER.exists():
            try:
                with open(BETFAIR_LEDGER) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    ledger = load_betfair_ledger()

    if ledger is None:
        st.info("Prediction engine is live but no bets placed yet. The scanner will find opportunities and record them here automatically.")
        ledger = {
            "bankroll_gbp": 250.0,
            "bankroll_aud": 500.0,
            "bets": [],
            "stats": {"total_bets": 0, "wins": 0, "losses": 0,
                      "total_staked": 0, "total_profit": 0, "roi_pct": 0},
            "started": datetime.now().isoformat(),
        }

    bets        = ledger.get("bets", [])
    stats       = ledger.get("stats", {})
    open_bets   = [b for b in bets if b.get("status") == "OPEN"]
    settled     = [b for b in bets if b.get("status") == "SETTLED"]
    wins        = [b for b in settled if b.get("result") == "WIN"]
    bankroll    = ledger.get("bankroll_gbp", 250.0)
    start_br    = 250.0  # £250 starting (£500 AUD @ 0.50)
    total_pnl   = bankroll - start_br
    roi_pct     = (total_pnl / stats.get("total_staked", 1)) * 100 if stats.get("total_staked", 0) > 0 else 0
    win_rate    = (len(wins) / len(settled) * 100) if settled else 0
    avg_edge    = (sum(b.get("edge", 0) for b in bets) / len(bets) * 100) if bets else 0
    avg_odds    = (sum(b.get("back_price", 0) for b in bets) / len(bets)) if bets else 0

    st.markdown("---")

    # ── ROW 1: P&L Summary ───────────────────────────────────────────────────
    st.markdown("## Bankroll & P&L")
    b1, b2, b3, b4, b5 = st.columns(5)
    b1.metric("Bankroll",      f"£{bankroll:,.2f}",
              delta=f"£{total_pnl:+.2f}" if bets else None)
    b2.metric("Starting",      f"£{start_br:,.2f}")
    b3.metric("Total P&L",     f"£{total_pnl:+.2f}",
              delta_color="normal" if total_pnl >= 0 else "inverse")
    b4.metric("ROI",           f"{roi_pct:.1f}%" if bets else "—")
    b5.metric("Paper Mode",    "✅ Active")

    if bets:
        br_pct = bankroll / start_br
        label  = f"£{bankroll:.2f} / £{start_br:.2f}"
        clr    = "normal" if br_pct >= 1 else "inverse"
        st.progress(min(br_pct, 1.5) / 1.5,
                    text=f"Bankroll: {label}  ({br_pct*100:.1f}% of starting)")

    st.markdown("---")

    # ── ROW 2: Performance Stats ──────────────────────────────────────────────
    st.markdown("## Performance")
    p1, p2, p3, p4, p5, p6 = st.columns(6)
    p1.metric("Total Bets",  str(stats.get("total_bets", 0)))
    p2.metric("Open",        str(len(open_bets)))
    p3.metric("Settled",     str(len(settled)))
    p4.metric("Win Rate",    f"{win_rate:.0f}%" if settled else "—")
    p5.metric("Avg Edge",    f"{avg_edge:.1f}%" if bets else "—")
    p6.metric("Avg Odds",    f"{avg_odds:.2f}" if bets else "—")

    # Go/no-go progress bar
    if settled:
        st.markdown("**Go / No-Go Criteria** (4-week paper trial — minimum thresholds)")
        g1, g2, g3 = st.columns(3)
        with g1:
            roi_ok = roi_pct > 0
            st.markdown(f"{'✅' if roi_ok else '🔴'} **Positive ROI after 5% commission**  \n`{roi_pct:.1f}%` (target: > 0%)")
        with g2:
            wr_ok = win_rate >= 52
            st.markdown(f"{'✅' if wr_ok else '🔴'} **Win Rate**  \n`{win_rate:.1f}%` (target: ≥ 52%)")
        with g3:
            min_bets = len(settled) >= 20
            st.markdown(f"{'✅' if min_bets else '⏳'} **Sample Size**  \n`{len(settled)} settled` (target: ≥ 20 for significance)")

    st.markdown("---")

    # ── ROW 3: Open Bets ─────────────────────────────────────────────────────
    st.markdown(f"## Open Bets  `{len(open_bets)}`")
    if open_bets:
        import pandas as pd
        rows = []
        for b in open_bets:
            agent_p  = b.get("agent_prob", 0) or 0
            mkt_p    = b.get("market_prob", 0) or 0
            edge_pct = b.get("edge", 0) * 100
            edge_str = f"+{edge_pct:.1f}%" if edge_pct > 0 else f"{edge_pct:.1f}%"
            rows.append({
                "Event":      b.get("event", ""),
                "Market":     b.get("market", ""),
                "Selection":  b.get("selection", ""),
                "Odds":       f"{b.get('back_price', 0):.2f}",
                "Stake":      f"£{b.get('stake_gbp', 0):.2f}",
                "To Win":     f"£{b.get('potential_profit', 0):.2f}",
                "Our Prob":   f"{agent_p*100:.0f}%",
                "Mkt Prob":   f"{mkt_p*100:.0f}%",
                "Edge":       edge_str,
                "Type":       b.get("event_type", ""),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Show reasoning for each open bet
        st.markdown("**Signal Reasoning**")
        for b in open_bets:
            reasoning = b.get("reasoning", "No reasoning captured")
            edge_pct  = (b.get("edge", 0) or 0) * 100
            pill_cls  = "pill-bull" if edge_pct >= 5 else "pill-neut"
            with st.expander(f"{b.get('event','')} — {b.get('selection','')} @ {b.get('back_price','')} | edge {edge_pct:.1f}%"):
                col_r1, col_r2 = st.columns([1, 3])
                with col_r1:
                    st.metric("Our Probability",    f"{(b.get('agent_prob',0) or 0)*100:.0f}%")
                    st.metric("Market Probability", f"{(b.get('market_prob',0) or 0)*100:.0f}%")
                    st.metric("Stake",              f"£{b.get('stake_gbp',0):.2f}")
                    st.metric("Kelly Edge",         f"{edge_pct:.1f}%")
                with col_r2:
                    st.markdown(f"**Reasoning:** {reasoning}")
    else:
        st.info("No open bets. Scanner places bets when it detects positive-edge opportunities (Kelly edge > 3%).")

    st.markdown("---")

    # ── ROW 4: Calibration (prob estimate vs actual) ──────────────────────────
    if settled:
        st.markdown("## Probability Calibration")
        st.caption("How well our probability estimates track actual outcomes. Should sit on the diagonal.")

        # Bucket agent probs into deciles and compare actual win rate
        buckets = {}
        for b in settled:
            ap = b.get("agent_prob", 0) or 0
            bucket = round(ap * 10) / 10  # round to nearest 0.1
            if bucket not in buckets:
                buckets[bucket] = {"count": 0, "wins": 0}
            buckets[bucket]["count"] += 1
            if b.get("result") == "WIN":
                buckets[bucket]["wins"] += 1

        if buckets:
            xs, ys, sizes = [], [], []
            for prob, data in sorted(buckets.items()):
                if data["count"] > 0:
                    xs.append(prob)
                    ys.append(data["wins"] / data["count"])
                    sizes.append(data["count"] * 15)

            fig_cal = go.Figure()
            fig_cal.add_trace(go.Scatter(
                x=[0, 1], y=[0, 1],
                mode="lines", name="Perfect calibration",
                line=dict(dash="dash", color="#555555"),
            ))
            fig_cal.add_trace(go.Scatter(
                x=xs, y=ys, mode="markers+lines",
                name="Agent calibration",
                marker=dict(size=sizes, color="#00d26a"),
                line=dict(color="#00d26a"),
            ))
            fig_cal.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor="#0e0e1a", plot_bgcolor="#0e0e1a",
                font_color="white",
                xaxis_title="Predicted Probability",
                yaxis_title="Actual Win Rate",
                xaxis=dict(range=[0, 1], gridcolor="#1a1a2e"),
                yaxis=dict(range=[0, 1], gridcolor="#1a1a2e"),
            )
            st.plotly_chart(fig_cal, use_container_width=True)

        st.markdown("---")

    # ── ROW 5: Settled Bet History ────────────────────────────────────────────
    st.markdown("## Settled History")
    if settled:
        import pandas as pd
        rows = []
        for b in reversed(settled[-50:]):
            result  = b.get("result", "")
            profit  = b.get("profit", 0) or 0
            rows.append({
                "Date":      (b.get("timestamp", "")[:10]),
                "Event":     b.get("event", ""),
                "Selection": b.get("selection", ""),
                "Odds":      f"{b.get('back_price',0):.2f}",
                "Stake":     f"£{b.get('stake_gbp',0):.2f}",
                "Result":    result,
                "P&L":       f"£{profit:+.2f}",
                "Our Prob":  f"{(b.get('agent_prob',0) or 0)*100:.0f}%",
                "Edge":      f"{(b.get('edge',0) or 0)*100:.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # P&L chart
        cumulative, running = [], 0
        for b in settled:
            running += b.get("profit", 0) or 0
            cumulative.append(running)

        fig_pnl = go.Figure()
        fig_pnl.add_trace(go.Scatter(
            y=cumulative, mode="lines+markers",
            line=dict(color="#00d26a" if running >= 0 else "#ff4b4b", width=2),
            marker=dict(size=5),
            name="Cumulative P&L (£)",
            fill="tozeroy",
            fillcolor="rgba(0,210,106,0.1)" if running >= 0 else "rgba(255,75,75,0.1)",
        ))
        fig_pnl.add_hline(y=0, line_dash="dash", line_color="#555555")
        fig_pnl.update_layout(
            height=220, margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="#0e0e1a", plot_bgcolor="#0e0e1a",
            font_color="white", yaxis_title="Cumulative P&L (£)",
            xaxis_title="Bet Number", xaxis=dict(gridcolor="#1a1a2e"),
            yaxis=dict(gridcolor="#1a1a2e"),
        )
        st.plotly_chart(fig_pnl, use_container_width=True)
    else:
        st.info("No settled bets yet. Open bets settle automatically when events complete.")

    st.markdown("---")

    # ── ROW 6: System Health ──────────────────────────────────────────────────
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

    with h1:
        st.markdown(f"**Ledger**<br>{ledger_age}", unsafe_allow_html=True)
    with h2:
        st.markdown(f"**Last Scan**<br>{log_age}", unsafe_allow_html=True)
    with h3:
        paper_on = True  # always paper mode for now
        st.markdown(f"**Mode**<br>{'✅ Paper (safe)' if paper_on else '🔴 LIVE'}", unsafe_allow_html=True)
    with h4:
        started = ledger.get("started", "")[:10] if ledger.get("started") else "—"
        st.markdown(f"**Trial Start**<br>{started}", unsafe_allow_html=True)

    if bf_log.exists():
        with st.expander("View scanner log"):
            st.code(bf_log.read_text()[-2000:], language="text")

    st.markdown("<p style='color:#333;font-size:11px;text-align:center;margin-top:1rem'>Larsen Ventures · Betfair Prediction Engine · Paper Mode · Built by Chappie</p>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — TICKER DISPLAY  (office wall view)
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    cfg     = load_ticker_config()
    tickers = cfg.get("tickers", [])
    name    = cfg.get("display_name", "Larsen Ventures")

    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;'>
      <span style='font-size:22px; font-weight:800; color:#ffffff; letter-spacing:1px'>{name.upper()}</span>
      <span style='font-size:12px; color:#555'>{datetime.now().strftime('%A %d %b %Y  %H:%M')} AWST</span>
    </div>
    """, unsafe_allow_html=True)

    if not tickers:
        st.warning(f"No tickers configured. Edit `{DROPBOX_CFG}` to add stocks.")
    else:
        symbols = tuple(t["symbol"] for t in tickers)
        with st.spinner("Loading live prices..."):
            quotes = get_all_quotes(symbols)

        # ── Scrolling ticker tape ──────────────────────────────────────────────
        def ticker_html(tickers_list, quotes_dict):
            items = []
            for t in tickers_list:
                sym   = t["symbol"]
                label = t.get("label", sym.replace(".AX", ""))
                q     = quotes_dict.get(sym, {})
                price = q.get("c")
                chg   = q.get("dp") or (
                    (q["c"] - q["pc"]) / q["pc"] * 100 if q.get("c") and q.get("pc") and q["pc"] > 0 else None
                )
                price_str = f"${price:,.2f}" if price else "—"
                if chg is None:
                    chg_cls, chg_str, arrow = "tick-chg-neu", "—", ""
                elif chg >= 0:
                    chg_cls, chg_str, arrow = "tick-chg-up", f"+{chg:.2f}%", "▲"
                else:
                    chg_cls, chg_str, arrow = "tick-chg-dn", f"{chg:.2f}%", "▼"
                items.append(f"""
                  <div class='tick-item'>
                    <span class='tick-sym'>{label}</span>
                    <span class='tick-price'>{price_str}</span>
                    <span class='{chg_cls}'>{arrow} {chg_str}</span>
                  </div>""")
            content = "".join(items)
            # Duplicate for seamless loop
            return f"<div class='ticker-wrap'><div class='ticker-scroll'>{content}{content}</div></div>"

        st.markdown(ticker_html(tickers, quotes), unsafe_allow_html=True)

        # ── Price grid cards ───────────────────────────────────────────────────
        st.markdown("")

        # Group by group field
        groups = {}
        for t in tickers:
            g = t.get("group", "Other")
            groups.setdefault(g, []).append(t)

        for group_name, group_tickers in groups.items():
            st.markdown(f"<p style='color:#555;font-size:11px;font-weight:600;letter-spacing:1px;margin:12px 0 4px 0'>{group_name.upper()}</p>", unsafe_allow_html=True)
            n_cols = min(len(group_tickers), 6)
            cols   = st.columns(n_cols)
            for i, t in enumerate(group_tickers):
                sym   = t["symbol"]
                label = t.get("label", sym.replace(".AX", ""))
                q     = quotes.get(sym, {})
                price = q.get("c")
                chg   = q.get("dp") or (
                    (q["c"] - q["pc"]) / q["pc"] * 100 if q.get("c") and q.get("pc") and q["pc"] > 0 else None
                )
                with cols[i % n_cols]:
                    if price:
                        clr    = "gc-up" if (chg or 0) >= 0 else "gc-dn"
                        arrow  = "▲" if (chg or 0) >= 0 else "▼"
                        chg_s  = f"{arrow} {abs(chg):.2f}%" if chg is not None else "—"
                        suffix = ".AX" if sym.endswith(".AX") else ""
                        # Use AUD for ASX, USD for US
                        currency = "A$" if suffix else "$"
                        st.markdown(f"""
                        <div class='grid-card'>
                          <div class='gc-sym'>{sym.replace('.AX','')}</div>
                          <div class='gc-label'>{label}</div>
                          <div class='gc-price {clr}'>{currency}{price:,.2f}</div>
                          <div class='gc-chg {clr}'>{chg_s}</div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class='grid-card'>
                          <div class='gc-sym'>{sym.replace('.AX','')}</div>
                          <div class='gc-label'>{label}</div>
                          <div class='gc-price gc-neu'>—</div>
                          <div class='gc-chg gc-neu'>No data</div>
                        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"""
        <p style='color:#333; font-size:11px; text-align:center'>
          Config file: <code>~/Dropbox/Chappie Share/ticker_config.json</code> · 
          Add/remove tickers by editing that file · Updates appear within 60 seconds
        </p>""", unsafe_allow_html=True)
