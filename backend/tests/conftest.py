import pytest
from httpx import AsyncClient, ASGITransport
try:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.main import app
    from app.database import Base, get_db
    from app.config import get_settings
    from app.models.user import User, UserRole
    HAS_DB_BACKEND = True
except (ImportError, Exception):
    HAS_DB_BACKEND = False

if HAS_DB_BACKEND:
    settings = get_settings()

    @pytest.fixture
    async def db_session():
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            yield session
            await session.rollback()
        await engine.dispose()

    @pytest.fixture
    async def client(db_session):
        async def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()

    @pytest.fixture
    async def auth_headers(client, db_session):
        # Attempt register (in case first run)
        await client.post("/api/v1/auth/register", json={
            "email": "admin@test.com",
            "password": "testpassword123",
            "name": "Test Admin"
        })
        # Explicitly elevate user role to ADMIN in test database session
        result = await db_session.execute(select(User).where(User.email == "admin@test.com"))
        user = result.scalar_one_or_none()
        if user:
            user.role = UserRole.ADMIN
            db_session.add(user)
            await db_session.commit()

        # Login to obtain JWT
        response = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "testpassword123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}



