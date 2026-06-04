"""Datenbank-Anbindung (SQLAlchemy 2.0).

Stellt Engine, Session-Factory und die deklarative Basis bereit. Im MVP läuft
das gegen SQLite; durch die Konfiguration über `DATABASE_URL` ist ein späterer
Wechsel auf Postgres ohne Code-Änderung möglich.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite braucht check_same_thread=False, damit die Connection über mehrere
# (Request-)Threads hinweg genutzt werden kann. Bei Postgres ist das Argument
# weder nötig noch erlaubt -> nur für sqlite setzen.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=settings.debug,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Gemeinsame deklarative Basis für alle ORM-Modelle."""


def init_db() -> None:
    """Legt alle Tabellen an, falls sie noch nicht existieren.

    Import der Modelle hier (nicht oben), damit alle Tabellen bei der
    Modell-Registrierung bekannt sind, bevor create_all() läuft.
    """
    from app import models  # noqa: F401  (Registriert alle Tabellen)

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI-Dependency: liefert eine Session und schließt sie sauber."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
