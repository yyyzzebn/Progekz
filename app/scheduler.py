"""Scheduler (Spec, Abschnitt 8) — proaktive Trigger über APScheduler.

Schritt 6: morgens (zur konfigurierbaren Weckzeit, in der Zeitzone des jeweiligen
Nutzers) für jeden Nutzer `run_brain("daily_briefing")` aufrufen und das Ergebnis
per Telegram schicken.

Erweiterbar gehalten: jeder Job ist ein „Registrar" in JOB_REGISTRARS. Weitere
Trigger (Budget-Check, Wochenreflexion, Video-Modul …) werden später als eigene
Funktion ergänzt und der Liste hinzugefügt — bestehender Code bleibt unberührt.

Starten:
    python -m app.scheduler
"""

import logging
from collections.abc import Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app import bot, crud
from app.brain import run_brain
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import User

logger = logging.getLogger(__name__)
settings = get_settings()


# --- Briefing-Job --------------------------------------------------------

def _briefing_time() -> tuple[int, int]:
    hour, minute = settings.briefing_time.split(":")
    return int(hour), int(minute)


def format_briefing(result: dict) -> str:
    """Formatiert das run_brain-Ergebnis (daily_briefing) für Telegram."""
    lines = [result.get("briefing_text", "").strip()]

    priorities = result.get("top_priorities") or []
    if priorities:
        lines += ["", "🎯 Top-Prioritäten:"]
        for p in priorities:
            line = f"• {p.get('task', '')}"
            if p.get("suggested_slot"):
                line += f" ({p['suggested_slot']})"
            if p.get("why"):
                line += f" — {p['why']}"
            lines.append(line)

    warnings = result.get("warnings") or []
    if warnings:
        lines += ["", "⚠️ Hinweise:"]
        lines += [f"• {w}" for w in warnings]

    if result.get("overload_flag"):
        lines += ["", "🔺 Überlast erkannt."]
        drops = result.get("drop_suggestions") or []
        if drops:
            lines.append("Streichen kannst du:")
            lines += [f"• {d}" for d in drops]

    return "\n".join(lines).strip()


def send_daily_briefing(user_id: int) -> None:
    """Job: Briefing für einen Nutzer erzeugen und per Telegram senden.

    Fehler werden geloggt, aber nicht weitergeworfen — ein Problem bei einem
    Nutzer (LLM-/Telegram-Fehler) darf den Scheduler nicht stoppen.
    """
    with SessionLocal() as session:
        user = crud.get_user(session, user_id)
        chat_id = user.telegram_chat_id if user else None
    if not chat_id:
        logger.warning("Briefing übersprungen: keine chat_id für user_id=%s", user_id)
        return

    try:
        result = run_brain(user_id, "daily_briefing")
        text = format_briefing(result)
        bot.send_message(chat_id, text)
        logger.info("Briefing an user_id=%s gesendet.", user_id)
    except Exception:  # noqa: BLE001  (bewusst breit, Job darf nicht crashen)
        logger.exception("Briefing für user_id=%s fehlgeschlagen.", user_id)


def register_daily_briefings(scheduler) -> None:
    """Registriert pro Nutzer einen Cron-Job zur Weckzeit in dessen Zeitzone."""
    hour, minute = _briefing_time()
    with SessionLocal() as session:
        users = [
            (u.id, u.timezone)
            for u in session.query(User)
            .filter(User.telegram_chat_id.isnot(None))
            .all()
        ]

    for user_id, timezone in users:
        scheduler.add_job(
            send_daily_briefing,
            CronTrigger(hour=hour, minute=minute, timezone=ZoneInfo(timezone)),
            args=[user_id],
            id=f"daily_briefing_user_{user_id}",
            name=f"Tägliches Briefing (user {user_id})",
            replace_existing=True,
        )
        logger.info(
            "Briefing-Job für user_id=%s um %02d:%02d %s registriert.",
            user_id,
            hour,
            minute,
            timezone,
        )


# --- Job-Registry --------------------------------------------------------

# Jeder Eintrag ist eine Funktion register(scheduler) -> None.
# Schritt 7+: register_budget_checks, register_weekly_reflections,
#             register_video_jobs … einfach hier ergänzen.
JOB_REGISTRARS: list[Callable[[object], None]] = [
    register_daily_briefings,
]


def build_scheduler(scheduler=None):
    """Baut den Scheduler und lässt alle Registrare ihre Jobs anmelden."""
    scheduler = scheduler or BlockingScheduler()
    for register in JOB_REGISTRARS:
        register(scheduler)
    return scheduler


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    init_db()
    scheduler = build_scheduler()
    jobs = scheduler.get_jobs()
    logger.info("Scheduler startet mit %d Job(s): %s", len(jobs), [j.id for j in jobs])
    if not jobs:
        logger.warning(
            "Keine Jobs — gibt es schon Nutzer? Erst im Bot /start ausführen."
        )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler beendet.")


if __name__ == "__main__":
    main()
