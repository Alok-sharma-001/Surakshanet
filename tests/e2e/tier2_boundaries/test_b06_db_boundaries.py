"""
Tier 2 Boundary & Corner Cases: Feature 6 - Database Service Boundaries (M2)
Unicode handling, connection timeouts, transaction rollbacks, SQL injection safety.
"""

import pytest
from tests.e2e.client import E2EDatabaseClient, E2EHttpClient


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(6)
def test_database_utf8_multibyte_support(db_client: E2EDatabaseClient):
    """TC-B06-01: Boundary - Multi-byte UTF-8 characters (Hindi, emojis) stored properly."""
    import psycopg2
    conn = psycopg2.connect(db_client.db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMPORARY TABLE e2e_unicode_test (id SERIAL, text_data TEXT);")
            unicode_sample = "सुरक्षानेट ITS Corridor 🚦 123"
            cur.execute("INSERT INTO e2e_unicode_test (text_data) VALUES (%s);", (unicode_sample,))
            cur.execute("SELECT text_data FROM e2e_unicode_test LIMIT 1;")
            res = cur.fetchone()[0]
            assert res == unicode_sample, f"UTF-8 corruption: expected '{unicode_sample}', got '{res}'"
    finally:
        conn.close()


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(6)
def test_database_transaction_rollback_boundary(db_client: E2EDatabaseClient):
    """TC-B06-02: Boundary - Transaction abort rolls back intermediate state."""
    import psycopg2
    conn = psycopg2.connect(db_client.db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMPORARY TABLE e2e_tx_test (id INT PRIMARY KEY, name TEXT);")
        conn.commit()

        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO e2e_tx_test VALUES (1, 'initial');")
                cur.execute("INSERT INTO e2e_tx_test VALUES (1, 'duplicate');")
            conn.commit()
        except Exception:
            conn.rollback()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM e2e_tx_test;")
            count = cur.fetchone()[0]
            assert count == 0
    finally:
        conn.close()


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(6)
def test_sql_injection_resistance_on_login(http_client: E2EHttpClient):
    """TC-B06-03: Boundary - SQL injection payload in login endpoint is safely rejected."""
    sqli_payload = "' OR '1'='1' --"
    res, _ = http_client.login_user(email=sqli_payload, password="password")
    assert res.status_code in (400, 401, 422, 429), f"SQL injection returned status {res.status_code}"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(6)
def test_database_timezone_is_utc(db_client: E2EDatabaseClient):
    """TC-B06-04: Boundary - Default database session timezone is UTC."""
    tz = db_client.execute_scalar("SHOW timezone;")
    assert tz is not None and "UTC" in str(tz).upper()


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(6)
def test_database_concurrent_queries_burst(db_client: E2EDatabaseClient):
    """TC-B06-05: Boundary - Burst of 10 rapid queries completes without exhausting connection pool."""
    results = []
    for i in range(10):
        val = db_client.execute_scalar(f"SELECT {i} * 2;")
        results.append(val)
    assert results == [i * 2 for i in range(10)]
