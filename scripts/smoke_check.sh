#!/usr/bin/env bash
# Surakshanet Deployment Smoke Checks
# Validates /api/v1/health, /metrics, and WebSocket connectivity.

set -eo pipefail

BASE_URL="${1:-${BACKEND_URL:-http://localhost:8000}}"
TIMEOUT=5

echo "Starting smoke check on $BASE_URL with timeout ${TIMEOUT}s..."

# 1. Health check
echo -n "Checking /api/v1/health... "
HEALTH_RESP=$(curl -s --max-time "$TIMEOUT" "$BASE_URL/api/v1/health" || true)
if [ -z "$HEALTH_RESP" ]; then
    echo "FAILED (No response or connection refused)"
    exit 1
fi

STATUS=$(echo "$HEALTH_RESP" | grep -o '"status"[^,]*' | cut -d'"' -f4 | tr '[:upper:]' '[:lower:]' || true)
if [ "$STATUS" != "healthy" ]; then
    echo "FAILED (Status: $STATUS)"
    exit 1
fi
echo "OK ($STATUS)"

# 2. Metrics check
echo -n "Checking /metrics... "
METRICS_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$BASE_URL/metrics" || true)
if [ "$METRICS_HTTP_CODE" != "200" ]; then
    echo "FAILED (HTTP $METRICS_HTTP_CODE)"
    exit 1
fi
echo "OK (HTTP 200)"

# 3. WebSocket connectivity check
echo -n "Checking WebSocket connectivity... "
WS_URL=$(echo "$BASE_URL" | sed 's|^http|ws|')/ws/smoke_test
WS_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" \
    -H "Upgrade: websocket" \
    -H "Connection: Upgrade" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
    -H "Sec-WebSocket-Version: 13" \
    "$BASE_URL/ws/smoke_test" || true)

if [ "$WS_HTTP_CODE" = "000" ]; then
    echo "FAILED (Connection failed to $WS_URL)"
    exit 1
fi
echo "OK (HTTP response: $WS_HTTP_CODE)"

echo "All smoke checks PASSED successfully."
exit 0
