"""FastAPI-Grundgerüst (Spec, Abschnitt 9, Schritt 1).

Initialisiert beim Start die Datenbank (Schema aus Abschnitt 4) und stellt
einen Health-Check-Endpoint bereit. Damit ist Schritt 1 allein lauffähig.
Spätere Schritte (Telegram-Bot, Gehirn, Scheduler) hängen sich hier an.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Beim Hochfahren: Tabellen anlegen, falls noch nicht vorhanden.
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Proaktiver Alltags-Copilot — MVP (Schritt 1: Projekt-Setup).",
    lifespan=lifespan,
)


@app.get("/")
def root() -> dict:
    return {"app": settings.app_name, "status": "ok"}


@app.get("/health")
def health() -> dict:
    """Liveness-Check: bestätigt, dass die App läuft."""
    return {"status": "healthy"}
