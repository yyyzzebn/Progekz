"""Modus-Registry des „Gehirns" (Spec, Abschnitt 5).

Jeder Modus ist ein `BrainMode`: eigener System-Prompt, eigener Zeithorizont,
eigenes erwartetes JSON-Schema und eine Funktion, die aus `user_state` (+ extra)
den User-Prompt baut. Neue Modi werden über `register_mode` hinzugefügt —
bestehender Code muss dafür nicht angefasst werden.
"""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BrainMode:
    name: str
    # Rolle/Anweisung; betont „nur JSON" (siehe build_system_prompt).
    system_prompt: str
    # Zeithorizont in Tagen für build_user_state.
    horizon_days: int
    # (state: dict, extra: dict) -> str  ->  fertiger User-Prompt.
    build_user_prompt: Callable[[dict, dict], str]
    # Menschlich lesbares Ziel-Schema (wird auch in den Prompt injiziert).
    output_schema: dict = field(default_factory=dict)


_REGISTRY: dict[str, BrainMode] = {}


def register_mode(mode: BrainMode) -> None:
    """Registriert einen Modus. Doppelte Namen sind ein Programmierfehler."""
    if mode.name in _REGISTRY:
        raise ValueError(f"Brain-Modus '{mode.name}' ist bereits registriert.")
    _REGISTRY[mode.name] = mode


def get_mode(name: str) -> BrainMode:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(keine)"
        raise KeyError(
            f"Unbekannter Brain-Modus '{name}'. Registriert: {known}."
        ) from None


def list_modes() -> list[str]:
    return sorted(_REGISTRY)
