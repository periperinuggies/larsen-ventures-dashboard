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
tab1, tab2 = st.tabs(["🤖  Trading Intelligence", "📺  Ticker Display"])

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
# TAB 2 — TICKER DISPLAY  (office wall view)
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
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
