import json
import logging
from typing import Optional, Dict, Any, List
import requests
from requests.cookies import RequestsCookieJar
import config

logger = logging.getLogger("WikifolioClient")


class WikifolioClient:
    BASE_URL = "https://www.wikifolio.com"

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.email = email or config.WIKIFOLIO_EMAIL
        self.password = password or config.WIKIFOLIO_PASSWORD
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.wikifolio.com/de/de/home",
            "Origin": "https://www.wikifolio.com"
        })
        self._load_saved_session()

    def _load_saved_session(self) -> bool:
        """
        Lädt zuvor gespeicherte Session-Cookies aus session_cookie.json falls vorhanden.
        """
        if not config.SESSION_FILE.exists():
            return False

        try:
            with open(config.SESSION_FILE, "r", encoding="utf-8") as f:
                cookies_dict = json.load(f)
                requests.utils.cookiejar_from_dict(cookies_dict, cookiejar=self.session.cookies)
                return True
        except Exception as e:
            logger.warning(f"Konnte Session-Datei nicht laden: {e}")
            return False

    def _save_session(self) -> None:
        """
        Speichert aktuelle Session-Cookies in session_cookie.json.
        """
        try:
            cookies_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
            with open(config.SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies_dict, f, indent=2)
        except Exception as e:
            logger.warning(f"Konnte Session-Cookies nicht speichern: {e}")

    def login(self) -> bool:
        """
        Meldet sich mit E-Mail und Passwort bei Wikifolio an.
        """
        if not self.email or not self.password:
            raise ValueError("WIKIFOLIO_EMAIL und WIKIFOLIO_PASSWORD müssen gesetzt sein.")

        login_url = f"{self.BASE_URL}/api/login?country=de&language=de"
        payload = {
            "email": self.email,
            "password": self.password,
            "keepLoggedIn": True
        }

        try:
            resp = self.session.post(login_url, json=payload, timeout=15)
            if resp.status_code == 200:
                self._save_session()
                return True
            else:
                error_msg = f"Wikifolio Login fehlgeschlagen (HTTP {resp.status_code}): {resp.text}"
                logger.error(error_msg)
                raise ConnectionError(error_msg)
        except requests.RequestException as e:
            raise ConnectionError(f"Netzwerkfehler beim Wikifolio Login: {e}")

    def get_portfolio(self, wikifolio_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ruft die Depot-Zusammensetzung für die gegebene Wikifolio-ID ab.
        Führt bei Bedarf einen automatischen Re-Login durch.
        """
        wf_id = wikifolio_id or config.WIKIFOLIO_ID
        url = f"{self.BASE_URL}/api/wikifolio/{wf_id}/portfolio"

        resp = self.session.get(url, timeout=15)

        # Bei 401 Unauthorized: Erneut einloggen und Anfrage wiederholen
        if resp.status_code == 401:
            logger.info("Session abgelaufen oder nicht eingeloggt. Führe Login durch...")
            self.login()
            resp = self.session.get(url, timeout=15)

        if resp.status_code != 200:
            raise RuntimeError(f"Fehler beim Abruf des Portfolios ({resp.status_code}): {resp.text}")

        raw_data = resp.json()
        return self._parse_portfolio(raw_data)

    def _parse_portfolio(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parst das Roh-JSON von Wikifolio in eine saubere, vergleichbare Datenstruktur.
        """
        positions: Dict[str, Dict[str, Any]] = {}
        cash_percentage = 0.0

        groups = raw_data.get("groups", [])
        for group in groups:
            items = group.get("items", [])
            group_type = group.get("type")

            for item in items:
                name = item.get("name", "").strip()
                isin = item.get("isin", "").strip()
                pct = float(item.get("percentage") or item.get("weighting") or 0.0)

                # Prüfen, ob es sich um den Cash-Bestand handelt
                is_cash = (
                    group_type == 0 or
                    "cash" in name.lower() or
                    "barbestand" in name.lower() or
                    not isin
                )

                if is_cash:
                    cash_percentage += pct
                else:
                    # Eindeutiger Schlüssel: Bevorzugt ISIN, sonst Name
                    pos_key = isin if isin else name
                    positions[pos_key] = {
                        "name": name,
                        "isin": isin,
                        "percentage": round(pct, 2),
                        "quantity": float(item.get("quantity") or 0.0),
                        "average_purchase_price": float(item.get("averagePurchasePrice") or 0.0),
                        "close_price": float(item.get("close") or item.get("price") or 0.0),
                        "performance_since_buy": float(item.get("performanceSinceBuy") or 0.0) if item.get("performanceSinceBuy") is not None else None,
                        "performance_today": float(item.get("performanceToday") or 0.0) if item.get("performanceToday") is not None else None
                    }

        # Falls kein expliziter Cash-Wert in den Items stand, berechnen: 100 - Summe(Aktien)
        if cash_percentage == 0.0 and positions:
            total_equity = sum(p["percentage"] for p in positions.values())
            cash_percentage = max(0.0, round(100.0 - total_equity, 2))
        else:
            cash_percentage = round(cash_percentage, 2)

        return {
            "cash_percentage": cash_percentage,
            "positions": positions,
            "raw_groups_count": len(groups),
        }

    def get_trade_history(self, wikifolio_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Ruft die Historie der ausgeführten Trades ab.
        """
        wf_id = wikifolio_id or config.WIKIFOLIO_ID
        url = f"{self.BASE_URL}/api/wikifolio/{wf_id}/tradehistory"

        resp = self.session.get(url, timeout=15)
        if resp.status_code == 401:
            self.login()
            resp = self.session.get(url, timeout=15)

        if resp.status_code != 200:
            logger.warning(f"Konnte Trade-Historie nicht abrufen ({resp.status_code}): {resp.text}")
            return []

        try:
            return resp.json()
        except Exception:
            return []
