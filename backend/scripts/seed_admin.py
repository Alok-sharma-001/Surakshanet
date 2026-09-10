import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import get_settings
from app.database import async_session_maker, init_db
from app.services.auth_service import seed_default_admin

async def main():
    settings = get_settings()
    print("Ensuring database tables exist...")
    await init_db()
    print(f"Seeding/updating the admin account for {settings.ADMIN_EMAIL}...")
    async with async_session_maker() as session:
        await seed_default_admin(session)
    print("Admin account configured.")
    print(f"Email: {settings.ADMIN_EMAIL}")
    # The password is taken from ADMIN_PASSWORD and is never echoed: this
    # script's output is routinely pasted into issues and CI logs.
    print("Password: (from ADMIN_PASSWORD)")
    print("Role:     ADMIN")

if __name__ == '__main__':
    asyncio.run(main())
