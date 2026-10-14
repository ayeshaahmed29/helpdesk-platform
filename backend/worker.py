"""SLA worker: runs run_sla_check every SLA_CHECK_INTERVAL_SECONDS.

Started by the `worker` service in docker-compose.yml.
"""

import logging
import os
import signal
import threading
import uuid
from datetime import UTC, datetime

import redis

from core.sla import run_sla_check
from database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sla_worker")

INTERVAL_SECONDS = max(int(os.getenv("SLA_CHECK_INTERVAL_SECONDS", "300")), 10)
LOCK_KEY = "lock:sla_check"
LOCK_TTL_SECONDS = 300

_redis = redis.Redis.from_url(
    os.environ["REDIS_URL"],
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

# Delete the lock only if it is still ours.
_RELEASE_SCRIPT = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)

stop = threading.Event()


def _handle_stop(_signum, _frame) -> None:
    stop.set()


def run_once() -> None:
    token = uuid.uuid4().hex
    try:
        got_lock = _redis.set(LOCK_KEY, token, nx=True, ex=LOCK_TTL_SECONDS)
    except redis.RedisError:
        logger.warning("Redis is not available, skipping this run")
        return

    if not got_lock:
        logger.info("Another worker is running the SLA check, skipping")
        return

    try:
        with SessionLocal() as db:
            flagged = run_sla_check(db, datetime.now(UTC))
        logger.info("SLA check done, %s ticket(s) flagged", flagged)
    except Exception:
        # The worker must never die because of one bad run.
        logger.exception("SLA check failed")
    finally:
        try:
            _redis.eval(_RELEASE_SCRIPT, 1, LOCK_KEY, token)
        except redis.RedisError:
            logger.warning("Could not release the lock, it will expire by itself")


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    logger.info("SLA worker started, checking every %s seconds", INTERVAL_SECONDS)
    while not stop.is_set():
        run_once()
        stop.wait(INTERVAL_SECONDS)
    logger.info("SLA worker stopped")


if __name__ == "__main__":
    main()