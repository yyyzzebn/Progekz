"""Prioritäten-Engine (Spec, Abschnitt 6.1).

Eigenständige, netz-/LLM-freie Logik: erkennt aus den Kalender-Terminen die
freien Zeitfenster des Tages und bereitet die offenen Tasks samt Deadline-Nähe
als Fakten auf. Diese Fakten werden dem „Gehirn" mitgegeben — das Modell
übernimmt nur noch Priorisierung & Begründung.
"""

from datetime import datetime, timedelta

_FMT = "%Y-%m-%d %H:%M"


def _parse(value: str) -> datetime:
    return datetime.strptime(value, _FMT)


def free_slots(
    busy: list[tuple[datetime, datetime]],
    window_start: datetime,
    window_end: datetime,
    min_minutes: int = 30,
) -> list[tuple[datetime, datetime]]:
    """Freie Lücken im Fenster [window_start, window_end] zwischen `busy`-Blöcken.

    Termine werden aufs Fenster zugeschnitten, überlappende zusammengefasst;
    Lücken kürzer als `min_minutes` werden verworfen. Reine Funktion.
    """
    if window_end <= window_start:
        return []

    # Auf das Fenster zuschneiden.
    clipped: list[tuple[datetime, datetime]] = []
    for start, end in busy:
        s = max(start, window_start)
        e = min(end, window_end)
        if e > s:
            clipped.append((s, e))
    clipped.sort()

    # Überlappende/anstoßende Termine zusammenfassen.
    merged: list[list[datetime]] = []
    for s, e in clipped:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    # Lücken einsammeln.
    min_gap = timedelta(minutes=min_minutes)
    slots: list[tuple[datetime, datetime]] = []
    cursor = window_start
    for s, e in merged:
        if s - cursor >= min_gap:
            slots.append((cursor, s))
        cursor = max(cursor, e)
    if window_end - cursor >= min_gap:
        slots.append((cursor, window_end))
    return slots


def compute_priority_facts(
    state: dict,
    *,
    day_end_hour: int = 22,
    min_slot_minutes: int = 30,
) -> dict:
    """Bereitet freie Slots und Deadline-Fakten aus einem user_state auf.

    Erwartet `state` aus build_user_state (mit "now", "events", "open_tasks").
    Liefert ein kompaktes Dict, das in den Briefing-Prompt gegeben wird.
    """
    now = _parse(state["now"])
    window_end = now.replace(
        hour=day_end_hour, minute=0, second=0, microsecond=0
    )

    busy = [
        (_parse(e["start"]), _parse(e["end"]))
        for e in state.get("events", [])
        if e.get("start") and e.get("end")
    ]
    slots = free_slots(busy, now, window_end, min_slot_minutes)

    free = [
        {
            "start": s.strftime(_FMT),
            "end": e.strftime(_FMT),
            "minutes": int((e - s).total_seconds() // 60),
        }
        for s, e in slots
    ]

    # Offene Tasks mit Deadline nach Dringlichkeit (Tage bis Fälligkeit).
    deadlines = []
    for t in state.get("open_tasks", []):
        due = t.get("due")
        days_until = (_parse(due).date() - now.date()).days if due else None
        deadlines.append(
            {
                "task": t.get("title"),
                "due": due,
                "days_until_due": days_until,
                "importance": t.get("importance"),
                "est_minutes": t.get("est_minutes"),
            }
        )
    # Dringendste zuerst (ohne Deadline ans Ende), dann nach Wichtigkeit.
    deadlines.sort(
        key=lambda d: (
            d["days_until_due"] if d["days_until_due"] is not None else 10**6,
            -(d["importance"] or 0),
        )
    )

    return {
        "free_slots": free,
        "free_minutes_total": sum(f["minutes"] for f in free),
        "open_deadlines": deadlines,
    }
