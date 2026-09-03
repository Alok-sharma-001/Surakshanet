from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an asynchronous database session."""
    async with async_session_maker() as session:
        yield session

async def init_db() -> None:
    """Initialize the database by creating all tables and seeding default admin."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Table/type initialization note: {e}")
    
    # Seed default admin user
    try:
        from app.services.auth_service import seed_default_admin
        async with async_session_maker() as session:
            await seed_default_admin(session)
    except Exception as e:
        print(f"Admin seeding note: {e}")
