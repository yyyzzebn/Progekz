"""Telegram-Bot (Spec, Abschnitt 9, Schritte 2–3).

Schritt 2 (Zustell-Schleife): `/start` speichert die `chat_id` des Nutzers,
übrige Textnachrichten werden als Echo zurückgespiegelt.

Schritt 3 (Eingabe-Befehle): manuelle Dateneingabe in die Tabellen aus
Abschnitt 4:
  /task <titel> <YYYY-MM-DD>           -> tasks
  /ausgabe <betrag> <kategorie>        -> transactions (als Ausgabe, negativ)
  /mood <energie 1-5> <stimmung 1-5>   -> mood_logs
  /budget <week|month> <kat> <betrag>  -> budgets

Der Bot-Token kommt ausschließlich aus der `.env` (TELEGRAM_BOT_TOKEN) — niemals
aus dem Code (Abschnitt 10).

Starten (Long-Polling, ideal zum Testen):

    python -m app.bot
"""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app import crud
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import User

logger = logging.getLogger(__name__)
settings = get_settings()


# --- Parsing-Helfer ------------------------------------------------------

def _parse_amount(raw: str) -> float:
    """Wandelt z.B. '12,50' oder '12.50' in float um. Wirft ValueError."""
    return float(raw.replace(",", "."))


def _parse_rating(raw: str) -> int:
    """Parst eine 1–5-Bewertung. Wirft ValueError außerhalb des Bereichs."""
    value = int(raw)
    if not 1 <= value <= 5:
        raise ValueError("Wert muss zwischen 1 und 5 liegen.")
    return value


async def _require_user(update: Update) -> User | None:
    """Liefert den User zur chat_id oder antwortet mit Hinweis auf /start."""
    chat = update.effective_chat
    if chat is None:
        return None
    with SessionLocal() as session:
        user = crud.get_user_by_chat_id(session, str(chat.id))
    if user is None and update.message is not None:
        await update.message.reply_text(
            "Ich kenne dich noch nicht — schick mir bitte zuerst /start."
        )
    return user


# --- Handler: Schritt 2 --------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — speichert die chat_id und begrüßt den Nutzer."""
    chat = update.effective_chat
    tg_user = update.effective_user
    if chat is None:
        return

    chat_id = str(chat.id)
    name = (tg_user.first_name if tg_user else None) or "Nutzer"

    with SessionLocal() as session:
        user, created = crud.get_or_create_user(
            session, chat_id, name, settings.default_timezone
        )
        user_name = user.name

    if created:
        text = (
            f"Hallo {user_name}! 👋\n"
            "Deine Verbindung steht — ich habe dich gespeichert.\n\n"
            + _help_text()
        )
    else:
        text = (
            f"Willkommen zurück, {user_name}!\n\n" + _help_text()
        )

    logger.info("/start von chat_id=%s (created=%s)", chat_id, created)
    await context.bot.send_message(chat_id=chat.id, text=text)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Spiegelt jede sonstige Textnachricht zurück (Echo-Test)."""
    if update.message is None or update.message.text is None:
        return
    await update.message.reply_text(update.message.text)


# --- Handler: Schritt 3 (Eingabe-Befehle) --------------------------------

def _help_text() -> str:
    return (
        "Eingabe-Befehle:\n"
        "• /task <titel> <YYYY-MM-DD> — Aufgabe mit Deadline\n"
        "• /ausgabe <betrag> <kategorie> — Ausgabe buchen\n"
        "• /mood <energie 1-5> <stimmung 1-5> — Tages-Check-in\n"
        "• /budget <week|month> <kategorie> <betrag> — Budget anlegen"
    )


async def task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/task <titel> <YYYY-MM-DD> — legt eine Aufgabe an."""
    user = await _require_user(update)
    if user is None:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Nutzung: /task <titel> <YYYY-MM-DD>\nz.B. /task Klausur lernen 2026-06-20"
        )
        return

    *title_parts, date_str = args
    title = " ".join(title_parts).strip()
    if not title:
        await update.message.reply_text("Bitte gib einen Titel an.")
        return

    try:
        due_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(
            f"'{date_str}' ist kein gültiges Datum. Erwartet: YYYY-MM-DD."
        )
        return

    # Deadline = Ende des angegebenen Tages.
    due_at = due_date.replace(hour=23, minute=59)
    with SessionLocal() as session:
        created = crud.create_task(
            session, user_id=user.id, title=title, due_at=due_at
        )
        task_id = created.id

    await update.message.reply_text(
        f'✅ Aufgabe #{task_id} gespeichert: „{title}" '
        f'(fällig {due_date.strftime("%d.%m.%Y")}).'
    )


async def ausgabe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ausgabe <betrag> <kategorie> — bucht eine Ausgabe."""
    user = await _require_user(update)
    if user is None:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Nutzung: /ausgabe <betrag> <kategorie>\nz.B. /ausgabe 12.50 Essen"
        )
        return

    try:
        amount = _parse_amount(args[0])
    except ValueError:
        await update.message.reply_text(
            f"'{args[0]}' ist kein gültiger Betrag. z.B. 12.50"
        )
        return
    if amount <= 0:
        await update.message.reply_text("Der Betrag muss größer als 0 sein.")
        return

    category = " ".join(args[1:]).strip()
    with SessionLocal() as session:
        tx = crud.create_expense(
            session, user_id=user.id, amount=amount, category=category
        )
        tx_id = tx.id

    await update.message.reply_text(
        f"💸 Ausgabe #{tx_id} gebucht: {amount:.2f} € für {category}."
    )


async def mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/mood <energie 1-5> <stimmung 1-5> — Tages-Check-in."""
    user = await _require_user(update)
    if user is None:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Nutzung: /mood <energie 1-5> <stimmung 1-5>\nz.B. /mood 4 3"
        )
        return

    try:
        energy = _parse_rating(args[0])
        mood_value = _parse_rating(args[1])
    except ValueError:
        await update.message.reply_text(
            "Energie und Stimmung müssen ganze Zahlen von 1 bis 5 sein."
        )
        return

    note = " ".join(args[2:]).strip() or None
    with SessionLocal() as session:
        log = crud.create_mood_log(
            session,
            user_id=user.id,
            energy=energy,
            mood=mood_value,
            note=note,
        )
        log_id = log.id

    await update.message.reply_text(
        f"🧭 Check-in #{log_id} gespeichert: Energie {energy}/5, Stimmung "
        f"{mood_value}/5."
    )


async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/budget <week|month> <kategorie> <betrag> — legt ein Budget an."""
    user = await _require_user(update)
    if user is None:
        return

    args = context.args or []
    if len(args) < 3:
        await update.message.reply_text(
            "Nutzung: /budget <week|month> <kategorie> <betrag>\n"
            "z.B. /budget week Essen 80"
        )
        return

    period = args[0].lower()
    if period not in ("week", "month"):
        await update.message.reply_text(
            "Zeitraum muss 'week' oder 'month' sein."
        )
        return

    try:
        limit_amount = _parse_amount(args[-1])
    except ValueError:
        await update.message.reply_text(
            f"'{args[-1]}' ist kein gültiger Betrag. z.B. 80"
        )
        return
    if limit_amount <= 0:
        await update.message.reply_text("Das Limit muss größer als 0 sein.")
        return

    category = " ".join(args[1:-1]).strip()
    period_label = "Woche" if period == "week" else "Monat"
    with SessionLocal() as session:
        b = crud.create_budget(
            session,
            user_id=user.id,
            period=period,
            category=category,
            limit_amount=limit_amount,
        )
        budget_id = b.id

    await update.message.reply_text(
        f"📊 Budget #{budget_id} gesetzt: {limit_amount:.2f} € pro "
        f"{period_label} für {category}."
    )


# --- Application ----------------------------------------------------------

def build_application() -> Application:
    """Baut die Telegram-Application und registriert die Handler."""
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN fehlt. Bitte in der .env setzen "
            "(siehe .env.example)."
        )

    application = (
        ApplicationBuilder().token(settings.telegram_bot_token).build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("task", task))
    application.add_handler(CommandHandler("ausgabe", ausgabe))
    application.add_handler(CommandHandler("mood", mood))
    application.add_handler(CommandHandler("budget", budget))
    # Alle Text-Nachrichten außer Commands -> Echo.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, echo)
    )
    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    # Sicherstellen, dass die Tabellen existieren.
    init_db()

    application = build_application()
    logger.info("Telegram-Bot startet (Long-Polling). Strg+C zum Beenden.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
