from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import engine

log = get_logger("db")


async def init_db() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Database initialized")
    except SQLAlchemyError:
        log.exception("Database initialization failed")
