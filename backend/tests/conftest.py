import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base, get_db
from app.config import get_settings

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
async def auth_headers(client):
    # Attempt register (in case first run)
    await client.post("/api/v1/auth/register", json={
        "email": "admin@test.com",
        "password": "testpassword123",
        "name": "Test Admin"
    })
    # Login to obtain JWT
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "testpassword123"
    })
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

