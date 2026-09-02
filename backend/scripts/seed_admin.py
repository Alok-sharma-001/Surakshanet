import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import async_session_maker, init_db
from app.services.auth_service import seed_default_admin

async def main():
    print("Ensuring database tables exist...")
    await init_db()
    print("Seeding/updating admin credentials for aloks92440@gmail.com...")
    async with async_session_maker() as session:
        await seed_default_admin(session)
    print("✅ Admin account successfully configured!")
    print("Email:    aloks92440@gmail.com")
    print("Password: Alok@2005")
    print("Role:     ADMIN")

if __name__ == '__main__':
    asyncio.run(main())
