import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Basisverzeichnisse
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Lade .env Datei falls vorhanden
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

# Wikifolio Konfiguration
WIKIFOLIO_EMAIL = os.getenv("WIKIFOLIO_EMAIL", "").strip()
WIKIFOLIO_PASSWORD = os.getenv("WIKIFOLIO_PASSWORD", "").strip()
WIKIFOLIO_ID = os.getenv("WIKIFOLIO_ID", "485772de-e808-4451-8a53-1fc0378d3b87").strip()
WIKIFOLIO_SYMBOL = os.getenv("WIKIFOLIO_SYMBOL", "wfnolimits").strip()

# Telegram Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Tracking Konfiguration
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "7200"))  # Standard: 2 Stunden
MARKET_HOURS_ONLY = os.getenv("MARKET_HOURS_ONLY", "true").lower() in ("true", "1", "yes")
ENABLE_MACOS_NOTIFICATIONS = os.getenv("ENABLE_MACOS_NOTIFICATIONS", "true").lower() in ("true", "1", "yes")

# Pfade für Datenhaltung
STATE_FILE = DATA_DIR / "portfolio_state.json"
SESSION_FILE = DATA_DIR / "session_cookie.json"
HISTORY_FILE = DATA_DIR / "history.jsonl"


def is_market_open() -> bool:
    """
    Prüft, ob der deutsche Aktienmarkt (L&S / Tradegate, 08:00 - 22:00 CET Mo-Fr) geöffnet ist.
    Gibt immer True zurück, falls MARKET_HOURS_ONLY deaktiviert ist.
    """
    if not MARKET_HOURS_ONLY:
        return True

    try:
        from zoneinfo import ZoneInfo
        local_time = datetime.now(ZoneInfo("Europe/Berlin"))
    except Exception:
        # Fallback bei fehlenden Zeitzonendaten
        now_utc = datetime.now(timezone.utc)
        is_dst = 3 <= now_utc.month <= 10
        tz_offset = timedelta(hours=2 if is_dst else 1)
        local_time = now_utc + tz_offset

    # Wochentag: Montag (0) bis Freitag (4)
    weekday = local_time.weekday()
    if weekday > 4:
        return False

    # Handelszeit: 08:00 bis 22:00 Uhr
    hour = local_time.hour
    minute = local_time.minute
    total_minutes = hour * 60 + minute

    start_minutes = 8 * 60   # 08:00
    end_minutes = 22 * 60    # 22:00

    return start_minutes <= total_minutes <= end_minutes


def validate_config(require_telegram: bool = True) -> list[str]:
    """
    Überprüft die Konfiguration und gibt fehlende Einstellungen zurück.
    """
    errors = []
    if not WIKIFOLIO_EMAIL or WIKIFOLIO_EMAIL == "deine-email@beispiel.de":
        errors.append("WIKIFOLIO_EMAIL ist weder in .env noch als GitHub Secret gesetzt.")
    if not WIKIFOLIO_PASSWORD or WIKIFOLIO_PASSWORD == "dein-geheimes-passwort":
        errors.append("WIKIFOLIO_PASSWORD ist weder in .env noch als GitHub Secret gesetzt.")
    if require_telegram:
        if not TELEGRAM_BOT_TOKEN or "ABCdefGh" in TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN ist weder in .env noch als GitHub Secret gesetzt.")
        if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "123456789":
            errors.append("TELEGRAM_CHAT_ID ist weder in .env noch als GitHub Secret gesetzt.")
    return errors
