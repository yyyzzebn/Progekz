"""run_brain — die eine Funktion, die alle Modi bedient (Spec, Abschnitt 5).

    state = build_user_state(user_id, horizon=mode.horizon_days)
    prompt = mode.build_user_prompt(state, extra)
    raw = call_claude(system=mode.system_prompt, user=prompt)
    return parse_json(raw)

Der `mode`-Parameter ist frei erweiterbar: jeder über register_mode angemeldete
Modus funktioniert hier, ohne dass run_brain angefasst werden muss.
"""

import logging

from app.brain.client import call_claude, parse_json
from app.brain.registry import get_mode
from app.brain.state import build_user_state

logger = logging.getLogger(__name__)


def run_brain(user_id: int, mode: str, extra: dict | None = None) -> dict:
    """Sammelt den Nutzerzustand, fragt das Modell und liefert strukturiertes JSON.

    `extra` trägt modus-spezifische Zusatzinfos (z.B. Kaufbetrag bei späteren
    Modi); für daily_briefing wird es nicht gebraucht.
    """
    extra = extra or {}
    brain_mode = get_mode(mode)

    state = build_user_state(user_id, horizon_days=brain_mode.horizon_days)
    user_prompt = brain_mode.build_user_prompt(state, extra)

    logger.info("run_brain mode=%s user_id=%s", mode, user_id)
    raw = call_claude(system=brain_mode.system_prompt, user=user_prompt)
    return parse_json(raw)
