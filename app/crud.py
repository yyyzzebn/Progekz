"""Persistenz-Helfer (CRUD) auf dem Datenmodell aus Abschnitt 4.

Die Funktionen kapseln das Anlegen/Lesen der Zeilen und nehmen jeweils eine
SQLAlchemy-Session entgegen. So sind sie unabhängig vom Telegram-Layer und
können später auch vom „Gehirn" und vom Scheduler genutzt werden.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Budget, MoodLog, Task, Transaction, User


# --- Users ---------------------------------------------------------------

def get_user_by_chat_id(session: Session, chat_id: str) -> User | None:
    return (
        session.query(User)
        .filter(User.telegram_chat_id == chat_id)
        .one_or_none()
    )


def get_or_create_user(
    session: Session, chat_id: str, name: str, timezone: str
) -> tuple[User, bool]:
    """Findet den User zur chat_id oder legt ihn an. Gibt (user, created)."""
    user = get_user_by_chat_id(session, chat_id)
    if user is not None:
        return user, False

    user = User(name=name, timezone=timezone, telegram_chat_id=chat_id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, True


# --- Tasks ---------------------------------------------------------------

def create_task(
    session: Session,
    user_id: int,
    title: str,
    due_at: datetime | None = None,
    importance: int = 3,
    category: str = "personal",
    est_minutes: int | None = None,
) -> Task:
    task = Task(
        user_id=user_id,
        title=title,
        due_at=due_at,
        importance=importance,
        category=category,
        est_minutes=est_minutes,
        status="open",
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


# --- Transactions --------------------------------------------------------

def create_expense(
    session: Session,
    user_id: int,
    amount: float,
    category: str,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> Transaction:
    """Legt eine Ausgabe an. amount wird als negativer Betrag gespeichert."""
    tx = Transaction(
        user_id=user_id,
        amount=-abs(amount),
        category=category,
        note=note,
        occurred_at=occurred_at or datetime.now(),
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


# --- Mood logs -----------------------------------------------------------

def create_mood_log(
    session: Session,
    user_id: int,
    energy: int,
    mood: int,
    note: str | None = None,
) -> MoodLog:
    log = MoodLog(user_id=user_id, energy=energy, mood=mood, note=note)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


# --- Budgets -------------------------------------------------------------

def create_budget(
    session: Session,
    user_id: int,
    period: str,
    category: str,
    limit_amount: float,
) -> Budget:
    budget = Budget(
        user_id=user_id,
        period=period,
        category=category,
        limit_amount=limit_amount,
    )
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget
