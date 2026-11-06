#!/usr/bin/env python3
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import importlib
import config
import simulator_engine

importlib.reload(simulator_engine)
from simulator_engine import (
    load_wikifolio_positions,
    fetch_stock_data,
    calculate_technical_indicators,
    evaluate_risk_and_rating,
    simulate_future_scenarios,
    generate_advisory_report,
    search_tickers,
)

st.set_page_config(
    page_title="Aktien-Simulator & Risiko-Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS für modernes Finanz-Dashboard-Design
st.markdown(
    """
    <style>
    .rating-card {
        border-radius: 12px;
        padding: 18px 22px;
        color: #ffffff;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    .rating-grade {
        font-size: 2.6rem;
        font-weight: 800;
        line-height: 1.1;
        letter-spacing: 1px;
    }
    .rating-sub {
        font-size: 0.95rem;
        opacity: 0.92;
        margin-top: 4px;
    }
    .advisory-box {
        border-left: 5px solid #3b82f6;
        background-color: rgba(59, 130, 246, 0.08);
        padding: 16px 20px;
        border-radius: 0 10px 10px 0;
        margin-bottom: 16px;
    }
    .signal-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900, show_spinner=False)
def cached_fetch_stock(query: str, period: str, exchange_suffix: str = "AUTO"):
    return fetch_stock_data(query, period=period, exchange_suffix=exchange_suffix)


@st.cache_data(ttl=900, show_spinner=False)
def cached_search_tickers(query: str):
    return search_tickers(query)


@st.cache_data(ttl=300, show_spinner=False)
def cached_wikifolio_positions(fetch_live: bool = False):
    return load_wikifolio_positions(fetch_live=fetch_live)


def format_large_number(val) -> str:
    if val is None or pd.isna(val):
        return "—"
    val = float(val)
    if abs(val) >= 1e12:
        return f"{val / 1e12:.2f} Bio."
    if abs(val) >= 1e9:
        return f"{val / 1e9:.2f} Mrd."
    if abs(val) >= 1e6:
        return f"{val / 1e6:.2f} Mio."
    return f"{val:,.0f}"


def build_technical_chart(df: pd.DataFrame, tech_data: dict, symbol: str, currency: str, show_bb: bool, show_reg: bool, show_fib: bool, show_sr: bool) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=(
            "",
            "Relative Strength Index (RSI 14)",
            "MACD (12, 26, 9)",
        ),
    )

    # 1. Candlestick / Kurs im Hauptchart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Kurs (OHLC)",
            increasing_line_color="#10b981",
            decreasing_line_color="#ef4444",
        ),
        row=1,
        col=1,
    )

    # Gleitende Durchschnitte
    fig.add_trace(
        go.Scatter(x=df.index, y=df["SMA_20"], name="SMA 20", line=dict(color="#38bdf8", width=1.3)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["SMA_50"], name="SMA 50", line=dict(color="#f59e0b", width=1.6)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["SMA_200"], name="SMA 200", line=dict(color="#a855f7", width=2.0)),
        row=1,
        col=1,
    )

    # Bollinger Bänder
    if show_bb:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["BB_Upper"],
                name="Bollinger Oben (2σ)",
                line=dict(color="rgba(148, 163, 184, 0.5)", width=1, dash="dot"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["BB_Lower"],
                name="Bollinger Unten (2σ)",
                line=dict(color="rgba(148, 163, 184, 0.5)", width=1, dash="dot"),
                fill="tonexty",
                fillcolor="rgba(148, 163, 184, 0.08)",
            ),
            row=1,
            col=1,
        )

    # Linearer Regressions-Trendkanal
    if show_reg:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Reg_Center"],
                name="Regressionstrend (6M)",
                line=dict(color="#3b82f6", width=1.8, dash="dash"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Reg_Upper"],
                name="Trendkanal Oben (+2σ)",
                line=dict(color="rgba(59, 130, 246, 0.55)", width=1.2, dash="dot"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Reg_Lower"],
                name="Trendkanal Unten (-2σ)",
                line=dict(color="rgba(59, 130, 246, 0.55)", width=1.2, dash="dot"),
                fill="tonexty",
                fillcolor="rgba(59, 130, 246, 0.06)",
            ),
            row=1,
            col=1,
        )

    # Support & Resistance Linien
    if show_sr:
        for res in tech_data["resistances"]:
            fig.add_hline(
                y=res,
                line_dash="dash",
                line_color="rgba(239, 68, 68, 0.65)",
                annotation_text=f"Widerstand {res:.2f}",
                annotation_position="top right",
                row=1,
                col=1,
            )
        for sup in tech_data["supports"]:
            fig.add_hline(
                y=sup,
                line_dash="dash",
                line_color="rgba(16, 185, 129, 0.65)",
                annotation_text=f"Support {sup:.2f}",
                annotation_position="bottom right",
                row=1,
                col=1,
            )

    # Fibonacci Retracements
    if show_fib:
        for label, val in tech_data["fibonacci_levels"].items():
            fig.add_hline(
                y=val,
                line_dash="dot",
                line_color="rgba(234, 179, 8, 0.45)",
                annotation_text=f"Fib {label}: {val:.2f}",
                annotation_position="top left",
                row=1,
                col=1,
            )

    # 2. RSI Subplot
    fig.add_trace(
        go.Scatter(x=df.index, y=df["RSI"], name="RSI (14)", line=dict(color="#ec4899", width=1.6)),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#10b981", row=2, col=1)
    fig.add_hline(y=50, line_dash="solid", line_color="rgba(148,163,184,0.3)", row=2, col=1)

    # 3. MACD Subplot
    colors_macd = np.where(df["MACD_Hist"] >= 0, "#10b981", "#ef4444")
    fig.add_trace(
        go.Bar(x=df.index, y=df["MACD_Hist"], name="MACD Histogramm", marker_color=colors_macd, opacity=0.65),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="#3b82f6", width=1.5)),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MACD_Signal"], name="Signal", line=dict(color="#f97316", width=1.5)),
        row=3,
        col=1,
    )

    fig.update_layout(
        height=820,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=95, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text=currency, row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)

    return fig


def build_simulation_chart(df: pd.DataFrame, sim_data: dict, risk_data: dict, symbol: str, currency: str) -> go.Figure:
    fig = go.Figure()

    # Letzte 120 Handelstage der echten Historie als Kontext
    hist_slice = df.iloc[-min(len(df), 120):]
    fig.add_trace(
        go.Scatter(
            x=hist_slice.index,
            y=hist_slice["Close"],
            name="Historischer Kurs",
            line=dict(color="#e2e8f0", width=2.4),
        )
    )

    f_dates = sim_data["future_dates"]
    pcts = sim_data["percentiles"]

    # Einzelne dünne Monte-Carlo-Zufallspfade im Hintergrund
    sample_paths = sim_data["sample_paths"]
    for i in range(min(25, sample_paths.shape[1])):
        fig.add_trace(
            go.Scatter(
                x=f_dates,
                y=sample_paths[:, i],
                mode="lines",
                line=dict(color="rgba(148, 163, 184, 0.12)", width=1),
                showlegend=(i == 0),
                name="Monte-Carlo Zufallspfade" if i == 0 else None,
                hoverinfo="skip",
            )
        )

    # 10% - 90% Konfidenzkorridor (Bull / Bear Band)
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=pcts["bull_90"],
            name="Bull-Szenario (90. Perzentil)",
            line=dict(color="#10b981", width=2, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=pcts["bear_10"],
            name="Bear-Szenario (10. Perzentil)",
            line=dict(color="#ef4444", width=2, dash="dash"),
            fill="tonexty",
            fillcolor="rgba(59, 130, 246, 0.08)",
        )
    )

    # 25% - 75% Kernkorridor
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=pcts["upper_75"],
            name="Oberes Quartil (75%)",
            line=dict(color="rgba(34, 197, 94, 0.5)", width=1, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=pcts["lower_25"],
            name="Unteres Quartil (25%)",
            line=dict(color="rgba(249, 115, 22, 0.5)", width=1, dash="dot"),
            fill="tonexty",
            fillcolor="rgba(59, 130, 246, 0.16)",
        )
    )

    # Median (Base Case) & Lineare Trend-Fortsetzung
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=pcts["median_50"],
            name="Base-Szenario (Median-Pfad)",
            line=dict(color="#3b82f6", width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=f_dates,
            y=pcts["regression_trend"],
            name="Lineare Trendkanal-Projektion",
            line=dict(color="#f59e0b", width=2, dash="dot"),
        )
    )

    # Analysten-Kursziel einzeichnen falls vorhanden
    analyst_target = risk_data["analyst_consensus"]["target_mean"]
    if analyst_target:
        fig.add_hline(
            y=analyst_target,
            line_dash="dashdot",
            line_color="#a855f7",
            annotation_text=f"Ø Analysten-Kursziel: {analyst_target:.2f} {currency}",
            annotation_position="top left",
        )

    fig.update_layout(
        height=540,
        template="plotly_dark",
        margin=dict(l=20, r=20, t=65, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
        hovermode="x unified",
        yaxis_title=f"Kurs ({currency})",
    )
    return fig


def main():
    # --- SIDEBAR: Aktienauswahl & Parameter ---
    with st.sidebar:
        st.title("🎛️ Simulations-Steuerung")
        st.caption("Wähle eine Aktie aus deinem Wikifolio-Depot oder suche weltweit nach jedem beliebigen Ticker / ISIN.")

        # 1. Wikifolio Schnellauswahl & Live-Refresh
        wf_positions = cached_wikifolio_positions(fetch_live=False)
        if st.button("🔄 Alle Marktdaten & Depot jetzt live aktualisieren", use_container_width=True):
            st.cache_data.clear()
            wf_positions = cached_wikifolio_positions(fetch_live=True)
            st.toast("Live-Daten von Yahoo Finance & Wikifolio wurden neu geladen!", icon="✅")

        preset_options = ["🔍 Freie Suche (Name, ISIN, ETF oder Ticker)"]
        preset_map = {}
        for pos in wf_positions:
            label = f"💼 {pos['name']} ({pos['percentage']:.1f}%)"
            preset_options.append(label)
            preset_map[label] = pos["isin"] or pos["name"]

        # Beliebte Standard-Aktien & ETFs ergänzen
        popular_stocks = [
            ("🌍 iShares Core MSCI World ETF (IE00B4L5Y983)", "EUNL.DE"),
            ("🌐 Vanguard FTSE All-World ETF (IE00BK5BQT80)", "VWCE.DE"),
            ("🇺🇸 iShares Core S&P 500 ETF (IE00B5BMR087)", "SXR8.DE"),
            ("🇩🇪 iShares Core DAX ETF (DE0005933931)", "EXS1.DE"),
            ("💻 iShares NASDAQ 100 ETF (IE00B53SZB19)", "SXRV.DE"),
            ("🍎 Apple (AAPL)", "AAPL"),
            ("🟢 NVIDIA (NVDA)", "NVDA"),
            ("🪟 Microsoft (MSFT)", "MSFT"),
            ("⚡ Tesla (TSLA)", "TSLA"),
            ("🇩🇪 Bayer (DE000BAY0017)", "BAYN.DE"),
            ("🇩🇪 SAP (SAP.DE)", "SAP.DE"),
            ("🇩🇪 Rheinmetall (RHM.DE)", "RHM.DE"),
            ("🇩🇪 Siemens (SIE.DE)", "SIE.DE"),
            ("🇩🇪 Allianz (ALV.DE)", "ALV.DE"),
            ("🇳🇱 ASML (ASML.AS)", "ASML.AS"),
            ("🔍 Alphabet (GOOGL)", "GOOGL"),
            ("📦 Amazon (AMZN)", "AMZN"),
        ]
        for label, sym in popular_stocks:
            preset_options.append(label)
            preset_map[label] = sym

        def on_preset_change():
            sel = st.session_state.get("preset_selector")
            if sel in preset_map:
                st.session_state["search_query_input"] = preset_map[sel]

        if "search_query_input" not in st.session_state:
            initial_preset = preset_options[1] if len(wf_positions) > 0 else "🟢 NVIDIA (NVDA)"
            st.session_state["search_query_input"] = preset_map.get(initial_preset, "NVDA")

        st.selectbox(
            "Schnellauswahl (Depot, ETFs & Favoriten)",
            options=preset_options,
            index=0,
            key="preset_selector",
            on_change=on_preset_change,
        )

        raw_query = st.text_input(
            "🔍 Freie Suche: Firmenname, ISIN, ETF oder Ticker",
            key="search_query_input",
            placeholder="z.B. DE000BAY0017, Bayer, MSCI World, AAPL...",
            help="Gib einfach eine ISIN (z.B. DE000BAY0017, IE00B4L5Y983), einen Unternehmens-/ETF-Namen (z.B. Bayer, MSCI World, Vanguard) oder einen Ticker ein und drücke Enter.",
        )

        # Live-Suchergebnisse anzeigen, wenn nach Name, ETF oder ISIN gesucht wird
        custom_query = raw_query.strip()
        if len(custom_query) >= 2:
            matches = cached_search_tickers(custom_query)
            if len(matches) > 1:
                match_labels = []
                match_map = {}
                for m in matches:
                    type_badge = "📦 ETF" if m["type"] in ("ETF", "MUTUALFUND") else "🏢 Aktie"
                    lbl = f"{type_badge}: {m['name']} ({m['symbol']}) – {m['exchange']}"
                    match_labels.append(lbl)
                    match_map[lbl] = m["symbol"]
                chosen_match = st.selectbox(
                    f"Gefundene Treffer für '{custom_query}' ({len(matches)}):",
                    options=match_labels,
                    index=0,
                    help="Wähle hier das gewünschte Wertpapier aus den Suchtreffern aus.",
                )
                custom_query = match_map[chosen_match]
            elif len(matches) == 1:
                m = matches[0]
                st.caption(f"✅ Gefunden: **{m['name']}** (`{m['symbol']}` • {m['type']})")
                custom_query = m["symbol"]

        exchange_options = {
            ".MU": "🌙 München / gettex (.MU) – Abendhandel bis 22 Uhr",
            ".SG": "🌙 Börse Stuttgart (.SG) – Abendhandel bis 22 Uhr",
            ".DU": "🌙 Börse Düsseldorf / Quotrix (.DU) – Abendhandel",
            ".F": "🏛️ Börse Frankfurt Parkett (.F) – bis 20 Uhr",
            ".DE": "☀️ XETRA (.DE) – Haupthandelsplatz (09:00–17:30 Uhr)",
            "AUTO": "⚙️ Standard / Automatisch (wie eingegeben)",
        }
        selected_exchange = st.selectbox(
            "Handelsplatz für deutsche Aktien",
            options=list(exchange_options.keys()),
            format_func=lambda k: exchange_options[k],
            index=0,
            help="XETRA (.DE) schließt um 17:30 Uhr. Für aktuelle Abendkurse (wie auf Onvista/gettex) wähle München/gettex (.MU) oder Stuttgart (.SG).",
        )

        hist_period = st.selectbox(
            "Historischer Analyse-Zeitraum",
            options=["1y", "2y", "5y"],
            format_func=lambda x: {"1y": "1 Jahr", "2y": "2 Jahre (Empfohlen)", "5y": "5 Jahre"}[x],
            index=1,
        )

        st.divider()
        st.subheader("🔮 Szenario- & Simulations-Regler")

        horizon_label = st.select_slider(
            "Simulations-Horizont in die Zukunft",
            options=["1 Monat (21T)", "3 Monate (63T)", "6 Monate (126T)", "1 Jahr (252T)", "2 Jahre (504T)"],
            value="6 Monate (126T)",
        )
        horizon_days = {
            "1 Monat (21T)": 21,
            "3 Monate (63T)": 63,
            "6 Monate (126T)": 126,
            "1 Jahr (252T)": 252,
            "2 Jahre (504T)": 504,
        }[horizon_label]

        scenario_mode = st.radio(
            "Markt-Szenario Modus",
            options=[
                "⚖️ Automatisch (Aus Trend & Analysten)",
                "🐂 Optimistisch (Bull-Markt / Rückenwind)",
                "🐻 Pessimistisch (Rezession / Gegenwind)",
                "🛠️ Eigene Parameter einstellen",
            ],
            index=0,
        )

        custom_drift = None
        vol_mult = 1.0
        shock_pct = 0.0

        if scenario_mode == "🐂 Optimistisch (Bull-Markt / Rückenwind)":
            custom_drift = 22.0
            vol_mult = 0.90
        elif scenario_mode == "🐻 Pessimistisch (Rezession / Gegenwind)":
            custom_drift = -15.0
            vol_mult = 1.35
            shock_pct = -5.0
        elif scenario_mode == "🛠️ Eigene Parameter einstellen":
            custom_drift = st.slider("Erwartete Jahresrendite / Drift (% p.a.)", -40.0, 60.0, 10.0, 1.0)
            vol_mult = st.slider("Volatilitäts-Multiplikator (Stressfaktor)", 0.5, 2.5, 1.0, 0.1)
            shock_pct = st.slider("Sofortiger Marktschock / Gap zum Start (%)", -30.0, 20.0, 0.0, 1.0)

        st.divider()
        st.subheader("📐 Chart-Methoden einblenden")
        show_bb = st.checkbox("Bollinger Bänder (20, 2σ)", value=True)
        show_reg = st.checkbox("Linearer Regressions-Trendkanal", value=True)
        show_sr = st.checkbox("Support & Resistance Zonen", value=True)
        show_fib = st.checkbox("Fibonacci Retracements (52W)", value=False)

    # --- DATEN LADEN & ANALYSIEREN ---
    with st.spinner(f"Analysiere Marktdaten, Chartmuster und Risikoprofil für '{custom_query}'..."):
        try:
            stock_bundle = cached_fetch_stock(custom_query, hist_period, selected_exchange)
        except Exception as e:
            st.error(f"❌ Konnte Daten für **'{custom_query}'** nicht abrufen: {e}")
            st.info("Tipp: Versuche das offizielle Tickersymbol (z. B. `AAPL`, `SAP.DE`, `NVDA`) oder eine gültige ISIN einzugeben.")
            return

        symbol = stock_bundle["symbol"]
        df_hist = stock_bundle["history"]
        info = stock_bundle["info"]

        company_name = info.get("longName") or info.get("shortName") or symbol
        currency = info.get("currency", "EUR")
        sector = info.get("sector", "Unbekannter Sektor")
        industry = info.get("industry", "")

        tech_data = calculate_technical_indicators(df_hist)
        risk_data = evaluate_risk_and_rating(df_hist, info)
        sim_data = simulate_future_scenarios(
            df_hist,
            tech_data,
            risk_data,
            horizon_days=horizon_days,
            num_simulations=500,
            custom_drift_override_pct=custom_drift,
            volatility_multiplier=vol_mult,
            shock_pct=shock_pct,
        )
        advisory = generate_advisory_report(symbol, info, tech_data, risk_data, sim_data)

    # --- KOPFZEILE ---
    curr_price = tech_data["current_price"]
    prev_close = float(df_hist["Close"].iloc[-2]) if len(df_hist) > 1 else curr_price
    day_change_pct = (curr_price / prev_close - 1.0) * 100.0
    last_bar_date = df_hist.index[-1].strftime("%d.%m.%Y")

    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.title(f"📊 {company_name} (`{symbol}`)")
        st.caption(
            f"Sektor: **{sector}** {f'• Branche: **{industry}**' if industry else ''} "
            f"• Währung: **{currency}** • Letzter Kursdatenpunkt: **{last_bar_date}** (Quelle: Yahoo Finance Live API)"
        )
    with head_col2:
        st.metric(
            label="Aktueller Marktpreis",
            value=f"{curr_price:.2f} {currency}",
            delta=f"{day_change_pct:+.2f}% (letzter Handelstag)",
        )

    # Top KPI-Zeile
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric(
        "Qualitäts- & Risiko-Rating",
        f"{risk_data['rating_grade']} ({risk_data['rating_score']:.0f}/100)",
        risk_data["risk_class"],
        delta_color="off",
    )
    kpi2.metric(
        "Technischer Trend-Score",
        f"{tech_data['tech_score']} / 100",
        "Bullisch" if tech_data["tech_score"] >= 55 else ("Bärisch" if tech_data["tech_score"] <= 45 else "Neutral"),
        delta_color="normal" if tech_data["tech_score"] >= 55 else ("inverse" if tech_data["tech_score"] <= 45 else "off"),
    )
    kpi3.metric(
        f"Simulations-Median ({horizon_label})",
        f"{sim_data['summary']['base_price']:.2f} {currency}",
        f"{sim_data['summary']['base_return_pct']:+.1f}% erwartet",
    )
    kpi4.metric(
        "Gewinn-Wahrscheinlichkeit",
        f"{sim_data['summary']['prob_profit_pct']:.1f}%",
        f"über {horizon_days} Handelstage",
        delta_color="off",
    )
    analyst_target = risk_data["analyst_consensus"]["target_mean"]
    if analyst_target:
        upside = (analyst_target / curr_price - 1.0) * 100.0
        kpi5.metric(
            "Ø Analysten-Kursziel",
            f"{analyst_target:.2f} {currency}",
            f"{upside:+.1f}% ({risk_data['analyst_consensus']['num_analysts']} Analysten)",
        )
    else:
        kpi5.metric("52-Wochen-Spanne", f"{tech_data['low_52w']:.1f} – {tech_data['high_52w']:.1f}", currency, delta_color="off")

    st.divider()

    # --- HAUPT-TABS (inkl. iPhone Kompakt-Überblick als 1. Reiter) ---
    tab_mobile, tab_sim, tab_tech, tab_risk, tab_adv = st.tabs([
        "📱 iPhone Kompakt-Check",
        "🔮 Zukunfts-Simulation & Szenarien",
        "📐 Chart-Methoden & Technische Analyse",
        "🛡️ AAA Risiko-Rating & Fundamentaldaten",
        "🧭 KI-Strategieberater & Handlungsplan",
    ])

    # =========================================================================
    # TAB 0: IPHONE KOMPAKT-CHECK (Alles auf einer Karte für unterwegs)
    # =========================================================================
    with tab_mobile:
        st.markdown(
            f"""
            <div style="border-radius: 14px; padding: 18px 20px; background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid rgba(148,163,184,0.2); margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div>
                        <div style="font-size: 0.8rem; opacity: 0.75; text-transform: uppercase;">Executive Summary • {symbol}</div>
                        <div style="font-size: 1.45rem; font-weight: 800; color: {advisory['verdict_color']};">{advisory['verdict']}</div>
                    </div>
                    <div style="background: {risk_data['rating_color']}; color: #fff; padding: 6px 14px; border-radius: 10px; font-weight: 800; font-size: 1.25rem;">
                        Rating: {risk_data['rating_grade']} ({risk_data['rating_score']:.0f}/100)
                    </div>
                </div>
                <p style="margin: 10px 0 0 0; font-size: 0.96rem; opacity: 0.92;">{advisory['summary_text']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Kompakte 2x2 / 3er Übersicht für schmale Displays
        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            st.info(
                f"**🔮 Simulation ({horizon_label})**\n\n"
                f"• 🐂 Bull (90%): **{sim_data['summary']['bull_price']:.2f} {currency}** ({sim_data['summary']['bull_return_pct']:+.1f}%)\n"
                f"• ⚖️ Median (50%): **{sim_data['summary']['base_price']:.2f} {currency}** ({sim_data['summary']['base_return_pct']:+.1f}%)\n"
                f"• 🐻 Bear (10%): **{sim_data['summary']['bear_price']:.2f} {currency}** ({sim_data['summary']['bear_return_pct']:+.1f}%)\n"
                f"• 🎲 Gewinn-Chance: **{sim_data['summary']['prob_profit_pct']:.1f}%**"
            )
        with m_c2:
            tl = advisory["tactical_levels"]
            st.success(
                f"**🎯 Taktische Handelsmarken**\n\n"
                f"• 🟢 Einstiegszone: **{tl['entry_zone']} {currency}**\n"
                f"• 🚧 1. Widerstand: **{tl['first_resistance']} {currency}**\n"
                f"• 🛑 Stop-Loss (2x ATR): **{tl['atr_stop_loss']} {currency}**\n"
                f"• 🎯 Analysten-Ziel: **{tl['analyst_target']}**"
            )
        with m_c3:
            m = risk_data["metrics"]
            st.warning(
                f"**🛡️ Risiko- & Trend-Check**\n\n"
                f"• 📐 Technik-Score: **{tech_data['tech_score']}/100** (RSI: {tech_data['rsi']:.1f})\n"
                f"• 📏 SMA 200: **{tech_data['sma200']:.2f} {currency}**\n"
                f"• 📉 Volatilität: **{m['annual_volatility_pct']:.1f}% p.a.**\n"
                f"• 🌊 Max Drawdown: **{m['max_drawdown_pct']:.1f}%** (VaR 95%: {m['var_95_daily_pct']:.1f}%)"
            )

        st.markdown("##### 📈 Kompakter Simulations- & Trend-Chart")
        st.plotly_chart(
            build_simulation_chart(df_hist, sim_data, risk_data, symbol, currency),
            use_container_width=True,
            key="mobile_sim_chart",
        )

        # Wichtigste Stärken & Risiken direkt untereinander
        mc_s, mc_r = st.columns(2)
        with mc_s:
            st.markdown("**✅ Wichtigste Stärken:**")
            for s in advisory["strengths"][:3]:
                st.markdown(f"- 🟢 {s}")
        with mc_r:
            st.markdown("**⚠️ Wichtigste Risiken:**")
            for r in advisory["risks"][:3]:
                st.markdown(f"- 🔴 {r}")

    # =========================================================================
    # TAB 1: ZUKUNFTS-SIMULATION & SZENARIEN
    # =========================================================================
    with tab_sim:
        st.subheader(f"🔮 Zukunfts-Simulation für {symbol} ({sim_data['horizon_days']} Handelstage Projektion)")
        st.plotly_chart(
            build_simulation_chart(df_hist, sim_data, risk_data, symbol, currency),
            use_container_width=True,
        )

        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        with s_col1:
            st.success(
                f"**🐂 Bull-Case (90. Perzentil)**\n\n"
                f"Kursziel: **{sim_data['summary']['bull_price']:.2f} {currency}**\n\n"
                f" Veränderung: **{sim_data['summary']['bull_return_pct']:+.1f}%**"
            )
        with s_col2:
            st.info(
                f"**⚖️ Base-Case (Median-Pfad)**\n\n"
                f"Kursziel: **{sim_data['summary']['base_price']:.2f} {currency}**\n\n"
                f"Veränderung: **{sim_data['summary']['base_return_pct']:+.1f}%**"
            )
        with s_col3:
            st.error(
                f"**🐻 Bear-Case (10. Perzentil)**\n\n"
                f"Kursziel: **{sim_data['summary']['bear_price']:.2f} {currency}**\n\n"
                f"Veränderung: **{sim_data['summary']['bear_return_pct']:+.1f}%**"
            )
        with s_col4:
            st.warning(
                f"**🎲 Wahrscheinlichkeits-Profil**\n\n"
                f"• Kurs im Plus: **{sim_data['summary']['prob_profit_pct']:.1f}%**\n"
                f"• Rendite ≥ +10%: **{sim_data['summary']['prob_gain_10_pct']:.1f}%**\n"
                f"• Verlust ≤ -10%: **{sim_data['summary']['prob_loss_10_pct']:.1f}%**"
            )

        with st.expander("📊 Verteilung der Endkurse am Ende des Simulationszeitraums (Histogramm)", expanded=False):
            hist_fig = go.Figure()
            hist_fig.add_trace(
                go.Histogram(
                    x=sim_data["final_prices"],
                    nbinsx=45,
                    marker_color="#3b82f6",
                    opacity=0.8,
                    name="Endkurse",
                )
            )
            hist_fig.add_vline(x=curr_price, line_dash="dash", line_color="#e2e8f0", annotation_text="Aktueller Kurs")
            hist_fig.add_vline(x=sim_data["summary"]["base_price"], line_dash="solid", line_color="#10b981", annotation_text="Median-Ziel")
            hist_fig.update_layout(
                height=320,
                template="plotly_dark",
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis_title=f"Simulierter Endkurs nach {horizon_days} Handelstagen ({currency})",
                yaxis_title="Anzahl Pfade",
            )
            st.plotly_chart(hist_fig, use_container_width=True)
            st.caption(
                f"Simulations-Parameter: Angenommener Drift = **{sim_data['base_annual_drift_pct']:+.1f}% p.a.**, "
                f"simulierte Jahresvolatilität = **{sim_data['sim_annual_vol_pct']:.1f}% p.a.** (500 Monte-Carlo-Pfade)."
            )

    # =========================================================================
    # TAB 2: CHART-METHODEN & TECHNISCHE ANALYSE
    # =========================================================================
    with tab_tech:
        st.subheader(f"📐 {symbol} – Kursverlauf, Trendkanal & Indikatoren ({currency})")
        st.plotly_chart(
            build_technical_chart(tech_data["df"], tech_data, symbol, currency, show_bb, show_reg, show_fib, show_sr),
            use_container_width=True,
        )

        t_col1, t_col2 = st.columns([3, 2])
        with t_col1:
            st.subheader("📡 Aktuelle Indikator-Signale")
            for sig in tech_data["signals"]:
                badge_map = {
                    "green": "🟢",
                    "red": "🔴",
                    "orange": "🟠",
                    "blue": "🔵",
                }
                icon = badge_map.get(sig["color"], "⚪")
                st.markdown(f"**{icon} {sig['indicator']} — {sig['status']}**  \n{sig['detail']}")

        with t_col2:
            st.subheader("🧱 Schlüsselmarken & Fibonacci (52W)")
            sr_df = pd.DataFrame(
                [
                    {"Typ": "🔴 Widerstand (R)", "Preis": f"{r:.2f} {currency}", "Abstand": f"{(r / curr_price - 1) * 100:+.1f}%"}
                    for r in reversed(tech_data["resistances"])
                ]
                + [{"Typ": "⚪ Aktueller Kurs", "Preis": f"{curr_price:.2f} {currency}", "Abstand": "0.0%"}]
                + [
                    {"Typ": "🟢 Unterstützung (S)", "Preis": f"{s:.2f} {currency}", "Abstand": f"{(s / curr_price - 1) * 100:+.1f}%"}
                    for s in tech_data["supports"]
                ]
            )
            st.dataframe(sr_df, use_container_width=True, hide_index=True)

            fib_rows = [
                {"Fibonacci Level": k, "Kursmarke": f"{v:.2f} {currency}", "Abstand": f"{(v / curr_price - 1) * 100:+.1f}%"}
                for k, v in tech_data["fibonacci_levels"].items()
            ]
            st.dataframe(pd.DataFrame(fib_rows), use_container_width=True, hide_index=True)

    # =========================================================================
    # TAB 3: AAA RISIKO-RATING & FUNDAMENTALDATEN
    # =========================================================================
    with tab_risk:
        r_col1, r_col2 = st.columns([2, 3])

        with r_col1:
            st.markdown(
                f"""
                <div class="rating-card" style="background: linear-gradient(135deg, {risk_data['rating_color']}dd, {risk_data['rating_color']}88);">
                    <div style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1.5px;">Synthetisches Qualitäts- & Bonitäts-Rating</div>
                    <div class="rating-grade">{risk_data['rating_grade']} <span style="font-size: 1.2rem; font-weight: 500;">({risk_data['rating_score']:.1f} / 100 Punkte)</span></div>
                    <div class="rating-sub"><b>{risk_data['risk_class']}</b> — {risk_data['rating_label']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.subheader("🏛️ Die 4 Säulen des Ratings")
            for pillar in risk_data["pillars"]:
                st.progress(int(pillar["score"]), text=f"**{pillar['name']}**: {pillar['score']}/100 — *{pillar['details']}*")

        with r_col2:
            st.subheader("📉 Quantitative Risiko- & Bilanzkennzahlen")
            m = risk_data["metrics"]
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Jahres-Volatilität", f"{m['annual_volatility_pct']:.1f}%")
            m_col2.metric("Max. Drawdown (Historie)", f"{m['max_drawdown_pct']:.1f}%")
            m_col3.metric("Aktueller Drawdown vom Hoch", f"{m['current_drawdown_pct']:.1f}%")

            m_col4, m_col5, m_col6 = st.columns(3)
            m_col4.metric("Value at Risk (95%, 1 Tag)", f"{m['var_95_daily_pct']:.2f}%", help="Mit 95% Sicherheit übersteigt der Tagesverlust diesen Wert nicht.")
            m_col5.metric("Value at Risk (95%, 1 Monat)", f"{m['var_95_monthly_pct']:.1f}%")
            m_col6.metric("Sharpe Ratio / Sortino", f"{m['sharpe_ratio']:.2f} / {m['sortino_ratio']:.2f}")

            st.divider()
            st.markdown("##### 🧾 Fundamentale Bilanz- & Bewertungsdaten (Yahoo Finance)")
            fund_table = pd.DataFrame(
                [
                    {"Kennzahl": "Marktkapitalisierung", "Wert": format_large_number(m["market_cap"]), "Kennzahl 2": "Beta-Faktor (Marktsensitivität)", "Wert 2": f"{m['beta']:.2f}" if m["beta"] is not None else "—"},
                    {"Kennzahl": "KGV (Trailing / Forward PE)", "Wert": f"{m['trailing_pe'] or '—'} / {m['forward_pe'] or '—'}", "Kennzahl 2": "Verschuldungsgrad (Debt/Equity)", "Wert 2": f"{m['debt_to_equity']:.1f}%" if m["debt_to_equity"] is not None else "—"},
                    {"Kennzahl": "Nettomarge (Profit Margin)", "Wert": f"{m['profit_margin_pct']:.1f}%" if m["profit_margin_pct"] is not None else "—", "Kennzahl 2": "Liquiditätsgrad (Current Ratio)", "Wert 2": f"{m['current_ratio']:.2f}" if m["current_ratio"] is not None else "—"},
                    {"Kennzahl": "Eigenkapitalrendite (ROE)", "Wert": f"{m['roe_pct']:.1f}%" if m["roe_pct"] is not None else "—", "Kennzahl 2": "Free Cashflow", "Wert 2": format_large_number(m["free_cashflow"])},
                    {"Kennzahl": "Barbestand (Total Cash)", "Wert": format_large_number(m["total_cash"]), "Kennzahl 2": "Gesamtverschuldung (Total Debt)", "Wert 2": format_large_number(m["total_debt"])},
                ]
            )
            st.dataframe(fund_table, use_container_width=True, hide_index=True)

        # Drawdown-Verlauf (Underwater-Chart)
        st.subheader("🌊 Historischer Drawdown-Verlauf (Underwater-Chart)")
        dd_fig = go.Figure()
        dd_fig.add_trace(
            go.Scatter(
                x=risk_data["drawdown_series"].index,
                y=risk_data["drawdown_series"].values,
                fill="tozeroy",
                line=dict(color="#ef4444", width=1.5),
                fillcolor="rgba(239, 68, 68, 0.25)",
                name="Drawdown (%)",
            )
        )
        dd_fig.update_layout(
            height=270,
            template="plotly_dark",
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis_title="Rückgang vom Hoch (%)",
        )
        st.plotly_chart(dd_fig, use_container_width=True)

    # =========================================================================
    # TAB 4: STRATEGIEBERATER & HANDLUNGSPLAN
    # =========================================================================
    with tab_adv:
        st.markdown(
            f"""
            <div class="advisory-box" style="border-left-color: {advisory['verdict_color']};">
                <div style="font-size: 0.85rem; text-transform: uppercase; opacity: 0.8;">Gesamturteil (Composite Score: {advisory['composite_score']} / 100)</div>
                <div style="font-size: 1.7rem; font-weight: 800; color: {advisory['verdict_color']}; margin: 4px 0;">{advisory['verdict']}</div>
                <div style="font-size: 1.05rem;">{advisory['summary_text']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        adv_c1, adv_c2 = st.columns(2)
        with adv_c1:
            st.subheader("✅ Stärken & Kurstreiber")
            if advisory["strengths"]:
                for s in advisory["strengths"]:
                    st.markdown(f"- 🟢 {s}")
            else:
                st.write("Aktuell keine ausgeprägten positiven Treiber identifiziert.")

        with adv_c2:
            st.subheader("⚠️ Risiken & Warnsignale")
            if advisory["risks"]:
                for r in advisory["risks"]:
                    st.markdown(f"- 🔴 {r}")
            else:
                st.write("Aktuell keine akuten Warnsignale identifiziert.")

        st.divider()
        st.subheader("🎯 Taktische Orientierungsmarken für Szenario-Planung")
        tl = advisory["tactical_levels"]
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.info(f"**Ideale Einstiegs-/Nachkaufzone**\n\n{tl['entry_zone']} {currency}")
        tc2.warning(f"**Nächster Chart-Widerstand**\n\n{tl['first_resistance']} {currency}")
        tc3.error(f"**Volatilitäts-Stop-Loss (2x ATR)**\n\n{tl['atr_stop_loss']} {currency}")
        tc4.success(f"**Analysten-Konsensziel**\n\n{tl['analyst_target']}")

        st.caption(
            "Hinweis: Dieses Dashboard dient ausschließlich der quantitativen Simulation, Chartanalyse und Informationsbündelung "
            "und stellt keine Anlageberatung im Sinne des WpHG dar."
        )


if __name__ == "__main__":
    main()
