from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def configure_sqlite_connection(dbapi_connection: object, _connection_record: object) -> None:
    """Tune SQLite for a small multi-user, single-process deployment."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute(f"PRAGMA busy_timeout={max(1000, settings.sqlite_busy_timeout_ms)}")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


if settings.database_url.startswith("sqlite"):
    event.listen(engine, "connect", configure_sqlite_connection)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
