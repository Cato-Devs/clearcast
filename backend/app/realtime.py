"""Redis: limits on login attempts, and sending new notifications to open browsers."""
import json
import logging

import redis
import redis.asyncio as async_redis

from app.config import REDIS_URL

log = logging.getLogger("uvicorn.error")

client = redis.Redis.from_url(REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
async_client = async_redis.Redis.from_url(REDIS_URL)

MAX_FAILED_LOGINS = 10
FAILED_LOGIN_WINDOW_SECONDS = 15 * 60


def channel(user_id):
    return f"notifications:{user_id}"


def publish(user_id, notification):
    """Send to the user's open browsers. If this fails, they still see it on their next refresh."""
    try:
        client.publish(channel(user_id), json.dumps(notification))
    except redis.RedisError as e:
        log.warning("Could not publish a notification: %s", e)


# If Redis is down, logins carry on working without the limit, instead of nobody being able to log in.


def too_many_failed_logins(key):
    try:
        return int(client.get(f"login:{key}") or 0) >= MAX_FAILED_LOGINS
    except redis.RedisError as e:
        log.warning("Could not check the login limit: %s", e)
        return False


def record_failed_login(key):
    try:
        pipe = client.pipeline()
        pipe.incr(f"login:{key}")
        pipe.expire(f"login:{key}", FAILED_LOGIN_WINDOW_SECONDS)
        pipe.execute()
    except redis.RedisError as e:
        log.warning("Could not record a failed login: %s", e)


def clear_failed_logins(key):
    try:
        client.delete(f"login:{key}")
    except redis.RedisError as e:
        log.warning("Could not clear failed logins: %s", e)
