"""Modus-Definitionen. Jeder Import hier registriert seinen Modus selbst.

Neuen Modus hinzufügen = neue Datei in diesem Ordner + eine Zeile hier. Kein
bestehender Code muss geändert werden (Spec: „nur Hinzufügen statt Umbauen").
"""

from app.brain.modes import daily_briefing  # noqa: F401  (self-registriert)

# Künftig z.B.:
# from app.brain.modes import purchase_decision   # noqa: F401
# from app.brain.modes import weekly_reflection    # noqa: F401
# from app.brain.modes import video_script          # noqa: F401
