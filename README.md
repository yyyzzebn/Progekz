# Proaktiver Alltags-Copilot

Eine Entscheidungs- und Prioritäts-Maschine, die proaktiv bei Prioritäten,
Finanzen und Selbstreflexion unterstützt. Siehe das technische Spec für Vision
und Baureihenfolge.

## Status

**Schritt 1 — Projekt-Setup** ✅
FastAPI-Grundgerüst, Settings über `.env` (pydantic-settings), SQLite-Anbindung
und das vollständige Datenmodell (Abschnitt 4) sind angelegt. Beim Start der App
werden alle Tabellen automatisch erstellt.

**Schritt 2 — Telegram-Bot-Grundgerüst** ✅
Bot reagiert auf `/start`, speichert die `chat_id` des Nutzers in der Datenbank
(legt bei Bedarf einen User an) und spiegelt jede sonstige Textnachricht als
Echo zurück. Beweist die Zustell-Schleife.

**Schritt 3 — Eingabe-Befehle** ✅
Manuelle Dateneingabe per Telegram in die Tabellen aus Abschnitt 4:

| Befehl | Beispiel | Tabelle |
|---|---|---|
| `/task <titel> <YYYY-MM-DD>` | `/task Klausur lernen 2026-06-20` | `tasks` |
| `/ausgabe <betrag> <kategorie>` | `/ausgabe 12.50 Essen` | `transactions` (negativ = Ausgabe) |
| `/mood <energie 1-5> <stimmung 1-5>` | `/mood 4 3 müde` | `mood_logs` |
| `/budget <week\|month> <kat> <betrag>` | `/budget week Essen 80` | `budgets` |

Eingaben werden validiert (Datum, Wertebereich 1–5, Betrag); unbekannte Nutzer
werden zuerst auf `/start` verwiesen. Betrag akzeptiert `12.50` und `12,50`.

Noch offen (Baureihenfolge, Abschnitt 9): Google-Calendar-Sync, das „Gehirn",
tägliches Briefing, Finanz-Coach, Wochenreflexion.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # Werte nach Bedarf ausfüllen
```

## Starten

```bash
uvicorn app.main:app --reload
```

Danach erreichbar:
- `http://127.0.0.1:8000/` — Status
- `http://127.0.0.1:8000/health` — Health-Check
- `http://127.0.0.1:8000/docs` — interaktive API-Doku (Swagger UI)

Die SQLite-Datei (Standard: `copilot.db`) wird beim ersten Start automatisch
mit allen Tabellen angelegt.

## Telegram-Bot (Schritt 2)

1. Bot bei [@BotFather](https://t.me/BotFather) anlegen und den Token in die
   `.env` eintragen: `TELEGRAM_BOT_TOKEN="..."`.
2. Bot per Long-Polling starten:

   ```bash
   python -m app.bot
   ```

3. In Telegram dem Bot `/start` schicken → die `chat_id` wird gespeichert.
   Jede weitere Nachricht wird als Echo zurückgespiegelt (Verbindungstest).

Der Bot läuft als eigener Prozess (Long-Polling); die FastAPI-App muss dafür
nicht laufen. Beide teilen sich dieselbe SQLite-Datenbank.

## Projektstruktur

```
app/
  config.py     # pydantic-settings (.env-Anbindung)
  database.py   # SQLAlchemy-Engine, Session, init_db()
  models.py     # ORM-Modelle = Datenmodell aus Abschnitt 4
  main.py       # FastAPI-App + Lifespan (DB-Init) + Health-Endpoints
  bot.py        # Telegram-Bot: /start, /task, /ausgabe, /mood, /budget, Echo
  crud.py       # Persistenz-Helfer (Anlegen/Lesen) auf dem Datenmodell
```
