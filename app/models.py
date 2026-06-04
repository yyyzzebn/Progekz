"""ORM-Modelle — der gemeinsame Datenunterbau (Spec, Abschnitt 4).

Alle Module teilen sich diese Tabellen. Jedes spätere Modul (Briefing,
Finanz-Coach, Reflexion) ist nur ein Aufsatz auf diese Daten.
"""

from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Europe/Berlin"
    )
    # Telegram-chat_id dient als Identitätsnachweis (Abschnitt 10).
    telegram_chat_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    events: Mapped[list["Event"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["Budget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    workouts: Mapped[list["Workout"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    mood_logs: Mapped[list["MoodLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reflections: Mapped[list["Reflection"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Event(Base):
    """Aus dem Kalender synchronisierte Termine."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("source IN ('gcal','manual')", name="ck_events_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    # external_id: ID beim Quell-System (z.B. Google Calendar) für Idempotenz.
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)

    user: Mapped["User"] = relationship(back_populates="events")


class Task(Base):
    """Aufgaben, Deadlines, Klausuren/Noten-Termine."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "importance BETWEEN 1 AND 5", name="ck_tasks_importance"
        ),
        CheckConstraint(
            "category IN ('study','work','personal','admin')",
            name="ck_tasks_category",
        ),
        CheckConstraint("status IN ('open','done')", name="ck_tasks_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    est_minutes: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(
        String(16), nullable=False, default="personal"
    )
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="tasks")


class Transaction(Base):
    """Finanzbewegungen (MVP: manuell). amount negativ = Ausgabe."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="transactions")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint(
            "period IN ('week','month')", name="ck_budgets_period"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_amount: Mapped[float] = mapped_column(Float, nullable=False)

    user: Mapped["User"] = relationship(back_populates="budgets")


class Workout(Base):
    __tablename__ = "workouts"
    __table_args__ = (
        CheckConstraint(
            "intensity BETWEEN 1 AND 5", name="ck_workouts_intensity"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    intensity: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="workouts")


class MoodLog(Base):
    """1 Tap pro Tag: Energie & Stimmung."""

    __tablename__ = "mood_logs"
    __table_args__ = (
        CheckConstraint("energy BETWEEN 1 AND 5", name="ck_mood_energy"),
        CheckConstraint("mood BETWEEN 1 AND 5", name="ck_mood_mood"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    energy: Mapped[int] = mapped_column(Integer, nullable=False)
    mood: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="mood_logs")


class Reflection(Base):
    """Wochenreflexionen."""

    __tablename__ = "reflections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    q_well: Mapped[str | None] = mapped_column(Text)
    q_drained: Mapped[str | None] = mapped_column(Text)
    q_offplan: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="reflections")


class Decision(Base):
    """Optional: Entscheidungs-Tagebuch (Phase 2+)."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    actual_outcome: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="decisions")
