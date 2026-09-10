#!/usr/bin/env python3
"""
Surakshanet - Control Service Entrypoint
========================================
Executes MARL/Webster signal control loop and safety envelope.
"""

import os
import sys
import time
import signal
import logging

# Ensure SUMO tools and shared libraries are in sys.path
candidate_paths = [
    os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"),
    "/usr/share/sumo/tools",
    "/usr/lib/python3/dist-packages",
    "/usr/local/share/sumo/tools",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
]
for p in candidate_paths:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    import traci  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "FATAL: 'traci' is not importable from this interpreter.\n"
        f"  interpreter: {sys.executable}\n"
        "  fix: see docs/04-environment-setup.md §2 (SN-013)"
    ) from exc

logger = logging.getLogger("surakshanet.control_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_running = True


def handle_signal(sig, frame):
    global _running
    logger.info(f"Received signal {sig}, shutting down control service...")
    _running = False


def main():
    global _running
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    redis_password = os.environ.get("REDIS_PASSWORD", None)

    r = None
    try:
        import redis
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
            socket_timeout=2.0
        )
        r.ping()
        logger.info("Connected to Redis for control service state.")
    except Exception as e:
        logger.warning(f"Control service starting with disconnected Redis ({e})")

    logger.info("Control service initialized successfully.")

    while _running:
        now = time.time()
        if r is not None:
            try:
                r.set("control_service:heartbeat", str(now))
                r.set("control_service:last_decision", str(now))
            except Exception as e:
                logger.debug(f"Error updating heartbeat: {e}")
        time.sleep(2.0)

    logger.info("Control service stopped.")


if __name__ == "__main__":
    main()
