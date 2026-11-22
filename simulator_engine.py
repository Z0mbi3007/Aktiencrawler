import json
import logging
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import requests
import yfinance as yf
import config

logger = logging.getLogger("SimulatorEngine")

# Bekannte ISIN -> Ticker Zuordnungen als schneller Cache/Fallback (Aktien & beliebte ETFs)
KNOWN_ISIN_MAP = {
    # Aktien
    "US0378331005": "AAPL",
    "US5949181045": "MSFT",
    "US67066G1040": "NVDA",
    "US88160R1014": "TSLA",
    "US02079K3059": "GOOGL",
    "US0231351067": "AMZN",
    "US30303M1027": "META",
    "DE0007164600": "SAP.DE",
    "DE0007236101": "SIE.DE",
    "DE0008404005": "ALV.DE",
    "DE0007030009": "RHM.DE",
    "DE000A1EWWW0": "ADS.DE",
    "DE000BAY0017": "BAYN.DE",
    "DE000BASF111": "BAS.DE",
    "DE0005557508": "DTE.DE",
    "DE0007100000": "MBG.DE",
    "DE0005190003": "BMW.DE",
    "DE0007664039": "VOW3.DE",
    "DE0008430026": "MUV2.DE",
    "DE000ENAG999": "EOAN.DE",
    "DE0005810055": "DB1.DE",
    "DE0005140008": "DBK.DE",
    "DE000CBK1001": "CBK.DE",
    "DE0006231004": "IFX.DE",
    "NL0010273215": "ASML.AS",
    "US0079031078": "AMD",
    "US11135F1012": "AVGO",
    "US64110L1061": "NFLX",
    "US69608A1088": "PLTR",
    # Beliebte ETFs
    "IE00B4L5Y983": "EUNL.DE",  # iShares Core MSCI World UCITS ETF
    "IE00B3RBWM25": "VGWL.DE",  # Vanguard FTSE All-World (Dist)
    "IE00BK5BQT80": "VWCE.DE",  # Vanguard FTSE All-World (Acc)
    "IE00B5BMR087": "SXR8.DE",  # iShares Core S&P 500 UCITS ETF
    "IE00B4L5YC18": "IS3N.DE",  # iShares Core MSCI EM IMI UCITS ETF
    "DE0005933931": "EXS1.DE",  # iShares Core DAX UCITS ETF
    "IE00B53SZB19": "SXRV.DE",  # iShares NASDAQ 100 UCITS ETF
    "LU0290358497": "XEON.DE",  # Xtrackers II EUR Overnight Rate Swap
    "DE000A0H08M3": "EXXT.DE",  # iShares NASDAQ-100 UCITS ETF (DE)
    # Rohstoff-ETCs (Gold & Silber)
    "DE000A0S9GB0": "4GLD.DE",  # Xetra-Gold ETC
    "DE000EWG2LD7": "EWG2.DE",  # EUWAX Gold II ETC
    "IE00B4ND3602": "PPFB.DE",  # iShares Physical Gold ETC
    "IE00B4NCWG09": "PPFD.DE",  # iShares Physical Silver ETC
}

# Deutsche & englische Suchbegriffe für Rohstoffe (Futures & physische ETCs)
KNOWN_COMMODITIES: Dict[str, List[Dict[str, str]]] = {
    "gold": [
        {"symbol": "GC=F", "name": "Gold (Weltmarkt-Future, Feinunze)", "exchange": "COMEX", "type": "FUTURE"},
        {"symbol": "4GLD.DE", "name": "Xetra-Gold ETC (DE000A0S9GB0, physisch hinterlegt)", "exchange": "XETRA", "type": "ETF"},
        {"symbol": "EWG2.DE", "name": "EUWAX Gold II ETC (DE000EWG2LD7)", "exchange": "XETRA", "type": "ETF"},
        {"symbol": "PPFB.DE", "name": "iShares Physical Gold ETC (IE00B4ND3602)", "exchange": "XETRA", "type": "ETF"},
    ],
    "xetra gold": [
        {"symbol": "4GLD.DE", "name": "Xetra-Gold ETC (DE000A0S9GB0)", "exchange": "XETRA", "type": "ETF"},
    ],
    "euwax gold": [
        {"symbol": "EWG2.DE", "name": "EUWAX Gold II ETC (DE000EWG2LD7)", "exchange": "XETRA", "type": "ETF"},
    ],
    "silber": [
        {"symbol": "SI=F", "name": "Silber (Weltmarkt-Future, Feinunze)", "exchange": "COMEX", "type": "FUTURE"},
        {"symbol": "PPFD.DE", "name": "iShares Physical Silver ETC (IE00B4NCWG09)", "exchange": "XETRA", "type": "ETF"},
    ],
    "silver": [
        {"symbol": "SI=F", "name": "Silber (Weltmarkt-Future, Feinunze)", "exchange": "COMEX", "type": "FUTURE"},
        {"symbol": "PPFD.DE", "name": "iShares Physical Silver ETC (IE00B4NCWG09)", "exchange": "XETRA", "type": "ETF"},
    ],
    "öl": [
        {"symbol": "BZ=F", "name": "Brent Rohöl (Nordsee-Referenzpreis, Barrel)", "exchange": "ICE / NYMEX", "type": "FUTURE"},
        {"symbol": "CL=F", "name": "WTI Rohöl (US-Referenzpreis, Barrel)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "oel": [
        {"symbol": "BZ=F", "name": "Brent Rohöl (Nordsee-Referenzpreis, Barrel)", "exchange": "ICE / NYMEX", "type": "FUTURE"},
        {"symbol": "CL=F", "name": "WTI Rohöl (US-Referenzpreis, Barrel)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "rohöl": [
        {"symbol": "BZ=F", "name": "Brent Rohöl (Nordsee-Referenzpreis, Barrel)", "exchange": "ICE / NYMEX", "type": "FUTURE"},
        {"symbol": "CL=F", "name": "WTI Rohöl (US-Referenzpreis, Barrel)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "brent": [
        {"symbol": "BZ=F", "name": "Brent Rohöl (Nordsee-Referenzpreis, Barrel)", "exchange": "ICE / NYMEX", "type": "FUTURE"},
    ],
    "wti": [
        {"symbol": "CL=F", "name": "WTI Rohöl (US-Referenzpreis, Barrel)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "kupfer": [
        {"symbol": "HG=F", "name": "Kupfer (Weltmarkt-Future)", "exchange": "COMEX", "type": "FUTURE"},
    ],
    "copper": [
        {"symbol": "HG=F", "name": "Kupfer (Weltmarkt-Future)", "exchange": "COMEX", "type": "FUTURE"},
    ],
    "platin": [
        {"symbol": "PL=F", "name": "Platin (Weltmarkt-Future, Feinunze)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "platinum": [
        {"symbol": "PL=F", "name": "Platin (Weltmarkt-Future, Feinunze)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "palladium": [
        {"symbol": "PA=F", "name": "Palladium (Weltmarkt-Future, Feinunze)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "erdgas": [
        {"symbol": "NG=F", "name": "Erdgas / Natural Gas (Henry Hub Future)", "exchange": "NYMEX", "type": "FUTURE"},
    ],
    "weizen": [
        {"symbol": "ZW=F", "name": "Weizen (CBOT Future)", "exchange": "CBOT", "type": "FUTURE"},
    ],
    "kaffee": [
        {"symbol": "KC=F", "name": "Kaffee Arabica (ICE Future)", "exchange": "ICE", "type": "FUTURE"},
    ],
    "kakao": [
        {"symbol": "CC=F", "name": "Kakao (ICE Future)", "exchange": "ICE", "type": "FUTURE"},
    ],
}

OPENFIGI_EXCH_TO_YAHOO = {
    "GR": ".DE",
    "GY": ".DE",
    "GF": ".F",
    "GM": ".MU",
    "GS": ".SG",
    "GD": ".DU",
    "GH": ".HM",
    "US": "",
    "UW": "",
    "UN": "",
    "UA": "",
    "LN": ".L",
    "NA": ".AS",
    "FP": ".PA",
    "IM": ".MI",
    "SW": ".SW",
    "VX": ".SW",
}


def _lookup_isin_via_openfigi(isin: str) -> List[Dict[str, str]]:
    """
    Fragt die kostenlose OpenFIGI-API ab, um eine ISIN (Aktie oder ETF)
    in offizielle Börsenticker (bevorzugt XETRA/Deutschland, sonst US/London/Amsterdam) aufzulösen.
    """
    try:
        resp = requests.post(
            "https://api.openfigi.com/v3/mapping",
            json=[{"idType": "ID_ISIN", "idValue": isin.strip().upper()}],
            headers={"Content-Type": "application/json"},
            timeout=6,
        )
        if resp.status_code == 200:
            payload = resp.json()
            if payload and isinstance(payload, list) and "data" in payload[0]:
                items = payload[0]["data"]
                results = []
                seen = set()
                # Sortiere so, dass deutsche/europäische/US Hauptbörsen zuerst kommen
                priority_order = ["GY", "GR", "GF", "GM", "GS", "UW", "UN", "US", "NA", "LN", "FP", "IM", "SW"]
                items_sorted = sorted(
                    items,
                    key=lambda x: priority_order.index(x.get("exchCode", "")) if x.get("exchCode", "") in priority_order else 99,
                )
                for item in items_sorted:
                    exch = item.get("exchCode", "")
                    ticker = item.get("ticker", "")
                    if not ticker or exch not in OPENFIGI_EXCH_TO_YAHOO:
                        continue
                    # OpenFIGI liefert für manche deutsche ETFs z.B. DAXEX statt EXS1, daher prüfen wir später die Gültigkeit
                    suffix = OPENFIGI_EXCH_TO_YAHOO[exch]
                    yf_sym = f"{ticker}{suffix}"
                    if yf_sym not in seen:
                        seen.add(yf_sym)
                        sec_type = "ETF" if item.get("securityType") in ("ETP", "ETF", "Open-End Fund") else "EQUITY"
                        results.append({
                            "symbol": yf_sym,
                            "name": item.get("name") or yf_sym,
                            "exchange": exch,
                            "type": sec_type,
                        })
                return results
    except Exception as e:
        logger.warning(f"OpenFIGI ISIN-Lookup für {isin} fehlgeschlagen: {e}")
    return []


def search_tickers(query: str) -> List[Dict[str, str]]:
    """
    Sucht passende Aktien, ETFs und Indizes über Yahoo Finance (und OpenFIGI bei ISINs)
    und gibt eine Liste mit Symbol, Name, Börse und Typ zurück.
    """
    if not query or len(query.strip()) < 2:
        return []
    q = query.strip()
    q_upper = q.upper()
    results: List[Dict[str, str]] = []
    seen_symbols = set()

    # 1. Prüfen ob bekannte ISIN oder Rohstoff-Suchbegriff (Gold, Silber, Öl, Kupfer, etc.)
    if q_upper in KNOWN_ISIN_MAP:
        sym = KNOWN_ISIN_MAP[q_upper]
        results.append({
            "symbol": sym,
            "name": f"{sym} (ISIN: {q_upper})",
            "exchange": "Haupthandelsplatz",
            "type": "ETF / Aktie",
        })
        seen_symbols.add(sym)

    q_lower = q.lower()
    if q_lower in KNOWN_COMMODITIES:
        for item in KNOWN_COMMODITIES[q_lower]:
            if item["symbol"] not in seen_symbols:
                seen_symbols.add(item["symbol"])
                results.append(dict(item))

    # 2. Suche über Yahoo Finance Search API
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        resp = requests.get(
            url,
            params={"q": q, "quotesCount": 12, "newsCount": 0},
            headers=headers,
            timeout=8,
        )
        if resp.status_code == 200:
            quotes = resp.json().get("quotes", [])
            for item in quotes:
                q_type = item.get("quoteType", "")
                sym = item.get("symbol", "")
                if sym and sym not in seen_symbols and q_type in ("EQUITY", "ETF", "MUTUALFUND", "INDEX", "CRYPTOCURRENCY", "FUTURE"):
                    seen_symbols.add(sym)
                    results.append({
                        "symbol": sym,
                        "name": item.get("longname") or item.get("shortname") or sym,
                        "exchange": item.get("exchDisp") or item.get("exchange", ""),
                        "type": q_type,
                    })
    except Exception as e:
        logger.warning(f"Yahoo Ticker-Suche fehlgeschlagen: {e}")

    # 3. Fallback über yfinance.Search falls HTTP-Aufruf leer war
    if not results:
        try:
            yf_search = yf.Search(q, max_results=10)
            for item in getattr(yf_search, "quotes", []) or []:
                sym = item.get("symbol", "")
                q_type = item.get("quoteType", "EQUITY")
                if sym and sym not in seen_symbols:
                    seen_symbols.add(sym)
                    results.append({
                        "symbol": sym,
                        "name": item.get("longname") or item.get("shortname") or sym,
                        "exchange": item.get("exchDisp") or item.get("exchange", ""),
                        "type": q_type,
                    })
        except Exception as e:
            logger.warning(f"yfinance.Search Fallback fehlgeschlagen: {e}")

    # 4. Falls Eingabe wie eine ISIN aussieht (12 Zeichen, z.B. DE000BAY0017) und noch nichts gefunden wurde: OpenFIGI
    is_isin = len(q_upper) == 12 and q_upper[:2].isalpha() and q_upper[2:11].isalnum()
    if is_isin and not results:
        figi_results = _lookup_isin_via_openfigi(q_upper)
        for item in figi_results:
            if item["symbol"] not in seen_symbols:
                seen_symbols.add(item["symbol"])
                results.append(item)

    return results


def resolve_query_to_ticker(query: str) -> str:
    """
    Löst einen Ticker, eine ISIN (z.B. DE000BAY0017, IE00B4L5Y983) oder einen Firmen-/ETF-Namen
    (z.B. 'Bayer', 'MSCI World', 'Rheinmetall') intelligent in das passende Yahoo-Finance-Tickersymbol auf.
    """
    q = query.strip()
    q_upper = q.upper()
    if not q_upper:
        return "AAPL"

    if q_upper in KNOWN_ISIN_MAP:
        return KNOWN_ISIN_MAP[q_upper]

    if q.lower() in KNOWN_COMMODITIES:
        return KNOWN_COMMODITIES[q.lower()][0]["symbol"]

    is_isin = len(q_upper) == 12 and q_upper[:2].isalpha() and q_upper[2:11].isalnum()

    # Wenn es ein expliziter Börsenticker mit Punkt/Bindestrich/Gleichheitszeichen ist (z.B. BAYN.DE, RHM.MU, BTC-USD, GC=F, MGC=F)
    # oder ein kurzes Großbuchstaben-Kürzel (1-4 Buchstaben wie AAPL, NVDA, SAP):
    looks_like_explicit_ticker = (
        not is_isin
        and " " not in q
        and ("." in q or "-" in q or "=" in q or len(q) <= 4)
    )
    if looks_like_explicit_ticker:
        return q_upper

    # Für ISINs, mehrteilige Suchbegriffe ("MSCI World") und Firmennamen ("Bayer", "Siemens"):
    matches = search_tickers(q)
    if matches:
        # Bevorzuge XETRA (.DE) oder Haupthandelsplätze, falls mehrere Treffer vorliegen
        for m in matches:
            if m["symbol"].endswith(".DE"):
                return m["symbol"]
        return matches[0]["symbol"]

    return q_upper


def load_wikifolio_positions(fetch_live: bool = False) -> List[Dict[str, Any]]:
    """
    Lädt die Aktienpositionen aus dem lokalen Cache (data/portfolio_state.json)
    oder optional live über den WikifolioClient.
    """
    portfolio_data = None

    if fetch_live:
        try:
            from wikifolio_client import WikifolioClient
            client = WikifolioClient()
            portfolio_data = client.get_portfolio(config.WIKIFOLIO_ID)
        except Exception as e:
            logger.warning(f"Live-Abruf von Wikifolio nicht möglich: {e}")

    if portfolio_data is None and config.STATE_FILE.exists():
        try:
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                portfolio_data = json.load(f)
        except Exception as e:
            logger.warning(f"Konnte lokale portfolio_state.json nicht lesen: {e}")

    if not portfolio_data or "positions" not in portfolio_data:
        return []

    positions_list = []
    for key, pos in portfolio_data.get("positions", {}).items():
        isin = pos.get("isin", key)
        name = pos.get("name", key)
        pct = pos.get("percentage", 0.0)
        positions_list.append({
            "isin": isin,
            "name": name,
            "percentage": pct,
            "quantity": pos.get("quantity", 0.0),
            "purchase_price": pos.get("average_purchase_price", 0.0),
        })

    # Nach Depot-Gewichtung absteigend sortieren
    positions_list.sort(key=lambda x: x["percentage"], reverse=True)
    return positions_list


GERMAN_EXCHANGE_SUFFIXES = (".DE", ".MU", ".SG", ".DU", ".F", ".HM")


def apply_exchange_preference(symbol: str, exchange_suffix: str) -> str:
    """
    Ersetzt bei deutschen Börsentickern (z.B. RHM.DE, SAP.DE) die Börsenendung
    durch den gewünschten Handelsplatz (z.B. .MU für München/gettex oder .SG für Stuttgart),
    sofern ein spezifischer deutscher Handelsplatz ausgewählt wurde.
    """
    if not exchange_suffix or exchange_suffix == "AUTO":
        return symbol
    upper_sym = symbol.upper()
    for suf in GERMAN_EXCHANGE_SUFFIXES:
        if upper_sym.endswith(suf):
            base = symbol[: -len(suf)]
            return f"{base}{exchange_suffix}"
    return symbol


def get_fx_rate(source_currency: str, target_currency: str) -> float:
    """
    Ermittelt den aktuellen Wechselkurs von source_currency nach target_currency
    über Yahoo Finance (z.B. USDEUR=X oder EURUSD=X).
    """
    src = (source_currency or "EUR").upper().strip()
    tgt = (target_currency or "EUR").upper().strip()

    # Britische Pence (GBp / GBX) zuerst in GBP behandeln
    gbp_factor = 1.0
    if source_currency in ("GBp", "GBX"):
        src = "GBP"
        gbp_factor = 0.01

    if src == tgt:
        return gbp_factor

    pair_symbol = f"{src}{tgt}=X"
    try:
        fx_hist = yf.Ticker(pair_symbol).history(period="5d")
        if fx_hist is not None and not fx_hist.empty:
            rate = float(fx_hist["Close"].dropna().iloc[-1])
            if rate > 0:
                return rate * gbp_factor
    except Exception as e:
        logger.warning(f"Konnte Wechselkurs für {pair_symbol} nicht direkt abrufen: {e}")

    # Fallback über den inversen Wechselkurs
    inv_symbol = f"{tgt}{src}=X"
    try:
        fx_hist = yf.Ticker(inv_symbol).history(period="5d")
        if fx_hist is not None and not fx_hist.empty:
            inv_rate = float(fx_hist["Close"].dropna().iloc[-1])
            if inv_rate > 0:
                return (1.0 / inv_rate) * gbp_factor
    except Exception as e:
        logger.warning(f"Konnte inversen Wechselkurs für {inv_symbol} nicht abrufen: {e}")

    # Statische Sicherheits-Fallbacks falls Yahoo FX kurzzeitig nicht antwortet
    fallback_to_eur = {"USD": 0.92, "GBP": 1.18, "CHF": 1.06, "JPY": 0.0061, "CAD": 0.67, "AUD": 0.60, "EUR": 1.0}
    if src in fallback_to_eur and tgt in fallback_to_eur:
        rate_eur = fallback_to_eur[src] / fallback_to_eur[tgt]
        return rate_eur * gbp_factor

    return 1.0 * gbp_factor


def fetch_stock_data(
    ticker_or_isin: str,
    period: str = "2y",
    exchange_suffix: str = "AUTO",
    target_currency: str = "EUR",
) -> Dict[str, Any]:
    """
    Lädt historische Kursdaten (OHLCV) sowie Fundamental- & Analystendaten von Yahoo Finance.
    Unterstützt die Auswahl des deutschen Handelsplatzes (XETRA .DE, München/gettex .MU, Stuttgart .SG etc.)
    sowie die automatische Währungsumrechnung (Standard: EUR, umschaltbar auf USD oder Originalwährung).
    """
    base_symbol = resolve_query_to_ticker(ticker_or_isin)
    symbol = apply_exchange_preference(base_symbol, exchange_suffix)
    ticker_obj = yf.Ticker(symbol)

    hist = ticker_obj.history(period=period, auto_adjust=True)
    if hist is not None and not hist.empty:
        hist = hist.dropna(subset=["Close"])
    if (hist is None or len(hist) < 5) and symbol != base_symbol:
        # Fallback auf das Basis-Symbol (.DE), falls die Regionalbörse für diesen Ticker keine/zu wenige Daten liefert
        logger.info(f"Zu wenige Daten auf {symbol}, nutze Fallback {base_symbol}")
        symbol = base_symbol
        ticker_obj = yf.Ticker(symbol)
        hist = ticker_obj.history(period=period, auto_adjust=True)
        if hist is not None and not hist.empty:
            hist = hist.dropna(subset=["Close"])

    if hist is None or hist.empty:
        # Zweiter Versuch über Namensauflösung falls direktes Symbol leer war
        alt_results = search_tickers(ticker_or_isin)
        if alt_results:
            base_symbol = alt_results[0]["symbol"]
            symbol = apply_exchange_preference(base_symbol, exchange_suffix)
            ticker_obj = yf.Ticker(symbol)
            hist = ticker_obj.history(period=period, auto_adjust=True)
            if hist is not None and not hist.empty:
                hist = hist.dropna(subset=["Close"])
            if (hist is None or len(hist) < 5) and symbol != base_symbol:
                symbol = base_symbol
                ticker_obj = yf.Ticker(symbol)
                hist = ticker_obj.history(period=period, auto_adjust=True)
                if hist is not None and not hist.empty:
                    hist = hist.dropna(subset=["Close"])

    if hist is None or hist.empty:
        raise ValueError(f"Keine Kursdaten für '{ticker_or_isin}' (aufgelöst als '{symbol}') gefunden.")

    # Zeitzone vereinheitlichen / entfernen für saubere Verarbeitung
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)

    info: Dict[str, Any] = {}
    try:
        info = dict(ticker_obj.info or {})
        # Falls auf einer Regionalbörse (.MU/.SG) wichtige Fundamental-/Analystendaten fehlen, vom Hauptticker (.DE) ergänzen
        if symbol != base_symbol and not info.get("targetMeanPrice") and not info.get("marketCap"):
            base_info = yf.Ticker(base_symbol).info or {}
            merged_info = dict(base_info)
            merged_info.update({k: v for k, v in info.items() if v is not None})
            info = merged_info
    except Exception as e:
        logger.warning(f"Konnte Fundamentaldaten (info) für {symbol} nicht vollständig abrufen: {e}")

    source_currency = info.get("currency") or "USD"
    financial_currency = info.get("financialCurrency") or source_currency

    # Währungsumrechnung falls gewünscht (z.B. EUR oder USD)
    fx_rate = 1.0
    final_currency = source_currency
    if target_currency and target_currency.upper() in ("EUR", "USD"):
        final_currency = target_currency.upper()
        if source_currency.upper() != final_currency or source_currency in ("GBp", "GBX"):
            fx_rate = get_fx_rate(source_currency, final_currency)
            for col in ("Open", "High", "Low", "Close"):
                if col in hist.columns:
                    hist[col] = hist[col] * fx_rate

            # Kursbezogene Felder in info umrechnen (Analysten-Kursziele, 52W-Hoch/Tief, Marktkapitalisierung)
            price_fields = [
                "currentPrice",
                "regularMarketPrice",
                "previousClose",
                "targetMeanPrice",
                "targetHighPrice",
                "targetLowPrice",
                "targetMedianPrice",
                "fiftyTwoWeekHigh",
                "fiftyTwoWeekLow",
                "marketCap",
                "totalAssets",
            ]
            for pf in price_fields:
                if info.get(pf) is not None:
                    try:
                        info[pf] = float(info[pf]) * fx_rate
                    except Exception:
                        pass

        # Bilanzfelder (Cash, Debt, Free Cashflow) von financial_currency in final_currency umrechnen
        fin_fx_rate = get_fx_rate(financial_currency, final_currency) if financial_currency.upper() != final_currency else 1.0
        for bf in ("totalCash", "totalDebt", "freeCashflow", "totalRevenue", "ebitda"):
            if info.get(bf) is not None:
                try:
                    info[bf] = float(info[bf]) * fin_fx_rate
                except Exception:
                    pass

        info["currency"] = final_currency

    return {
        "symbol": symbol,
        "base_symbol": base_symbol,
        "history": hist,
        "info": info,
        "source_currency": source_currency,
        "display_currency": final_currency,
        "fx_rate": fx_rate,
    }


def calculate_technical_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Berechnet umfassende technische Indikatoren, Trendkanäle, Support-/Resistance-Zonen
    und Fibonacci-Retracements auf Basis der historischen Kursdaten.
    """
    data = df.copy()
    close = data["Close"]
    high = data["High"]
    low = data["Low"]

    # 1. Gleitende Durchschnitte (SMA & EMA)
    data["SMA_20"] = close.rolling(window=20, min_periods=5).mean()
    data["SMA_50"] = close.rolling(window=50, min_periods=15).mean()
    data["SMA_200"] = close.rolling(window=200, min_periods=50).mean()
    data["EMA_20"] = close.ewm(span=20, adjust=False).mean()

    # 2. Bollinger Bänder (20 Tage, 2 Standardabweichungen)
    bb_std = close.rolling(window=20, min_periods=5).std()
    data["BB_Middle"] = data["SMA_20"]
    data["BB_Upper"] = data["BB_Middle"] + 2.0 * bb_std
    data["BB_Lower"] = data["BB_Middle"] - 2.0 * bb_std
    data["BB_Width"] = (data["BB_Upper"] - data["BB_Lower"]) / data["BB_Middle"] * 100.0

    # 3. RSI (14 Tage nach Wilder / EMA)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    data["RSI"] = 100.0 - (100.0 / (1.0 + rs))
    data["RSI"] = data["RSI"].fillna(50.0)

    # 4. MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    data["MACD"] = ema12 - ema26
    data["MACD_Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["MACD_Hist"] = data["MACD"] - data["MACD_Signal"]

    # 5. ATR (Average True Range, 14 Tage)
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    data["ATR_14"] = tr.rolling(window=14, min_periods=5).mean()

    # 6. Linearer Regressions-Trendkanal (über die letzten max. 126 Handelstage ~ 6 Monate)
    lookback = min(len(data), 126)
    recent_close = close.iloc[-lookback:].dropna()
    if len(recent_close) >= 3:
        x = np.arange(len(recent_close))
        try:
            slope, intercept = np.polyfit(x, recent_close.values.astype(float), 1)
            reg_line = intercept + slope * x
            residuals = recent_close.values.astype(float) - reg_line
            channel_std = float(np.std(residuals))
        except Exception:
            slope, intercept = 0.0, float(recent_close.iloc[-1])
            reg_line = np.full(len(recent_close), intercept)
            channel_std = 0.0
    else:
        slope = 0.0
        intercept = float(close.dropna().iloc[-1]) if not close.dropna().empty else 0.0
        reg_line = np.full(len(recent_close), intercept)
        channel_std = 0.0

    data["Reg_Center"] = np.nan
    data["Reg_Upper"] = np.nan
    data["Reg_Lower"] = np.nan

    if len(recent_close) > 0:
        idx_slice = recent_close.index
        data.loc[idx_slice, "Reg_Center"] = reg_line
        data.loc[idx_slice, "Reg_Upper"] = reg_line + 2.0 * channel_std
        data.loc[idx_slice, "Reg_Lower"] = reg_line - 2.0 * channel_std

    # 7. Support- & Resistance-Niveaus (aus lokalen Extrema & 52-Wochen-Spanne)
    window_1y = min(len(data), 252)
    high_52w = float(high.iloc[-window_1y:].max())
    low_52w = float(low.iloc[-window_1y:].min())
    curr_price = float(close.iloc[-1])

    # Fibonacci Retracements (bezogen auf 52-Wochen-Spanne)
    price_range = high_52w - low_52w
    fibonacci_levels = {
        "0.0% (52W Hoch)": round(high_52w, 2),
        "23.6% Retracement": round(high_52w - 0.236 * price_range, 2),
        "38.2% Retracement": round(high_52w - 0.382 * price_range, 2),
        "50.0% Retracement": round(high_52w - 0.500 * price_range, 2),
        "61.8% Golden Pocket": round(high_52w - 0.618 * price_range, 2),
        "100.0% (52W Tief)": round(low_52w, 2),
    }

    # Pivot-basierte Unterstützungen und Widerstände der letzten 120 Tage
    recent_highs = high.iloc[-min(len(data), 120):]
    recent_lows = low.iloc[-min(len(data), 120):]

    # Lokale Hochs und Tiefs über 10-Tages-Fenster
    roll_max = recent_highs[recent_highs == recent_highs.rolling(11, center=True).max()].dropna().values
    roll_min = recent_lows[recent_lows == recent_lows.rolling(11, center=True).min()].dropna().values

    resistances = sorted([float(p) for p in roll_max if p > curr_price * 1.005])
    supports = sorted([float(p) for p in roll_min if p < curr_price * 0.995], reverse=True)

    # Deduplizieren nahe beieinander liegender Levels (innerhalb 1.5%)
    def deduplicate_levels(levels: List[float], threshold: float = 0.015) -> List[float]:
        cleaned: List[float] = []
        for lvl in levels:
            if not any(abs(lvl - existing) / existing < threshold for existing in cleaned):
                cleaned.append(round(lvl, 2))
        return cleaned[:3]

    top_resistances = deduplicate_levels(resistances)
    if not top_resistances:
        top_resistances = [round(max(high_52w, curr_price * 1.05), 2)]

    top_supports = deduplicate_levels(supports)
    if not top_supports:
        top_supports = [round(min(low_52w, curr_price * 0.95), 2)]

    # 8. Aktuelle technische Signale auswerten
    last_row = data.iloc[-1]
    sma20_val = float(last_row["SMA_20"]) if pd.notna(last_row["SMA_20"]) else curr_price
    sma50_val = float(last_row["SMA_50"]) if pd.notna(last_row["SMA_50"]) else curr_price
    sma200_val = float(last_row["SMA_200"]) if pd.notna(last_row["SMA_200"]) else curr_price
    rsi_val = float(last_row["RSI"])
    macd_val = float(last_row["MACD"])
    macd_sig = float(last_row["MACD_Signal"])
    bb_upper = float(last_row["BB_Upper"]) if pd.notna(last_row["BB_Upper"]) else curr_price * 1.05
    bb_lower = float(last_row["BB_Lower"]) if pd.notna(last_row["BB_Lower"]) else curr_price * 0.95

    signals = []
    tech_score = 50  # 0 (stark bärisch) bis 100 (stark bullisch)

    # Langfristiger Trend (SMA 200)
    if curr_price > sma200_val:
        pct_above = (curr_price / sma200_val - 1) * 100
        signals.append({
            "indicator": "Langfrist-Trend (SMA 200)",
            "status": "Bullisch",
            "color": "green",
            "detail": f"Kurs notiert {pct_above:+.1f}% oberhalb der 200-Tage-Linie ({sma200_val:.2f})"
        })
        tech_score += 15
    else:
        pct_below = (curr_price / sma200_val - 1) * 100
        signals.append({
            "indicator": "Langfrist-Trend (SMA 200)",
            "status": "Bärisch",
            "color": "red",
            "detail": f"Kurs notiert {pct_below:+.1f}% unterhalb der 200-Tage-Linie ({sma200_val:.2f})"
        })
        tech_score -= 15

    # Mittelfristiger Trend (SMA 50 & Golden/Death Cross)
    if sma50_val > sma200_val and curr_price > sma50_val:
        signals.append({
            "indicator": "Mittelfrist-Trend (SMA 50/200)",
            "status": "Bullisch (Golden Cross Struktur)",
            "color": "green",
            "detail": f"SMA 50 ({sma50_val:.2f}) liegt über SMA 200 ({sma200_val:.2f}), intakter Aufwärtstrend"
        })
        tech_score += 12
    elif sma50_val < sma200_val and curr_price < sma50_val:
        signals.append({
            "indicator": "Mittelfrist-Trend (SMA 50/200)",
            "status": "Bärisch (Death Cross Struktur)",
            "color": "red",
            "detail": f"SMA 50 ({sma50_val:.2f}) liegt unter SMA 200 ({sma200_val:.2f}), Abwärtstrend aktiv"
        })
        tech_score -= 12
    else:
        signals.append({
            "indicator": "Mittelfrist-Trend (SMA 50/200)",
            "status": "Neutral / Übergangsphase",
            "color": "orange",
            "detail": f"Kurs ({curr_price:.2f}) konsolidiert zwischen SMA 50 ({sma50_val:.2f}) und SMA 200 ({sma200_val:.2f})"
        })

    # RSI Bewertung
    if rsi_val >= 70:
        signals.append({
            "indicator": "RSI (14 Tage)",
            "status": f"Überkauft ({rsi_val:.1f})",
            "color": "orange",
            "detail": "Hohes kurzfristiges Rückschlagspotenzial (Gewinnmitnahmen möglich)"
        })
        tech_score -= 5
    elif rsi_val <= 30:
        signals.append({
            "indicator": "RSI (14 Tage)",
            "status": f"Überverkauft ({rsi_val:.1f})",
            "color": "green",
            "detail": "Technisch überverkauft – erhöhte Wahrscheinlichkeit für Gegenbewegung (Rebound)"
        })
        tech_score += 10
    elif 50 <= rsi_val < 70:
        signals.append({
            "indicator": "RSI (14 Tage)",
            "status": f"Positives Momentum ({rsi_val:.1f})",
            "color": "green",
            "detail": "Gesunde Aufwärtsdynamik ohne extreme Überhitzung"
        })
        tech_score += 8
    else:
        signals.append({
            "indicator": "RSI (14 Tage)",
            "status": f"Schwaches Momentum ({rsi_val:.1f})",
            "color": "orange",
            "detail": "Momentum im unteren neutralen Bereich (< 50)"
        })
        tech_score -= 5

    # MACD Bewertung
    if macd_val > macd_sig:
        signals.append({
            "indicator": "MACD (12, 26, 9)",
            "status": "Kaufsignal aktiv",
            "color": "green",
            "detail": f"MACD ({macd_val:.2f}) verläuft oberhalb der Signallinie ({macd_sig:.2f})"
        })
        tech_score += 10
    else:
        signals.append({
            "indicator": "MACD (12, 26, 9)",
            "status": "Verkaufssignal aktiv",
            "color": "red",
            "detail": f"MACD ({macd_val:.2f}) verläuft unterhalb der Signallinie ({macd_sig:.2f})"
        })
        tech_score -= 10

    # Bollinger Band Position
    bb_pos = (curr_price - bb_lower) / max(bb_upper - bb_lower, 1e-6) * 100
    if curr_price >= bb_upper:
        signals.append({
            "indicator": "Bollinger Bänder (20, 2σ)",
            "status": "Am oberen Band",
            "color": "orange",
            "detail": f"Kurs berührt/überschreitet oberes Band ({bb_upper:.2f}) – kurzfristig gedehnt"
        })
    elif curr_price <= bb_lower:
        signals.append({
            "indicator": "Bollinger Bänder (20, 2σ)",
            "status": "Am unteren Band",
            "color": "green",
            "detail": f"Kurs am unteren Band ({bb_lower:.2f}) – statistische Unterstützungszone"
        })
    else:
        signals.append({
            "indicator": "Bollinger Bänder (20, 2σ)",
            "status": f"Im Kanal ({bb_pos:.0f}%)",
            "color": "blue",
            "detail": f"Bandbreite zwischen {bb_lower:.2f} und {bb_upper:.2f}"
        })

    # Regressions-Trendkanal Steigung (annualisiert in %)
    annualized_reg_slope_pct = (slope * 252 / curr_price) * 100.0
    if annualized_reg_slope_pct > 5:
        tech_score += 5
    elif annualized_reg_slope_pct < -5:
        tech_score -= 5

    tech_score = int(np.clip(tech_score, 0, 100))

    return {
        "df": data,
        "current_price": curr_price,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "sma20": sma20_val,
        "sma50": sma50_val,
        "sma200": sma200_val,
        "rsi": rsi_val,
        "macd": macd_val,
        "macd_signal": macd_sig,
        "atr": float(last_row["ATR_14"]) if pd.notna(last_row["ATR_14"]) else 0.0,
        "regression_slope_daily": float(slope),
        "regression_slope_annual_pct": float(annualized_reg_slope_pct),
        "regression_channel_std": channel_std,
        "fibonacci_levels": fibonacci_levels,
        "resistances": top_resistances,
        "supports": top_supports,
        "signals": signals,
        "tech_score": tech_score,
    }


def evaluate_risk_and_rating(df: pd.DataFrame, info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Berechnet quantitative Risiko-Metriken (Volatilität, VaR, CVaR, Max Drawdown, Sharpe, Beta)
    sowie ein synthetisches Bonitäts- & Qualitäts-Rating (AAA bis C) anhand von Bilanz-,
    Verschuldungs-, Cashflow- und Stabilitätskennzahlen aus dem Internet.
    """
    close = df["Close"]
    returns = close.pct_change().dropna()

    # 1. Quantitative Markt-Risikokennzahlen
    daily_vol = float(returns.std()) if len(returns) > 5 else 0.02
    annual_vol = daily_vol * np.sqrt(252) * 100.0  # in %

    mean_daily_ret = float(returns.mean()) if len(returns) > 5 else 0.0003
    annual_return = ((1.0 + mean_daily_ret) ** 252 - 1.0) * 100.0  # in %

    # Risikofreier Zins (Annahme: 3.0% p.a.)
    rf_rate = 3.0
    sharpe_ratio = (annual_return - rf_rate) / annual_vol if annual_vol > 0 else 0.0

    # Downside Deviation & Sortino Ratio
    neg_returns = returns[returns < 0]
    downside_vol = float(neg_returns.std()) * np.sqrt(252) * 100.0 if len(neg_returns) > 2 else annual_vol
    sortino_ratio = (annual_return - rf_rate) / downside_vol if downside_vol > 0 else 0.0

    # Historischer Value at Risk (VaR 95% & 99%) – 1 Tag und 1 Monat (21 Handelstage)
    var_95_daily = float(np.percentile(returns, 5)) * 100.0 if len(returns) > 10 else -2.5
    cvar_95_daily = float(returns[returns <= np.percentile(returns, 5)].mean()) * 100.0 if len(returns) > 10 else -3.5
    var_95_monthly = var_95_daily * np.sqrt(21)

    # Maximaler historischer Drawdown im Betrachtungszeitraum
    rolling_max = close.cummax()
    drawdowns = (close - rolling_max) / rolling_max * 100.0
    max_drawdown = float(drawdowns.min())
    current_drawdown = float(drawdowns.iloc[-1])

    # 2. Fundamentaldaten aus Yahoo Finance extrahieren
    quote_type = info.get("quoteType", "EQUITY")
    is_commodity = (quote_type == "FUTURE") or str(info.get("symbol", "")).endswith("=F")
    is_etf = quote_type in ("ETF", "MUTUALFUND") or is_commodity
    beta = info.get("beta") or info.get("beta3Year")
    debt_to_equity = info.get("debtToEquity")  # oft in % angegeben bei Yahoo (z.B. 150 = 1.5x)
    current_ratio = info.get("currentRatio")
    quick_ratio = info.get("quickRatio")
    profit_margins = info.get("profitMargins")  # als Dezimalzahl z.B. 0.25
    operating_margins = info.get("operatingMargins")
    roe = info.get("returnOnEquity")
    roa = info.get("returnOnAssets")
    free_cashflow = info.get("freeCashflow")
    total_cash = info.get("totalCash")
    total_debt = info.get("totalDebt")
    market_cap = info.get("marketCap") or info.get("totalAssets")
    trailing_pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")
    dividend_yield = info.get("dividendYield") or info.get("yield")
    expense_ratio = info.get("annualReportExpenseRatio") or info.get("netExpenseRatio")

    # Analysten-Daten
    target_mean = info.get("targetMeanPrice")
    target_high = info.get("targetHighPrice")
    target_low = info.get("targetLowPrice")
    recommendation_key = info.get("recommendationKey", "none")
    recommendation_mean = info.get("recommendationMean")  # 1.0 = Strong Buy, 5.0 = Sell
    num_analysts = info.get("numberOfAnalystOpinions") or 0

    # 3. Synthetisches Qualitäts- & Risiko-Rating (AAA bis C) berechnen
    # Wir bewerten 4 Säulen (angepasst für Einzelaktien vs. breit gestreute ETFs):
    score_pillars: List[Dict[str, Any]] = []
    total_points = 0.0
    max_points = 0.0

    if is_etf:
        # Säule 1: Struktur & Ausfallschutz (ETF vs. Rohstoff) (max 30 Punkte)
        if is_commodity:
            div_pts = 26.0
            div_details = ["Physischer Rohstoff / Sachwert (kein Unternehmens-Insolvenzrisiko, Inflations- & Krisenschutz)"]
            if annual_vol < 20.0:
                div_pts = 28.0
                div_details.append("Relativ stabile Preisentwicklung im Rohstoffvergleich")
            pillar1_name = "Sachwert & Krisenschutz (Rohstoff)"
        else:
            div_pts = 27.0
            div_details = ["Rechtlich geschütztes Sondervermögen (kein Emittenten-Insolvenzrisiko), breite Index-Streuung"]
            if annual_vol < 18.0:
                div_pts = 29.0
                div_details.append("Sehr geringe Schwankungsbreite durch breite Diversifikation")
            pillar1_name = "Diversifikation & Struktur (ETF)"
        score_pillars.append({
            "name": pillar1_name,
            "score": round(div_pts / 30.0 * 100),
            "details": "; ".join(div_details),
        })
        total_points += div_pts
        max_points += 30.0

        # ETF-Säule 2: Rendite-Risiko-Effizienz / Sharpe & Trend (max 30 Punkte)
        eff_pts = 18.0
        eff_details = []
        if sharpe_ratio >= 0.8:
            eff_pts = 27.0
            eff_details.append(f"Starkes Rendite-Risiko-Verhältnis (Sharpe Ratio: {sharpe_ratio:.2f})")
        elif sharpe_ratio >= 0.3:
            eff_pts = 22.0
            eff_details.append(f"Solides Rendite-Risiko-Verhältnis (Sharpe Ratio: {sharpe_ratio:.2f})")
        elif sharpe_ratio >= 0.0:
            eff_pts = 16.0
            eff_details.append(f"Moderate historische Risikoprämie (Sharpe Ratio: {sharpe_ratio:.2f})")
        else:
            eff_pts = 9.0
            eff_details.append(f"Negative historische Überschussrendite (Sharpe Ratio: {sharpe_ratio:.2f})")

        if expense_ratio is not None:
            ter_pct = float(expense_ratio) * 100.0 if float(expense_ratio) < 1 else float(expense_ratio)
            eff_details.append(f"Kostenquote (TER): {ter_pct:.2f}% p.a.")
            if ter_pct <= 0.25:
                eff_pts = min(30.0, eff_pts + 3.0)

        score_pillars.append({
            "name": "Rendite-Effizienz & Kosten",
            "score": round(eff_pts / 30.0 * 100),
            "details": "; ".join(eff_details),
        })
        total_points += eff_pts
        max_points += 30.0
    else:
        # Säule 1: Bilanz & Verschuldung für Aktien (max 30 Punkte)
        balance_pts = 15.0  # Neutraler Startwert falls Daten fehlen
        balance_details = []
        if total_cash is not None and total_debt is not None:
            if total_cash >= total_debt:
                balance_pts = 28.0
                balance_details.append("Netto-Cash-Position (Barbestand übersteigt Gesamtverschuldung)")
            elif debt_to_equity is not None:
                if debt_to_equity < 50:
                    balance_pts = 25.0
                    balance_details.append(f"Niedriger Verschuldungsgrad (Debt/Equity: {debt_to_equity:.1f}%)")
                elif debt_to_equity < 120:
                    balance_pts = 19.0
                    balance_details.append(f"Moderater Verschuldungsgrad (Debt/Equity: {debt_to_equity:.1f}%)")
                elif debt_to_equity < 250:
                    balance_pts = 12.0
                    balance_details.append(f"Erhöhte Verschuldung (Debt/Equity: {debt_to_equity:.1f}%)")
                else:
                    balance_pts = 5.0
                    balance_details.append(f"Hohe Verschuldung (Debt/Equity: {debt_to_equity:.1f}%)")
        elif debt_to_equity is not None:
            if debt_to_equity < 60:
                balance_pts = 25.0
                balance_details.append(f"Solide Bilanzrelation (Debt/Equity: {debt_to_equity:.1f}%)")
            elif debt_to_equity < 150:
                balance_pts = 17.0
                balance_details.append(f"Normale Verschuldung (Debt/Equity: {debt_to_equity:.1f}%)")
            else:
                balance_pts = 8.0
                balance_details.append(f"Hoher Fremdkapitalanteil (Debt/Equity: {debt_to_equity:.1f}%)")

        if current_ratio is not None:
            if current_ratio >= 1.5:
                balance_pts = min(30.0, balance_pts + 3.0)
                balance_details.append(f"Starke kurzfristige Liquidität (Current Ratio: {current_ratio:.2f})")
            elif current_ratio < 0.9:
                balance_pts = max(0.0, balance_pts - 4.0)
                balance_details.append(f"Knappe kurzfristige Liquidität (Current Ratio: {current_ratio:.2f})")

        if not balance_details:
            balance_details.append("Keine detaillierten Bilanzdaten gemeldet (neutral gewichtet)")

        score_pillars.append({
            "name": "Bilanz & Solvenz",
            "score": round(balance_pts / 30.0 * 100),
            "details": "; ".join(balance_details)
        })
        total_points += balance_pts
        max_points += 30.0

        # Säule 2: Profitabilität & Cashflow für Aktien (max 30 Punkte)
        prof_pts = 15.0
        prof_details = []
        if profit_margins is not None:
            pm_pct = profit_margins * 100.0
            if pm_pct >= 20:
                prof_pts = 26.0
                prof_details.append(f"Exzellente Nettomarge ({pm_pct:.1f}%)")
            elif pm_pct >= 10:
                prof_pts = 21.0
                prof_details.append(f"Gute Nettomarge ({pm_pct:.1f}%)")
            elif pm_pct > 0:
                prof_pts = 14.0
                prof_details.append(f"Positive Nettomarge ({pm_pct:.1f}%)")
            else:
                prof_pts = 5.0
                prof_details.append(f"Unternehmen schreibt aktuell Verluste (Marge: {pm_pct:.1f}%)")

        if free_cashflow is not None:
            if free_cashflow > 0:
                prof_pts = min(30.0, prof_pts + 4.0)
                prof_details.append("Positiver Free Cashflow")
            else:
                prof_pts = max(0.0, prof_pts - 5.0)
                prof_details.append("Negativer Free Cashflow (Cash-Burn)")

        if not prof_details:
            prof_details.append("Keine Margendaten verfügbar (Standardgewichtung)")

        score_pillars.append({
            "name": "Ertragskraft & Cashflow",
            "score": round(prof_pts / 30.0 * 100),
            "details": "; ".join(prof_details)
        })
        total_points += prof_pts
        max_points += 30.0

    # Säule 3: Volatilitäts- & Drawdown-Stabilität (max 25 Punkte)
    stab_pts = 12.5
    stab_details = []
    if annual_vol < 20.0:
        stab_pts = 22.0
        stab_details.append(f"Niedrige Kursvolatilität ({annual_vol:.1f}% p.a.)")
    elif annual_vol < 32.0:
        stab_pts = 16.0
        stab_details.append(f"Moderate Kursvolatilität ({annual_vol:.1f}% p.a.)")
    elif annual_vol < 48.0:
        stab_pts = 10.0
        stab_details.append(f"Erhöhte Kursvolatilität ({annual_vol:.1f}% p.a.)")
    else:
        stab_pts = 4.0
        stab_details.append(f"Sehr hohe Kursschwankungen ({annual_vol:.1f}% p.a.)")

    if max_drawdown > -20.0:
        stab_pts = min(25.0, stab_pts + 3.0)
        stab_details.append(f"Geringer Max. Drawdown ({max_drawdown:.1f}%)")
    elif max_drawdown < -45.0:
        stab_pts = max(0.0, stab_pts - 4.0)
        stab_details.append(f"Tiefer historischer Einbruch ({max_drawdown:.1f}%)")

    score_pillars.append({
        "name": "Kurs- & Krisenstabilität",
        "score": round(stab_pts / 25.0 * 100),
        "details": "; ".join(stab_details)
    })
    total_points += stab_pts
    max_points += 25.0

    # Säule 4: Marktstellung & Kapitalisierung / Fondsvolumen (max 15 Punkte)
    cap_pts = 11.0 if is_etf else 8.0
    cap_details = []
    if market_cap is not None:
        cap_b = market_cap / 1e9
        if is_etf:
            if cap_b >= 5:
                cap_pts = 15.0
                cap_details.append(f"Sehr großes Fondsvolumen ({cap_b:.1f} Mrd. AuM – höchste Liquidität)")
            elif cap_b >= 0.5:
                cap_pts = 13.0
                cap_details.append(f"Etabliertes Fondsvolumen ({cap_b:.2f} Mrd. AuM)")
            elif cap_b >= 0.1:
                cap_pts = 10.0
                cap_details.append(f"Solides Fondsvolumen ({cap_b * 1000:.0f} Mio. AuM)")
            else:
                cap_pts = 5.0
                cap_details.append(f"Kleiner ETF ({cap_b * 1000:.0f} Mio. AuM – Schließungsrisiko beachten)")
        else:
            if cap_b >= 200:
                cap_pts = 15.0
                cap_details.append(f"Mega-Cap Marktführer ({cap_b:.0f} Mrd. Börsenwert)")
            elif cap_b >= 20:
                cap_pts = 13.0
                cap_details.append(f"Etablierter Large-Cap ({cap_b:.1f} Mrd. Börsenwert)")
            elif cap_b >= 2:
                cap_pts = 9.0
                cap_details.append(f"Solider Mid-Cap ({cap_b:.1f} Mrd. Börsenwert)")
            else:
                cap_pts = 4.0
                cap_details.append(f"Small-Cap mit höherem Liquiditätsrisiko ({cap_b:.2f} Mrd.)")
    else:
        cap_details.append("Börsenwert / Fondsvolumen nicht gemeldet (Standardgewichtung)")

    score_pillars.append({
        "name": "Fondsvolumen & Liquidität" if is_etf else "Marktgröße & Liquidität",
        "score": round(cap_pts / 15.0 * 100),
        "details": "; ".join(cap_details)
    })
    total_points += cap_pts
    max_points += 15.0

    overall_rating_score = round((total_points / max_points) * 100.0, 1)

    # Übersetzung in AAA bis C Skala (angelehnt an S&P / Moody's / Fitch)
    if overall_rating_score >= 86:
        rating_grade = "AAA"
        rating_label = "Höchste Qualität & Bonität (Prime Investment Grade)"
        rating_color = "#10b981"  # Smaragdgrün
        risk_class = "Niedriges Risiko"
    elif overall_rating_score >= 76:
        rating_grade = "AA"
        rating_label = "Sehr hohe Qualität & Finanzstärke (High Grade)"
        rating_color = "#22c55e"
        risk_class = "Niedriges bis moderates Risiko"
    elif overall_rating_score >= 66:
        rating_grade = "A"
        rating_label = "Solide Finanz- & Marktposition (Upper Medium Grade)"
        rating_color = "#84cc16"
        risk_class = "Moderates Risiko"
    elif overall_rating_score >= 54:
        rating_grade = "BBB"
        rating_label = "Befriedigende Qualität, konjunktursensibel (Investment Grade)"
        rating_color = "#eab308"
        risk_class = "Mittelhohes Risiko"
    elif overall_rating_score >= 42:
        rating_grade = "BB"
        rating_label = "Spekulativer Charakter, erhöhte Schwankung (Non-Investment Grade)"
        rating_color = "#f97316"
        risk_class = "Erhöhtes Risiko"
    elif overall_rating_score >= 30:
        rating_grade = "B"
        rating_label = "Hochspekulativ, anfällig bei Marktschocks"
        rating_color = "#ef4444"
        risk_class = "Hohes Risiko"
    else:
        rating_grade = "CCC / C"
        rating_label = "Sehr hohes Ausfall- oder Verlustrisiko (Distressed)"
        rating_color = "#b91c1c"
        risk_class = "Sehr hohes Risiko"

    return {
        "rating_grade": rating_grade,
        "rating_score": overall_rating_score,
        "rating_label": rating_label,
        "rating_color": rating_color,
        "risk_class": risk_class,
        "pillars": score_pillars,
        "metrics": {
            "annual_volatility_pct": round(annual_vol, 2),
            "annual_return_pct": round(annual_return, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "var_95_daily_pct": round(var_95_daily, 2),
            "cvar_95_daily_pct": round(cvar_95_daily, 2),
            "var_95_monthly_pct": round(var_95_monthly, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "current_drawdown_pct": round(current_drawdown, 2),
            "beta": round(float(beta), 2) if beta is not None else None,
            "debt_to_equity": round(float(debt_to_equity), 1) if debt_to_equity is not None else None,
            "current_ratio": round(float(current_ratio), 2) if current_ratio is not None else None,
            "profit_margin_pct": round(float(profit_margins) * 100.0, 1) if profit_margins is not None else None,
            "roe_pct": round(float(roe) * 100.0, 1) if roe is not None else None,
            "trailing_pe": round(float(trailing_pe), 1) if trailing_pe is not None else None,
            "forward_pe": round(float(forward_pe), 1) if forward_pe is not None else None,
            "dividend_yield_pct": round(float(dividend_yield) * 100.0, 2) if dividend_yield is not None and dividend_yield < 1 else (round(float(dividend_yield), 2) if dividend_yield is not None else None),
            "market_cap": market_cap,
            "free_cashflow": free_cashflow,
            "total_cash": total_cash,
            "total_debt": total_debt,
        },
        "analyst_consensus": {
            "target_mean": round(float(target_mean), 2) if target_mean is not None else None,
            "target_high": round(float(target_high), 2) if target_high is not None else None,
            "target_low": round(float(target_low), 2) if target_low is not None else None,
            "recommendation_key": recommendation_key,
            "recommendation_mean": round(float(recommendation_mean), 2) if recommendation_mean is not None else None,
            "num_analysts": int(num_analysts),
        },
        "drawdown_series": drawdowns,
    }


def simulate_future_scenarios(
    df: pd.DataFrame,
    tech_data: Dict[str, Any],
    risk_data: Dict[str, Any],
    horizon_days: int = 126,
    num_simulations: int = 500,
    custom_drift_override_pct: Optional[float] = None,
    volatility_multiplier: float = 1.0,
    shock_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Simuliert zukünftige Kursverläufe über den gewählten Zeithorizont (in Handelstagen):
    1. Geometrische Brownsche Bewegung (Monte-Carlo-Simulation mit hunderten Zufallspfaden)
    2. Deterministische Szenario-Pfade (Bull Case / Base Case / Bear Case / Analysten-Ziel / Trendkanal-Fortsetzung)
    3. Optionale Was-wäre-wenn-Einstellungen (Marktschock, Volatilitätsfaktor, eigener Drift)
    """
    close = df["Close"]
    returns = close.pct_change().dropna()
    last_date = close.index[-1]
    start_price = float(close.iloc[-1]) * (1.0 + shock_pct / 100.0)

    # Historische Parameter (geglättet / begrenzt gegen extreme Ausreißer)
    hist_daily_vol = float(returns.std()) if len(returns) > 10 else 0.018
    sim_daily_vol = hist_daily_vol * volatility_multiplier

    hist_annual_return = risk_data["metrics"]["annual_return_pct"] / 100.0
    # Begrenze den Standard-Drift auf realistische [-25%, +35%] p.a., sofern nicht manuell überschrieben
    if custom_drift_override_pct is not None:
        base_annual_drift = custom_drift_override_pct / 100.0
    else:
        # Kombination aus historischem Trend, Regressionstrend und Analystenziel (falls vorhanden)
        reg_annual = tech_data["regression_slope_annual_pct"] / 100.0
        blended_drift = 0.5 * hist_annual_return + 0.5 * reg_annual

        target_mean = risk_data["analyst_consensus"]["target_mean"]
        if target_mean and target_mean > 0:
            analyst_implied_return = (target_mean / float(close.iloc[-1])) - 1.0
            blended_drift = 0.6 * blended_drift + 0.4 * analyst_implied_return

        base_annual_drift = float(np.clip(blended_drift, -0.30, 0.40))

    daily_mu = base_annual_drift / 252.0

    # Zukünftige Handelstage generieren (Business Days)
    future_dates = pd.bdate_range(start=last_date, periods=horizon_days + 1)

    # Monte-Carlo Pfade (Geometrische Brownsche Bewegung)
    rng = np.random.default_rng(seed=42)
    dt = 1.0
    random_shocks = rng.normal(
        loc=(daily_mu - 0.5 * (sim_daily_vol ** 2)) * dt,
        scale=sim_daily_vol * np.sqrt(dt),
        size=(horizon_days, num_simulations)
    )

    log_paths = np.vstack([np.zeros((1, num_simulations)), np.cumsum(random_shocks, axis=0)])
    price_paths = start_price * np.exp(log_paths)

    # Perzentil-Korridore über alle simulierten Pfade
    p10 = np.percentile(price_paths, 10, axis=1)  # Bear Case (10. Perzentil)
    p25 = np.percentile(price_paths, 25, axis=1)  # Moderater Pessimismus
    p50 = np.percentile(price_paths, 50, axis=1)  # Base Case (Median)
    p75 = np.percentile(price_paths, 75, axis=1)  # Moderater Optimismus
    p90 = np.percentile(price_paths, 90, axis=1)  # Bull Case (90. Perzentil)
    mean_path = np.mean(price_paths, axis=1)

    # Lineare Trendkanal-Fortsetzung (Projektion der 6-Monats-Regression)
    days_arr = np.arange(horizon_days + 1)
    reg_slope = tech_data["regression_slope_daily"]
    reg_proj = start_price + reg_slope * days_arr

    # Endwerte auswerten
    final_prices = price_paths[-1, :]
    orig_price = float(close.iloc[-1])
    prob_profit = float(np.mean(final_prices > orig_price) * 100.0)
    prob_gain_10 = float(np.mean(final_prices >= orig_price * 1.10) * 100.0)
    prob_loss_10 = float(np.mean(final_prices <= orig_price * 0.90) * 100.0)

    return {
        "future_dates": future_dates,
        "start_price": orig_price,
        "shocked_start_price": start_price,
        "horizon_days": horizon_days,
        "base_annual_drift_pct": round(base_annual_drift * 100.0, 2),
        "sim_annual_vol_pct": round(sim_daily_vol * np.sqrt(252) * 100.0, 2),
        "sample_paths": price_paths[:, :40],  # 40 repräsentative Zufallspfade für den Plot
        "final_prices": final_prices,
        "percentiles": {
            "bear_10": p10,
            "lower_25": p25,
            "median_50": p50,
            "upper_75": p75,
            "bull_90": p90,
            "mean": mean_path,
            "regression_trend": reg_proj,
        },
        "summary": {
            "bear_price": round(float(p10[-1]), 2),
            "bear_return_pct": round((float(p10[-1]) / orig_price - 1.0) * 100.0, 2),
            "base_price": round(float(p50[-1]), 2),
            "base_return_pct": round((float(p50[-1]) / orig_price - 1.0) * 100.0, 2),
            "bull_price": round(float(p90[-1]), 2),
            "bull_return_pct": round((float(p90[-1]) / orig_price - 1.0) * 100.0, 2),
            "prob_profit_pct": round(prob_profit, 1),
            "prob_gain_10_pct": round(prob_gain_10, 1),
            "prob_loss_10_pct": round(prob_loss_10, 1),
        }
    }


def generate_advisory_report(
    symbol: str,
    info: Dict[str, Any],
    tech_data: Dict[str, Any],
    risk_data: Dict[str, Any],
    sim_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Führt Charttechnik, Fundamental-/Bonitätsrating, Analystenkonsens und Simulations-Szenarien
    zu einer strukturierten Strategie- und Beratungseinschätzung zusammen.
    """
    curr_price = tech_data["current_price"]
    tech_score = tech_data["tech_score"]
    rating_score = risk_data["rating_score"]
    rating_grade = risk_data["rating_grade"]

    analyst = risk_data["analyst_consensus"]
    target_mean = analyst["target_mean"]
    analyst_upside_pct = ((target_mean / curr_price) - 1.0) * 100.0 if target_mean else None

    # Analysten-Score (0 bis 100)
    analyst_score = 50
    if analyst_upside_pct is not None:
        if analyst_upside_pct >= 20:
            analyst_score = 85
        elif analyst_upside_pct >= 8:
            analyst_score = 70
        elif analyst_upside_pct >= -5:
            analyst_score = 50
        else:
            analyst_score = 25

    # Gesamt-Score aus Technik (40%), Fundamental/Bonität (40%), Analysten/Simulation (20%)
    composite_score = round(0.40 * tech_score + 0.40 * rating_score + 0.20 * analyst_score)

    if composite_score >= 72:
        verdict = "STARK BULLISCH / AUFSTOCKEN"
        verdict_color = "#10b981"
        summary_text = (
            f"{symbol} überzeugt sowohl durch ein starkes Qualitäts- und Bonitätsprofil ({rating_grade}) "
            f"als auch durch eine konstruktive charttechnische Verfassung (Technik-Score: {tech_score}/100)."
        )
    elif composite_score >= 58:
        verdict = "MODERAT POSITIV / HALTEN & AUFBAUEN"
        verdict_color = "#22c55e"
        summary_text = (
            f"{symbol} zeigt ein solides Chancen-Risiko-Verhältnis (Bonitäts-Score: {rating_grade}). "
            f"Rücksetzer in Richtung der technischen Unterstützungszonen bieten sich für gestaffelte Einstiege an."
        )
    elif composite_score >= 44:
        verdict = "NEUTRAL / ABWARTEN (SEITWÄRTSPHASE)"
        verdict_color = "#eab308"
        summary_text = (
            f"Bei {symbol} halten sich positive und bremsende Faktoren aktuell die Waage. "
            f"Vor neuen Engagements sollte ein klarer Ausbruch über die nächsten Widerstände oder eine Bereinigung abgewartet werden."
        )
    else:
        verdict = "VORSICHT / DEFENSIV AGIEREN"
        verdict_color = "#ef4444"
        summary_text = (
            f"{symbol} weist aktuell erhöhte charttechnische oder fundamentale Risiken auf (Rating: {rating_grade}, "
            f"Technik-Score: {tech_score}/100). Enge Stop-Loss-Absicherungen und Risikobegrenzung stehen im Vordergrund."
        )

    # Konkrete Handlungspunkte (Takeaways) generieren
    strengths = []
    risks = []

    if rating_score >= 66:
        strengths.append(f"Hohe fundamentale Bilanz- & Ertragsqualität (Rating {rating_grade}, Score {rating_score}/100).")
    else:
        risks.append(f"Unterdurchschnittliches Risiko-/Bilanz-Rating ({rating_grade}, Score {rating_score}/100).")

    if curr_price > tech_data["sma200"]:
        strengths.append(f"Intakter langfristiger Aufwärtstrend oberhalb der 200-Tage-Linie ({tech_data['sma200']:.2f}).")
    else:
        risks.append(f"Kurs notiert unter der wichtigen 200-Tage-Linie ({tech_data['sma200']:.2f}) – übergeordneter Abwärtsdruck.")

    if tech_data["rsi"] < 35:
        strengths.append(f"RSI ({tech_data['rsi']:.1f}) signalisiert überverkauftes Niveau – Rebound-Chance.")
    elif tech_data["rsi"] > 70:
        risks.append(f"RSI ({tech_data['rsi']:.1f}) zeigt kurzfristige Überhitzung – Rücksetzer-Gefahr.")

    if analyst_upside_pct is not None:
        if analyst_upside_pct > 5:
            strengths.append(
                f"Analysten-Konsens sieht im Mittel +{analyst_upside_pct:.1f}% Kurspotenzial "
                f"(Durchschnittsziel: {target_mean:.2f}, {analyst['num_analysts']} Analysten)."
            )
        elif analyst_upside_pct < -5:
            risks.append(
                f"Aktueller Kurs liegt bereits über dem mittleren Analysten-Kursziel von {target_mean:.2f} ({analyst_upside_pct:+.1f}%)."
            )

    vol = risk_data["metrics"]["annual_volatility_pct"]
    mdd = risk_data["metrics"]["max_drawdown_pct"]
    if vol > 35 or mdd < -35:
        risks.append(f"Hohe historische Schwankungsbreite (Volatilität: {vol:.1f}% p.a., Max Drawdown: {mdd:.1f}%).")
    else:
        strengths.append(f"Kontrollierte historische Volatilität ({vol:.1f}% p.a.) mit moderatem Drawdown-Profil ({mdd:.1f}%).")

    # Schlüsselmarken für das Trading / Risikomanagement
    nearest_support = tech_data["supports"][0] if tech_data["supports"] else round(curr_price * 0.93, 2)
    nearest_resistance = tech_data["resistances"][0] if tech_data["resistances"] else round(curr_price * 1.07, 2)
    atr_stop = round(curr_price - 2.0 * tech_data["atr"], 2) if tech_data["atr"] > 0 else round(curr_price * 0.94, 2)

    return {
        "composite_score": composite_score,
        "tech_score": tech_score,
        "rating_score": rating_score,
        "analyst_score": analyst_score,
        "verdict": verdict,
        "verdict_color": verdict_color,
        "summary_text": summary_text,
        "strengths": strengths,
        "risks": risks,
        "tactical_levels": {
            "entry_zone": f"{nearest_support:.2f} – {curr_price:.2f}",
            "first_resistance": f"{nearest_resistance:.2f}",
            "atr_stop_loss": f"{atr_stop:.2f} (2x ATR Abstand)",
            "analyst_target": f"{target_mean:.2f} ({analyst_upside_pct:+.1f}%)" if target_mean and analyst_upside_pct is not None else "Nicht verfügbar",
        }
    }
