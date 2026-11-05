"""Database engine, session factory, and the declarative `Base` for all ORM models."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Consistent constraint names make Alembic migrations predictable and reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_engine(get_settings().database_url, pool_pre_ping=True)


@event.listens_for(Engine, "connect")
def _use_utc(dbapi_connection, _connection_record) -> None:
    """Make PostgreSQL return timestamps in UTC, whatever the server's local time zone is."""
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'UTC'")
    dbapi_connection.commit()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Use in route signatures: `def handler(db: DbSession): ...`
DbSession = Annotated[Session, Depends(get_db)]
