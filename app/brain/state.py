"""build_user_state — die zentrale, virtuelle Sicht (Spec, Abschnitt 4).

Fasst den aktuellen Stand des Nutzers aus events, tasks, transactions, budgets,
workouts und mood_logs zu einem kompakten Dict zusammen. Dieses Dict ist der
Input fürs „Gehirn" und wird als JSON in den Prompt gegeben (kein Prosa).
"""

from datetime import date, datetime, timedelta

from app import crud
from app.database import SessionLocal


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _period_start(period: str, today: date) -> datetime:
    """Beginn der laufenden Budget-Periode (Woche = Montag, Monat = 1.)."""
    if period == "week":
        start = today - timedelta(days=today.weekday())
    else:  # "month"
        start = today.replace(day=1)
    return datetime(start.year, start.month, start.day)


def build_user_state(user_id: int, horizon_days: int = 1) -> dict:
    """Kompakter Snapshot des Nutzerzustands über den gegebenen Horizont."""
    now = datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_end = day_start + timedelta(days=horizon_days, hours=23, minutes=59)
    today = now.date()

    with SessionLocal() as session:
        user = crud.get_user(session, user_id)
        if user is None:
            raise ValueError(f"Kein User mit id={user_id}.")

        events = crud.get_events_between(session, user_id, day_start, horizon_end)
        tasks = crud.get_open_tasks(session, user_id)
        budgets = crud.get_budgets(session, user_id)
        workouts = crud.get_planned_workouts_between(
            session, user_id, now, horizon_end
        )
        last_mood = crud.get_latest_mood(session, user_id)

        budget_state = []
        for b in budgets:
            spent = crud.spending_by_category_since(
                session, user_id, b.category, _period_start(b.period, today)
            )
            available = b.limit_amount - spent
            used_pct = round(spent / b.limit_amount * 100) if b.limit_amount else 0
            budget_state.append(
                {
                    "category": b.category,
                    "period": b.period,
                    "limit": round(b.limit_amount, 2),
                    "spent": round(spent, 2),
                    "available": round(available, 2),
                    "used_pct": used_pct,
                }
            )

        # Ausgaben der letzten 7 Tage als grober Kontext.
        recent_tx = crud.get_transactions_since(
            session, user_id, now - timedelta(days=7)
        )
        recent_spending = round(
            sum(abs(t.amount) for t in recent_tx if t.amount < 0), 2
        )

        return {
            "now": _fmt(now),
            "timezone": user.timezone,
            "horizon_days": horizon_days,
            "events": [
                {"title": e.title, "start": _fmt(e.start_at), "end": _fmt(e.end_at)}
                for e in events
            ],
            "open_tasks": [
                {
                    "title": t.title,
                    "due": _fmt(t.due_at),
                    "importance": t.importance,
                    "est_minutes": t.est_minutes,
                    "category": t.category,
                }
                for t in tasks
            ],
            "budgets": budget_state,
            "recent_spending_7d": recent_spending,
            "planned_workouts": [
                {
                    "type": w.type,
                    "planned_at": _fmt(w.planned_at),
                    "intensity": w.intensity,
                }
                for w in workouts
            ],
            "last_mood": (
                {
                    "energy": last_mood.energy,
                    "mood": last_mood.mood,
                    "logged_at": _fmt(last_mood.logged_at),
                    "note": last_mood.note,
                }
                if last_mood
                else None
            ),
        }
