# 📈 Wikifolio Depot Tracker & Notifier

Automatischer Tracker für das Wikifolio **NoLimits (`wfnolimits`)** (oder jedes andere Wikifolio). Erkennt Depot-Änderungen (Kauf neuer Aktien, Verkauf, Aufstockung, Teilverkauf, Cashquoten-Änderung) und sendet sofortige Benachrichtigungen per **Telegram Push-Nachricht** und optionaler **macOS Desktop-Mitteilung**.

---

## ⚡ Schnellstart in 3 Schritten

### 1. Telegram-Bot erstellen (2 Minuten)
1. Öffne Telegram und suche nach **[@BotFather](https://t.me/botfather)**.
2. Sende `/newbot` und wähle einen Namen sowie Benutzernamen (z. B. `MeinDepotTrackerBot`).
3. Kopiere das ausgegebene **HTTP API Token** (z. B. `123456789:ABCdefGhIJK...`).
4. Öffne deinen neu erstellten Bot in Telegram und klicke auf **Start** (oder sende ihm eine beliebige Nachricht wie `Hallo`).
5. Ermittle deine persönliche **Chat-ID**:
   - Suche in Telegram nach **[@userinfobot](https://t.me/userinfobot)** und starte ihn. Er zeigt dir direkt deine `Id` (z. B. `987654321`) an.

---

### 2. Konfiguration anlegen (`.env`)
Erstelle eine Datei `.env` im Projektordner (du kannst die Vorlage `.env.example` kopieren):

```bash
cp .env.example .env
```

Öffne `.env` und trage deine Zugangsdaten ein:

```env
# Wikifolio Login (kostenloser Account)
WIKIFOLIO_EMAIL=deine-email@beispiel.de
WIKIFOLIO_PASSWORD=dein-passwort

# Telegram Benachrichtigungen
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=987654321

# Überprüfungsintervall (in Sekunden, z. B. 900 = 15 Minuten)
CHECK_INTERVAL_SECONDS=900

# Nur zu Handelszeiten prüfen (Mo-Fr, 08:00 - 22:00 Uhr)
MARKET_HOURS_ONLY=true
```

---

### 3. Verbindung testen & Tracker starten

#### A. Telegram-Benachrichtigung testen
```bash
./run.sh --test-notify
```
*Sendet sofort eine Testnachricht an dein Smartphone/Telegram.*

#### B. Aktuelles Depot in der Konsole ansehen
```bash
./run.sh --status
```
*Gibt den aktuellen Depotbestand (Aktien, Anteile, Stückzahlen, Cashquote) übersichtlich im Terminal aus.*

#### C. Tracker starten (Dauerüberwachung)
```bash
./run.sh --daemon
```
*Prüft das Depot fortlaufend im eingestellten Intervall (z. B. alle 15 Minuten). Beim ersten Start wird eine Bestätigung des aktuellen Depots versendet. Sobald eine Transaktion stattfindet, erhältst du eine Benachrichtigung!*

---

## 🔔 Beispiel-Benachrichtigung in Telegram

```
🚨 ÄNDERUNG IM DEPOT: NoLimits

🟢 NEUE POSITION GEKAUFT
• Aktie: NVIDIA Corp. (US67066G1040)
• Depot-Anteil: 24.50% (Stk: 120.00) zu 118.40 €

🔴 POSITION VOLLSTÄNDIG VERKAUFT
• Aktie: Tesla Inc. (US88160R1014)
• Vorheriger Anteil: 22.10%

📋 Neuer Depotbestand:
• NVIDIA Corp.: 24.50%
• Apple Inc.: 45.20%
• Cash: 30.30%
```

---

## 🛠️ CLI-Optionen

| Befehl | Beschreibung |
|---|---|
| `./run.sh --daemon` | Startet den Tracker im Dauerbetrieb mit dem konfigurierten Intervall |
| `./run.sh --once` | Führt genau eine Überprüfung durch und beendet sich (z. B. für Cronjobs) |
| `./run.sh --status` | Zeigt das aktuelle Wikifolio-Depot im Terminal an |
| `./run.sh --test-notify` | Sendet eine Testnachricht an Telegram |
| `./run.sh --reset` | Löscht den lokalen Depot-Cache (erzwingt neue Initialisierung) |

---

## 🖥️ Als automatischer macOS-Hintergrunddienst einrichten (LaunchAgent)

Damit der Tracker auch nach einem Neustart des Macs immer unsichtbar im Hintergrund weiterläuft:

1. Kopiere die vorgefertigte Datei `com.user.wikifoliotracker.plist` in deinen LaunchAgents-Ordner:
   ```bash
   cp com.user.wikifoliotracker.plist ~/Library/LaunchAgents/
   ```

2. Aktiviere den Dienst:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.user.wikifoliotracker.plist
   ```

3. Logdateien ansehen:
   ```bash
   tail -f data/tracker.stdout.log
   ```

4. Dienst stoppen / deaktivieren:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.user.wikifoliotracker.plist
   ```

---

## 📁 Projektstruktur

```
AktienCrawler/
├── .env.example                  # Vorlage für Zugangsdaten & Einstellungen
├── .env                          # Deine privaten Zugangsdaten (wird nicht committet)
├── config.py                     # Konfigurations- & Validierungslogik
├── notifier.py                   # Telegram- und macOS-Benachrichtigungen
├── wikifolio_client.py           # Wikifolio API-Client mit Session-Verwaltung
├── tracker.py                    # Hauptlogik: Diff-Erkennung, Cache, Daemon
├── run.sh                        # Komfortables Start-Skript
├── com.user.wikifoliotracker.plist # macOS Hintergrunddienst
├── tests/
│   └── test_tracker.py           # Unit-Tests
└── data/                         # Automatisch erstellte lokale Daten
    ├── portfolio_state.json      # Letzter bekannter Depotzustand
    ├── session_cookie.json       # Wikifolio Login-Session
    └── history.jsonl             # Chronologisches Änderungsprotokoll
```
