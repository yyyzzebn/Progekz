"""Modus `daily_briefing` (Spec, Abschnitt 5 & 6.2).

Nüchterner Prioritäten-Coach: aus dem Tageszustand ein kurzes Briefing mit
Top-Prioritäten, Budget-Warnungen und Überlast-Erkennung. Antwort strikt als
JSON nach OUTPUT_SCHEMA.
"""

import json

from app.brain.registry import BrainMode, register_mode

SYSTEM_PROMPT = (
    "Du bist ein nüchterner, ehrlicher Prioritäten-Coach. Du hilfst dem Nutzer, "
    "den Tag zu strukturieren: Du erkennst freie Zeitfenster zwischen Terminen, "
    "ordnest offene Aufgaben nach Wichtigkeit und Deadline-Nähe zu, warnst bei "
    "knappen Budgets und erkennst Überlast.\n\n"
    "Antworte AUSSCHLIESSLICH mit einem einzigen JSON-Objekt nach dem vorgegebenen "
    "Schema. Kein Markdown, keine Code-Fences/Backticks, kein Vorwort, kein "
    "Nachwort. Schreibe auf Deutsch und bleib konkret und knapp."
)

OUTPUT_SCHEMA = {
    "briefing_text": "Kurzer, freundlicher Fließtext für Telegram (3-5 Sätze).",
    "top_priorities": [
        {
            "task": "Aufgabentitel",
            "why": "knappe Begründung",
            "suggested_slot": "z.B. 14:00-15:30",
        }
    ],
    "warnings": ["z.B. Budget Essen diese Woche zu 85% ausgeschöpft"],
    "overload_flag": False,
    "drop_suggestions": ["Aufgaben, die man bei Überlast streichen kann"],
}


def build_user_prompt(state: dict, extra: dict) -> str:
    return (
        "Aktueller Stand des Nutzers (kompaktes JSON):\n"
        f"{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
        "Erstelle daraus das heutige Briefing. Wähle 1-3 Top-Prioritäten und "
        "schlage realistische Zeitfenster vor, die nicht mit Terminen kollidieren. "
        "Setze overload_flag auf true und fülle drop_suggestions, wenn deutlich "
        "mehr ansteht als in den freien Slot passt.\n\n"
        "Antworte ausschließlich mit JSON nach genau diesem Schema:\n"
        f"{json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2)}"
    )


register_mode(
    BrainMode(
        name="daily_briefing",
        system_prompt=SYSTEM_PROMPT,
        horizon_days=1,
        build_user_prompt=build_user_prompt,
        output_schema=OUTPUT_SCHEMA,
    )
)
