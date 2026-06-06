"""Das „Gehirn" (Spec, Abschnitt 5).

Öffentliche API:
    run_brain(user_id, mode, extra=None) -> dict
    build_user_state(user_id, horizon_days=...) -> dict
    register_mode / get_mode / list_modes  (Modus-Registry)
    BrainParseError

Der Import unten lädt das modes-Paket, sodass alle Modi sich registrieren.
"""

from app.brain.client import BrainParseError, call_claude, parse_json
from app.brain.core import run_brain
from app.brain.registry import BrainMode, get_mode, list_modes, register_mode
from app.brain.state import build_user_state

# Alle Modi registrieren (self-registration beim Import).
from app.brain import modes  # noqa: F401,E402

__all__ = [
    "run_brain",
    "build_user_state",
    "BrainMode",
    "register_mode",
    "get_mode",
    "list_modes",
    "call_claude",
    "parse_json",
    "BrainParseError",
]
