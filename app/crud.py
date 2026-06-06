"""Persistenz-Helfer (CRUD) auf dem Datenmodell aus Abschnitt 4.

Die Funktionen kapseln das Anlegen/Lesen der Zeilen und nehmen jeweils eine
SQLAlchemy-Session entgegen. So sind sie unabhängig vom Telegram-Layer und
können später auch vom „Gehirn" und vom Scheduler genutzt werden.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Budget, Event, MoodLog, Task, Transaction, User, Workout


# --- Users ---------------------------------------------------------------

def get_user_by_chat_id(session: Session, chat_id: str) -> User | None:
    return (
        session.query(User)
        .filter(User.telegram_chat_id == chat_id)
        .one_or_none()
    )


def get_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


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


# --- Events (Kalender) ---------------------------------------------------

def upsert_gcal_event(
    session: Session,
    user_id: int,
    external_id: str,
    title: str,
    start_at: datetime,
    end_at: datetime,
) -> bool:
    """Legt ein Kalender-Event an oder aktualisiert es (idempotent).

    Identifiziert bestehende Events über (user_id, source='gcal', external_id),
    sodass ein erneuter Sync keine Duplikate erzeugt. Committet NICHT selbst —
    der Aufrufer committet den Batch. Gibt True zurück, wenn neu angelegt.
    """
    event = (
        session.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.source == "gcal",
            Event.external_id == external_id,
        )
        .one_or_none()
    )
    if event is not None:
        event.title = title
        event.start_at = start_at
        event.end_at = end_at
        return False

    session.add(
        Event(
            user_id=user_id,
            title=title,
            start_at=start_at,
            end_at=end_at,
            source="gcal",
            external_id=external_id,
        )
    )
    return True


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


# --- Lesezugriffe für build_user_state -----------------------------------

def get_events_between(
    session: Session, user_id: int, start: datetime, end: datetime
) -> list[Event]:
    return (
        session.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.start_at >= start,
            Event.start_at <= end,
        )
        .order_by(Event.start_at)
        .all()
    )


def get_open_tasks(session: Session, user_id: int) -> list[Task]:
    """Offene Aufgaben, früheste Deadline zuerst (Tasks ohne Deadline ans Ende)."""
    return (
        session.query(Task)
        .filter(Task.user_id == user_id, Task.status == "open")
        .order_by(Task.due_at.is_(None), Task.due_at, Task.importance.desc())
        .all()
    )


def get_transactions_since(
    session: Session, user_id: int, since: datetime
) -> list[Transaction]:
    return (
        session.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.occurred_at >= since)
        .order_by(Transaction.occurred_at.desc())
        .all()
    )


def get_budgets(session: Session, user_id: int) -> list[Budget]:
    return session.query(Budget).filter(Budget.user_id == user_id).all()


def get_planned_workouts_between(
    session: Session, user_id: int, start: datetime, end: datetime
) -> list[Workout]:
    return (
        session.query(Workout)
        .filter(
            Workout.user_id == user_id,
            Workout.done.is_(False),
            Workout.planned_at >= start,
            Workout.planned_at <= end,
        )
        .order_by(Workout.planned_at)
        .all()
    )


def get_latest_mood(session: Session, user_id: int) -> MoodLog | None:
    return (
        session.query(MoodLog)
        .filter(MoodLog.user_id == user_id)
        .order_by(MoodLog.logged_at.desc())
        .first()
    )


def spending_by_category_since(
    session: Session, user_id: int, category: str, since: datetime
) -> float:
    """Summe der Ausgaben (positiver Betrag) einer Kategorie seit `since`."""
    total = 0.0
    rows = (
        session.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.category == category,
            Transaction.amount < 0,
            Transaction.occurred_at >= since,
        )
        .all()
    )
    for tx in rows:
        total += abs(tx.amount)
    return total
