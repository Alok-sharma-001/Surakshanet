import pytest
from sqlalchemy import select

from app.models.junction import Junction
from scripts.seed_city import seed_city, CITY_JUNCTIONS


@pytest.mark.asyncio
async def test_seed_city_is_idempotent_by_name():
    """Regression test: seed_city()'s idempotency check previously compared
    the TOTAL junction row count against len(CITY_JUNCTIONS) — vulnerable to
    any other seeding process changing that total, or to the count
    fluctuating across test/reset cycles for unrelated reasons. Found live:
    9, then 18, duplicate "Bangalore Silk Board" rows on the demo Postgres
    from exactly this. The fix matches by name, so calling seed_city() twice
    must never create a second row for the same decorative junction.

    Runs against the real database (seed_city() commits internally, so this
    can't run inside a rolled-back transaction) — this is safe precisely
    because the fix under test makes a second run a no-op rather than a
    duplication, which is what this test verifies.
    """
    from app.database import async_session_maker

    await seed_city()
    await seed_city()

    city_names = [j["name"] for j in CITY_JUNCTIONS]
    async with async_session_maker() as db:
        res = await db.execute(select(Junction).where(Junction.name.in_(city_names)))
        rows = res.scalars().all()

    counts = {}
    for row in rows:
        counts[row.name] = counts.get(row.name, 0) + 1

    duplicated = {name: n for name, n in counts.items() if n > 1}
    assert not duplicated, f"seed_city() must not duplicate junctions on a second run: {duplicated}"
    assert set(counts.keys()) == set(city_names), "seed_city() must ensure every decorative junction exists"
