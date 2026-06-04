# Proaktiver Alltags-Copilot

Eine Entscheidungs- und Prioritäts-Maschine, die proaktiv bei Prioritäten,
Finanzen und Selbstreflexion unterstützt. Siehe das technische Spec für Vision
und Baureihenfolge.

## Status

**Schritt 1 — Projekt-Setup** ✅
FastAPI-Grundgerüst, Settings über `.env` (pydantic-settings), SQLite-Anbindung
und das vollständige Datenmodell (Abschnitt 4) sind angelegt. Beim Start der App
werden alle Tabellen automatisch erstellt.

Noch offen (Baureihenfolge, Abschnitt 9): Telegram-Bot, Eingabe-Befehle,
Google-Calendar-Sync, das „Gehirn", tägliches Briefing, Finanz-Coach,
Wochenreflexion.

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

## Projektstruktur

```
app/
  config.py     # pydantic-settings (.env-Anbindung)
  database.py   # SQLAlchemy-Engine, Session, init_db()
  models.py     # ORM-Modelle = Datenmodell aus Abschnitt 4
  main.py       # FastAPI-App + Lifespan (DB-Init) + Health-Endpoints
```
