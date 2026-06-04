"""Telegram-Bot-Grundgerüst (Spec, Abschnitt 9, Schritt 2).

Beweist die Zustell-Schleife: `/start` speichert die `chat_id` des Nutzers in
der Datenbank (legt bei Bedarf einen User an), alle übrigen Textnachrichten
werden als Echo zurückgespiegelt.

Der Bot-Token kommt ausschließlich aus der `.env` (TELEGRAM_BOT_TOKEN) — niemals
aus dem Code (Abschnitt 10).

Starten (Long-Polling, ideal zum Testen):

    python -m app.bot
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import User

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_or_create_user(chat_id: str, name: str) -> tuple[User, bool]:
    """Findet den User zur chat_id oder legt ihn an.

    Gibt (user, created) zurück. created=True, wenn neu angelegt.
    """
    with SessionLocal() as session:
        user = (
            session.query(User)
            .filter(User.telegram_chat_id == chat_id)
            .one_or_none()
        )
        if user is not None:
            return user, False

        user = User(
            name=name,
            timezone=settings.default_timezone,
            telegram_chat_id=chat_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user, True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — speichert die chat_id und begrüßt den Nutzer."""
    chat = update.effective_chat
    tg_user = update.effective_user
    if chat is None:
        return

    chat_id = str(chat.id)
    name = (tg_user.first_name if tg_user else None) or "Nutzer"

    user, created = _get_or_create_user(chat_id, name)

    if created:
        text = (
            f"Hallo {user.name}! 👋\n"
            "Deine Verbindung steht — ich habe dich gespeichert.\n"
            "Schick mir eine Nachricht, ich spiegele sie dir zurück (Echo-Test)."
        )
    else:
        text = (
            f"Willkommen zurück, {user.name}! "
            "Du bist bereits verbunden. Schick mir eine Nachricht für den Echo-Test."
        )

    logger.info("/start von chat_id=%s (created=%s)", chat_id, created)
    await context.bot.send_message(chat_id=chat.id, text=text)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Spiegelt jede sonstige Textnachricht zurück (Echo-Test)."""
    if update.message is None or update.message.text is None:
        return
    await update.message.reply_text(update.message.text)


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
    # Sicherstellen, dass die Tabellen existieren (User-Tabelle wird gebraucht).
    init_db()

    application = build_application()
    logger.info("Telegram-Bot startet (Long-Polling). Strg+C zum Beenden.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
