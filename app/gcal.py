"""Google-Calendar-Sync, read-only (Spec, Abschnitt 9, Schritt 4).

Holt per OAuth (Scope: calendar.readonly) die kommenden Termine und schreibt sie
idempotent in die `events`-Tabelle: jedes Event trägt source='gcal' und die
Google-Event-ID als `external_id`, sodass ein erneuter Sync vorhandene Einträge
aktualisiert statt zu duplizieren.

Die OAuth-Client-Zugangsdaten kommen ausschließlich aus der `.env`
(GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) — niemals aus dem Code (Abschnitt 10).
Das ausgehandelte Token wird in GOOGLE_TOKEN_FILE (gitignored) gespeichert.

Aufbau bewusst getrennt:
  * `authorize()`       — einmalige, interaktive OAuth-Zustimmung (lokal).
  * `load_credentials()`— nicht-interaktiv: lädt/erneuert Token (scheduler-tauglich).
  * `sync_calendar()`   — die Funktion, die der Scheduler später periodisch ruft.
  * `_normalize_event` / `sync_events_to_db` — netzfreie Logik, gut testbar.

CLI:
    python -m app.gcal auth     # einmalig: Google-Zugriff freigeben (lokal)
    python -m app.gcal sync     # Termine holen und in die DB schreiben
"""

import argparse
import logging
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app import crud
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import User

logger = logging.getLogger(__name__)
settings = get_settings()

# Read-only — die App bekommt ausdrücklich keinen Schreibzugriff.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Zeithorizont des Sync: ab jetzt so viele Tage in die Zukunft.
SYNC_DAYS = 30
MAX_RESULTS = 250


# --- OAuth / Credentials -------------------------------------------------

def _client_config() -> dict:
    """Baut die OAuth-Client-Config aus den .env-Werten (statt credentials.json)."""
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET fehlen. Bitte in der .env "
            "setzen (siehe .env.example)."
        )
    return {
        "installed": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def authorize():
    """Einmalige, interaktive OAuth-Zustimmung. Speichert das Token.

    Öffnet lokal einen Browser/Consent-Screen. Danach genügt
    `load_credentials()` (Token wird automatisch erneuert).
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
    creds = flow.run_local_server(port=0)
    with open(settings.google_token_file, "w") as fh:
        fh.write(creds.to_json())
    logger.info("Google-Token gespeichert in %s", settings.google_token_file)
    return creds


def load_credentials():
    """Lädt das gespeicherte Token und erneuert es bei Bedarf (nicht-interaktiv).

    Bewusst ohne Browser-Flow, damit der Scheduler nie an einem Consent-Screen
    hängenbleibt. Fehlt das Token, wird klar auf `authorize()` verwiesen.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_path = settings.google_token_file
    if not os.path.exists(token_path):
        raise RuntimeError(
            f"Kein Google-Token ({token_path}). Bitte einmalig "
            "`python -m app.gcal auth` ausführen."
        )

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as fh:
                fh.write(creds.to_json())
        else:
            raise RuntimeError(
                "Google-Token ungültig und nicht erneuerbar. Bitte erneut "
                "`python -m app.gcal auth` ausführen."
            )
    return creds


# --- Event-Normalisierung (netzfrei, testbar) ----------------------------

def _parse_time_node(node: dict) -> datetime:
    """Wandelt ein Google start/end-Node in eine naive lokale datetime.

    Google liefert entweder 'dateTime' (mit Zeitzone) oder 'date' (ganztägig).
    Zeitbehaftete Werte werden in die DEFAULT_TIMEZONE umgerechnet und naiv
    gespeichert (das DB-Modell führt naive Zeitstempel).
    """
    if "dateTime" in node:
        dt = datetime.fromisoformat(node["dateTime"])
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo(settings.default_timezone))
            dt = dt.replace(tzinfo=None)
        return dt
    # Ganztägig: 'date' = YYYY-MM-DD
    d = date.fromisoformat(node["date"])
    return datetime(d.year, d.month, d.day)


def _normalize_event(item: dict) -> dict | None:
    """Macht aus einem Google-API-Event ein flaches Dict für die DB.

    Gibt None zurück, wenn das Event übersprungen werden soll (abgesagt oder
    ohne brauchbare Zeitangaben).
    """
    if item.get("status") == "cancelled":
        return None
    start, end = item.get("start"), item.get("end")
    ext_id = item.get("id")
    if not ext_id or not start or not end:
        return None
    try:
        start_at = _parse_time_node(start)
        end_at = _parse_time_node(end)
    except (KeyError, ValueError):
        return None
    return {
        "external_id": ext_id,
        "title": item.get("summary") or "(ohne Titel)",
        "start_at": start_at,
        "end_at": end_at,
    }


def sync_events_to_db(
    session: Session, user_id: int, normalized: list[dict]
) -> dict:
    """Schreibt normalisierte Events idempotent in die DB. Committet einmal."""
    created = updated = 0
    for ev in normalized:
        is_new = crud.upsert_gcal_event(
            session,
            user_id=user_id,
            external_id=ev["external_id"],
            title=ev["title"],
            start_at=ev["start_at"],
            end_at=ev["end_at"],
        )
        if is_new:
            created += 1
        else:
            updated += 1
    session.commit()
    return {"created": created, "updated": updated, "total": len(normalized)}


# --- Sync (mit Netz) -----------------------------------------------------

def _fetch_events(creds) -> list[dict]:
    """Holt die kommenden Termine über die Calendar API (singleEvents)."""
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=SYNC_DAYS)).isoformat()
    result = (
        service.events()
        .list(
            calendarId=settings.google_calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=MAX_RESULTS,
        )
        .execute()
    )
    return result.get("items", [])


def sync_calendar(user_id: int) -> dict:
    """Holt die Termine und schreibt sie für den User in die `events`-Tabelle.

    Das ist die Funktion, die der Scheduler später periodisch (alle 30 Min)
    aufruft. Liefert Zähler {created, updated, total}.
    """
    creds = load_credentials()
    items = _fetch_events(creds)
    normalized = [n for n in (_normalize_event(i) for i in items) if n]
    with SessionLocal() as session:
        stats = sync_events_to_db(session, user_id, normalized)
    logger.info(
        "Kalender-Sync user_id=%s: %s neu, %s aktualisiert (von %s API-Events)",
        user_id,
        stats["created"],
        stats["updated"],
        len(items),
    )
    return stats


def sync_all_users() -> dict:
    """Synchronisiert den Kalender für alle bekannten User.

    Im MVP gibt es i.d.R. genau einen User. Der Scheduler kann diese Funktion
    direkt anbinden.
    """
    with SessionLocal() as session:
        user_ids = [u.id for u in session.query(User).all()]
    if not user_ids:
        logger.warning("Kein User vorhanden — bitte zuerst /start im Bot.")
        return {"users": 0}

    totals = {"users": 0, "created": 0, "updated": 0, "total": 0}
    for uid in user_ids:
        stats = sync_calendar(uid)
        totals["users"] += 1
        for key in ("created", "updated", "total"):
            totals[key] += stats[key]
    return totals


# --- CLI -----------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    parser = argparse.ArgumentParser(description="Google-Calendar-Sync (read-only)")
    parser.add_argument(
        "command",
        choices=["auth", "sync"],
        help="auth = einmalige OAuth-Freigabe, sync = Termine in die DB holen",
    )
    args = parser.parse_args()

    init_db()
    if args.command == "auth":
        authorize()
        print("✅ Google-Zugriff freigegeben. Jetzt: python -m app.gcal sync")
    else:
        stats = sync_all_users()
        print(f"✅ Sync fertig: {stats}")


if __name__ == "__main__":
    main()
