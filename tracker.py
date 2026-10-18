#!/usr/bin/env python3
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import config
from wikifolio_client import WikifolioClient
from notifier import Notifier

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Tracker")


def load_previous_state() -> Optional[Dict[str, Any]]:
    """
    Lädt den zuletzt gespeicherten Depotbestand.
    """
    if not config.STATE_FILE.exists():
        return None
    try:
        with open(config.STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden des vorherigen Zustands: {e}")
        return None


def save_state(state: Dict[str, Any]) -> None:
    """
    Speichert den aktuellen Depotbestand auf der Festplatte.
    """
    try:
        with open(config.STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Fehler beim Speichern des Zustands: {e}")


def log_history(entry_type: str, details: Any) -> None:
    """
    Protokolliert Änderungen chronologisch in einer JSONL-Datei.
    """
    try:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": entry_type,
            "details": details
        }
        with open(config.HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Konnte Historie nicht schreiben: {e}")


def detect_changes(prev_portfolio: Dict[str, Any], curr_portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Vergleicht zwei Portfolio-Zustände und ermittelt Käufe, Verkäufe und Gewichtungsänderungen.
    """
    changes: List[Dict[str, Any]] = []

    prev_positions = prev_portfolio.get("positions", {})
    curr_positions = curr_portfolio.get("positions", {})

    prev_keys = set(prev_positions.keys())
    curr_keys = set(curr_positions.keys())

    # 1. Neu gekaufte Positionen
    new_keys = curr_keys - prev_keys
    for k in new_keys:
        pos = curr_positions[k]
        changes.append({
            "type": "BUY_NEW",
            "isin": pos.get("isin", k),
            "name": pos.get("name", "Unbekannt"),
            "percentage": pos.get("percentage", 0.0),
            "quantity": pos.get("quantity", 0.0),
            "purchase_price": pos.get("average_purchase_price")
        })

    # 2. Vollständig verkaufte Positionen
    removed_keys = prev_keys - curr_keys
    for k in removed_keys:
        pos = prev_positions[k]
        changes.append({
            "type": "SELL_ALL",
            "isin": pos.get("isin", k),
            "name": pos.get("name", "Unbekannt"),
            "old_percentage": pos.get("percentage", 0.0)
        })

    # 3. Bestehende Positionen: Änderungen an Gewichtung oder Stückzahl
    common_keys = prev_keys & curr_keys
    for k in common_keys:
        prev_pos = prev_positions[k]
        curr_pos = curr_positions[k]

        old_pct = prev_pos.get("percentage", 0.0)
        new_pct = curr_pos.get("percentage", 0.0)
        old_qty = prev_pos.get("quantity", 0.0)
        new_qty = curr_pos.get("quantity", 0.0)

        pct_diff = round(new_pct - old_pct, 2)
        qty_diff = round(new_qty - old_qty, 4)

        # Schwelle: Relevante Änderung ab 0.2% Gewichtung oder Stückzahländerung
        if abs(pct_diff) >= 0.2 or abs(qty_diff) > 0.001:
            if pct_diff > 0:
                changes.append({
                    "type": "INCREASE",
                    "isin": curr_pos.get("isin", k),
                    "name": curr_pos.get("name", "Unbekannt"),
                    "old_percentage": old_pct,
                    "new_percentage": new_pct,
                    "old_quantity": old_qty,
                    "new_quantity": new_qty
                })
            else:
                changes.append({
                    "type": "DECREASE",
                    "isin": curr_pos.get("isin", k),
                    "name": curr_pos.get("name", "Unbekannt"),
                    "old_percentage": old_pct,
                    "new_percentage": new_pct,
                    "old_quantity": old_qty,
                    "new_quantity": new_qty
                })

    # 4. Signifikante Änderung der Cashquote (ab 0.5% Differenz)
    old_cash = prev_portfolio.get("cash_percentage", 0.0)
    new_cash = curr_portfolio.get("cash_percentage", 0.0)
    if abs(round(new_cash - old_cash, 2)) >= 0.5:
        # Nur aufnehmen, wenn nicht bereits Käufe/Verkäufe dasselbe erklären
        changes.append({
            "type": "CASH_CHANGED",
            "old_cash": old_cash,
            "new_cash": new_cash
        })

    return changes


def run_check(client: WikifolioClient, notifier: Notifier) -> str:
    """
    Führt eine einzelne Depotüberprüfung durch.
    Gibt den Status ('market_closed', 'initial', 'changes', 'no_changes') zurück.
    """
    if not config.is_market_open():
        logger.info("Außerhalb der Börsenzeiten (08:00 - 22:00 Uhr Mo-Fr). Prüfung übersprungen.")
        return "market_closed"

    logger.info(f"Überprüfe Depot '{config.WIKIFOLIO_SYMBOL}' (ID: {config.WIKIFOLIO_ID})...")
    curr_portfolio = client.get_portfolio(config.WIKIFOLIO_ID)
    curr_portfolio["timestamp"] = datetime.now(timezone.utc).isoformat()

    prev_state = load_previous_state()

    # Fall 1: Erster Start / Kein vorheriger Zustand vorhanden
    if prev_state is None:
        logger.info("Kein vorheriger Depotzustand vorhanden. Erstelle initiale Momentaufnahme...")
        save_state(curr_portfolio)
        log_history("INITIAL_SNAPSHOT", curr_portfolio)

        notifier.send_initial_snapshot(
            wikifolio_name="NoLimits",
            symbol=config.WIKIFOLIO_SYMBOL,
            portfolio_data=curr_portfolio
        )
        logger.info("✅ Initiale Momentaufnahme gespeichert und Bestätigung gesendet.")
        return "initial"

    # Fall 2: Vergleich mit vorherigem Zustand
    changes = detect_changes(prev_state, curr_portfolio)

    if changes:
        logger.info(f"🚨 {len(changes)} Änderung(en) im Depot festgestellt!")
        for c in changes:
            logger.info(f"  -> {c.get('type')}: {c.get('name')} ({c.get('isin', '')})")

        notifier.send_changes_alert(
            wikifolio_name="NoLimits",
            symbol=config.WIKIFOLIO_SYMBOL,
            changes=changes,
            current_portfolio=curr_portfolio
        )

        save_state(curr_portfolio)
        log_history("CHANGES_DETECTED", {"changes": changes, "portfolio": curr_portfolio})
        return "changes"
    else:
        logger.info("Keine Änderungen im Depot festgestellt.")
        return "no_changes"


def print_status(client: WikifolioClient) -> None:
    """
    Holt das aktuelle Depot ab und gibt es formatiert auf der Konsole aus.
    """
    print(f"\n📊 Abruf des aktuellen Depots für '{config.WIKIFOLIO_SYMBOL}'...")
    portfolio = client.get_portfolio(config.WIKIFOLIO_ID)

    positions = portfolio.get("positions", {})
    cash_pct = portfolio.get("cash_percentage", 0.0)

    print("\n" + "=" * 65)
    print(f" WIKIFOLIO: NoLimits ({config.WIKIFOLIO_SYMBOL})")
    print("=" * 65)
    if not positions:
        print(" Keine Aktienpositionen im Depot (100% Cash)")
    else:
        print(f"{'AKTIENNAME':<28} {'ISIN':<14} {'ANTEIL':<10} {'STÜCK':<10}")
        print("-" * 65)
        for isin, pos in positions.items():
            name = pos.get("name", "Unbekannt")[:26]
            pct = pos.get("percentage", 0.0)
            qty = pos.get("quantity", 0.0)
            print(f"{name:<28} {isin:<14} {pct:>6.2f}%   {qty:>8.2f}")

    print("-" * 65)
    print(f"{'BARBESTAND (CASH)':<43} {cash_pct:>6.2f}%")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Wikifolio Depot Tracker & Notifier")
    parser.add_argument("--once", action="store_true", help="Führt eine einmalige Prüfung durch und beendet das Skript")
    parser.add_argument("--daemon", action="store_true", help="Startet die kontinuierliche Überwachung im Hintergrund")
    parser.add_argument("--status", action="store_true", help="Zeigt das aktuelle Depot in der Konsole an")
    parser.add_argument("--test-notify", action="store_true", help="Sendet eine Testnachricht an Telegram")
    parser.add_argument("--reset", action="store_true", help="Löscht den gespeicherten Zustand (erzwingt neue Initialisierung)")
    args = parser.parse_args()

    # Reset
    if args.reset:
        if config.STATE_FILE.exists():
            config.STATE_FILE.unlink()
            print("✅ Gespeicherter Depotzustand wurde gelöscht.")
        else:
            print("Kein gespeicherter Zustand vorhanden.")
        return

    notifier = Notifier()

    # Testnachricht
    if args.test_notify:
        print("Sende Testnachricht an Telegram...")
        if not notifier.has_telegram:
            print("❌ Fehler: TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlen in .env.")
            sys.exit(1)
        success = notifier.send_telegram(
            "🔔 <b>Testnachricht vom Wikifolio-Tracker</b>\n\n"
            "Die Telegram-Verbindung funktioniert einwandfrei! Du wirst benachrichtigt, sobald sich das Depot von NoLimits verändert."
        )
        if success:
            print("✅ Testnachricht erfolgreich an Telegram gesendet!")
        else:
            print("❌ Fehler beim Senden der Testnachricht. Bitte Token und Chat-ID prüfen.")
        return

    # Konfiguration validieren
    errors = config.validate_config(require_telegram=not args.status)
    if errors:
        print("\n❌ KONFIGURATIONSFEHLER:")
        for err in errors:
            print(f"  • {err}")
        print("\nBitte bearbeite die Datei '.env' und trage deine Zugangsdaten ein.")
        print("Eine Vorlage findest du in '.env.example'.\n")
        sys.exit(1)

    client = WikifolioClient()

    # Status ausgeben
    if args.status:
        try:
            print_status(client)
        except Exception as e:
            logger.error(f"Fehler beim Abruf: {e}")
            sys.exit(1)
        return

    # Einmalige Prüfung
    if args.once:
        try:
            res = run_check(client, notifier)
            print(f"Prüfung beendet mit Ergebnis: {res}")
        except Exception as e:
            logger.error(f"Fehler bei der Prüfung: {e}")
            sys.exit(1)
        return

    # Kontinuierlicher Modus (Daemon)
    if args.daemon:
        interval = config.CHECK_INTERVAL_SECONDS
        print(f"\n🚀 Starte Wikifolio-Tracker für '{config.WIKIFOLIO_SYMBOL}'...")
        print(f"⏱️  Intervall: alle {interval} Sekunden ({interval // 60} Minuten)")
        print(f"🕒 Börsenzeiten-Filter: {'Aktiv (08:00 - 22:00 Mo-Fr)' if config.MARKET_HOURS_ONLY else 'Inaktiv (24/7)'}")
        print("Drücke Strg+C zum Beenden.\n")

        try:
            while True:
                try:
                    run_check(client, notifier)
                except Exception as e:
                    logger.error(f"Unerwarteter Fehler im Durchlauf: {e}")

                logger.info(f"Warte {interval} Sekunden bis zur nächsten Prüfung...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 Tracker wurde durch den Benutzer beendet.")
            sys.exit(0)

    # Standard-Verhalten ohne Argumente: Hilfe anzeigen
    parser.print_help()


if __name__ == "__main__":
    main()
