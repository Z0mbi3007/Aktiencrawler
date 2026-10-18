import subprocess
import requests
import html
from typing import Optional
import config


class Notifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.has_telegram = bool(self.bot_token and self.chat_id and "ABCdefGh" not in self.bot_token)
        self.enable_macos = config.ENABLE_MACOS_NOTIFICATIONS

    def send_telegram(self, message_html: str) -> bool:
        """
        Sendet eine HTML-formatierte Nachricht an den konfigurierten Telegram-Chat.
        """
        if not self.has_telegram:
            print("[Notifier] Telegram nicht konfiguriert (Token/Chat-ID fehlt). Nachricht wird übersprungen.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message_html,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                print(f"[Notifier] Telegram Fehler ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            print(f"[Notifier] Verbindungsfehler zu Telegram: {e}")
            return False

    def send_macos_notification(self, title: str, subtitle: str, message: str) -> None:
        """
        Sendet eine Desktop-Mitteilung auf macOS über AppleScript.
        """
        if not self.enable_macos:
            return

        def escape_as(s: str) -> str:
            return s.replace('\\', '\\\\').replace('"', '\\"')

        safe_title = escape_as(title)
        safe_sub = escape_as(subtitle)
        safe_msg = escape_as(message)

        script = f'display notification "{safe_msg}" with title "{safe_title}" subtitle "{safe_sub}" sound name "Glass"'
        try:
            subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
        except Exception as e:
            print(f"[Notifier] macOS Benachrichtigung fehlgeschlagen: {e}")

    def notify(self, title: str, body_html: str, short_text: Optional[str] = None) -> bool:
        """
        Sendet die Benachrichtigung sowohl über Telegram als auch macOS-Mitteilung.
        """
        full_message = f"<b>{html.escape(title)}</b>\n\n{body_html}"
        tg_success = self.send_telegram(full_message)

        # macOS Notification (plain text)
        macos_body = short_text or title
        self.send_macos_notification("Wikifolio Alert", title, macos_body)

        return tg_success

    def send_initial_snapshot(self, wikifolio_name: str, symbol: str, portfolio_data: dict) -> bool:
        """
        Sendet nach dem ersten Start eine Übersicht des aktuellen Depots.
        """
        title = f"🟢 Wikifolio Tracker gestartet: {wikifolio_name}"
        lines = [
            f"Symbol: <b>{html.escape(symbol)}</b>",
            f"Link: <a href='https://www.wikifolio.com/de/de/w/{symbol}#portfolio'>Wikifolio Portfolio</a>\n",
            "<b>📊 Aktueller Depotbestand:</b>"
        ]

        cash_pct = portfolio_data.get("cash_percentage", 0.0)
        positions = portfolio_data.get("positions", {})

        if not positions:
            lines.append("<i>Keine Aktienpositionen im Depot (100% Cash).</i>")
        else:
            for isin, pos in positions.items():
                name = pos.get("name", "Unbekannt")
                pct = pos.get("percentage", 0.0)
                qty = pos.get("quantity", 0.0)
                perf = pos.get("performance_since_buy")
                perf_str = f" ({perf:+.2f}%)" if perf is not None else ""
                lines.append(f"• <b>{html.escape(name)}</b>: <b>{pct:.2f}%</b> (Stk: {qty:.2f}){perf_str}")

        lines.append(f"\n💰 <b>Cashquote:</b> {cash_pct:.2f}%")
        lines.append(f"\n<i>Der Tracker prüft ab jetzt automatisch auf Änderungen.</i>")

        return self.notify(title, "\n".join(lines), f"Tracking für {wikifolio_name} aktiv.")

    def send_changes_alert(self, wikifolio_name: str, symbol: str, changes: list[dict], current_portfolio: dict) -> bool:
        """
        Sendet eine strukturierte Benachrichtigung bei festgestellten Depot-Änderungen.
        """
        title = f"🚨 ÄNDERUNG IM DEPOT: {wikifolio_name}"
        lines = []

        # Änderungen auflisten
        for c in changes:
            ctype = c.get("type")
            name = html.escape(c.get("name", ""))
            isin = c.get("isin", "")

            if ctype == "BUY_NEW":
                pct = c.get("percentage", 0.0)
                qty = c.get("quantity", 0.0)
                price = c.get("purchase_price")
                price_str = f" zu {price:.2f} €" if price else ""
                lines.append(f"🟢 <b>NEUE POSITION GEKAUFT</b>\n• Aktie: <b>{name}</b> ({isin})\n• Depot-Anteil: <b>{pct:.2f}%</b> (Stk: {qty:.2f}){price_str}\n")

            elif ctype == "SELL_ALL":
                old_pct = c.get("old_percentage", 0.0)
                lines.append(f"🔴 <b>POSITION VOLLSTÄNDIG VERKAUFT</b>\n• Aktie: <b>{name}</b> ({isin})\n• Vorheriger Anteil: {old_pct:.2f}%\n")

            elif ctype == "INCREASE":
                old_pct = c.get("old_percentage", 0.0)
                new_pct = c.get("new_percentage", 0.0)
                diff = new_pct - old_pct
                lines.append(f"📈 <b>POSITION AUFGESTOCKT</b>\n• Aktie: <b>{name}</b> ({isin})\n• Anteil erhöht von {old_pct:.2f}% auf <b>{new_pct:.2f}%</b> (+{diff:.2f}%)\n")

            elif ctype == "DECREASE":
                old_pct = c.get("old_percentage", 0.0)
                new_pct = c.get("new_percentage", 0.0)
                diff = old_pct - new_pct
                lines.append(f"📉 <b>TEILVERKAUF DURCHGEFÜHRT</b>\n• Aktie: <b>{name}</b> ({isin})\n• Anteil reduziert von {old_pct:.2f}% auf <b>{new_pct:.2f}%</b> (-{diff:.2f}%)\n")

            elif ctype == "CASH_CHANGED":
                old_cash = c.get("old_cash", 0.0)
                new_cash = c.get("new_cash", 0.0)
                lines.append(f"💵 <b>CASHQUOTE GEÄNDERT</b>\n• Von {old_cash:.2f}% auf <b>{new_cash:.2f}%</b>\n")

        # Aktueller Depotbestand als Zusammenfassung anhängen
        lines.append("<b>📋 Neuer Depotbestand:</b>")
        positions = current_portfolio.get("positions", {})
        if not positions:
            lines.append("<i>Keine Aktienpositionen (100% Cash)</i>")
        else:
            for isin, pos in positions.items():
                pname = html.escape(pos.get("name", "Unbekannt"))
                ppct = pos.get("percentage", 0.0)
                lines.append(f"• {pname}: <b>{ppct:.2f}%</b>")

        cash_pct = current_portfolio.get("cash_percentage", 0.0)
        lines.append(f"• Cash: <b>{cash_pct:.2f}%</b>")
        lines.append(f"\n<a href='https://www.wikifolio.com/de/de/w/{symbol}#portfolio'>Portfolio auf Wikifolio ansehen</a>")

        short_summary = f"{len(changes)} Änderung(en) in {wikifolio_name} festgestellt!"
        return self.notify(title, "\n".join(lines), short_summary)
