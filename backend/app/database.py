import os
import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine_kwargs = {"echo": settings.DEBUG}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def _load_spatialite(dbapi_conn, connection_record):
        try:
            raw = getattr(dbapi_conn, "_connection", None)
            if raw and hasattr(raw, "_conn"):
                raw._conn.enable_load_extension(True)
                for lib in ["/usr/lib/mod_spatialite.so", "/usr/local/lib/mod_spatialite.so", "mod_spatialite"]:
                    if os.path.exists(lib) or "/" not in lib:
                        try:
                            raw._conn.load_extension(lib)
                            break
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"SpatiaLite extension load note: {e}")

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
async_session_factory = async_session_maker

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an asynchronous database session."""
    async with async_session_maker() as session:
        yield session


import asyncio
import logging
import os
from alembic.config import Config
from alembic import command

logger = logging.getLogger(__name__)


def run_alembic_migrations() -> None:
    """Execute Alembic migrations up to head synchronously."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
    if os.path.exists(alembic_ini_path):
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        logger.info("Executing Alembic migrations up to head...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations completed successfully.")
    else:
        logger.warning(f"alembic.ini not found at {alembic_ini_path}")


_MIGRATION_LOCK_KEY = 875_501_001  # arbitrary, unique to this app


async def _run_migrations_once() -> None:
    """Guard alembic upgrade head with a Postgres advisory lock so multiple
    uvicorn workers booting concurrently don't race on the same migration —
    that race was previously masked by swallowing every exception here."""
    async with engine.connect() as conn:
        got_lock = (await conn.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _MIGRATION_LOCK_KEY}
        )).scalar()
        if not got_lock:
            logger.info("Another worker is running migrations; skipping.")
            return
        try:
            await asyncio.to_thread(run_alembic_migrations)
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATION_LOCK_KEY}
            )


async def init_db() -> None:
    """Initialize the database by executing Alembic migrations and seeding default admin."""
    if "sqlite" in settings.DATABASE_URL:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        await _run_migrations_once()

    # Seed default admin user
    try:
        from app.services.auth_service import seed_default_admin
        async with async_session_maker() as session:
            await seed_default_admin(session)
    except Exception as e:
        logger.warning(f"Admin seeding note: {e}")
