"""One-time codes, sent by SMS, that prove someone has the phone number they entered.

A code is kept in Redis for CODE_TTL_SECONDS, only as a hash, together with what to do once it's
confirmed (for sign-up: the new account's details, with the password already hashed).
"""
import hashlib
import hmac
import json
import logging
import secrets

import httpx
import redis
from fastapi import HTTPException

from app.config import JWT_SECRET
from app.realtime import client
from app.sms import send_sms, sms_enabled

log = logging.getLogger("uvicorn.error")

CODE_TTL_SECONDS = 10 * 60
MAX_WRONG_TRIES = 5
RESEND_WAIT_SECONDS = 60
# Each code is an SMS that costs money, so how many can be asked for is limited
MAX_CODES_PER_PHONE_PER_HOUR = 5
MAX_CODES_PER_ADDRESS_PER_HOUR = 20


def code_hash(phone, code):
    return hmac.new(JWT_SECRET.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def limit_hit(key, limit, seconds):
    """Counts one more use of key; True if that goes over the limit."""
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.expire(key, seconds, nx=True)
    count, _ = pipe.execute()
    return count > limit


def send_code(key, phone, address, payload):
    """Send a new code to phone and remember payload until it's confirmed.

    If SMS isn't set up, the code is written to the backend log instead, so the system can still
    be tried out locally (docker compose logs backend). It's never shown to the person asking.
    """
    try:
        if not client.set(f"otp-wait:{phone}", 1, ex=RESEND_WAIT_SECONDS, nx=True):
            raise HTTPException(status_code=429, detail="Wait a minute before asking for another code.")
        if limit_hit(f"otp-phone:{phone}", MAX_CODES_PER_PHONE_PER_HOUR, 3600) or limit_hit(
            f"otp-address:{address}", MAX_CODES_PER_ADDRESS_PER_HOUR, 3600
        ):
            raise HTTPException(status_code=429, detail="Too many codes asked for. Try again in an hour.")
        code = f"{secrets.randbelow(10**6):06d}"
        entry = {"phone": phone, "hash": code_hash(phone, code), "wrong": 0, "payload": payload}
        client.set(key, json.dumps(entry), ex=CODE_TTL_SECONDS)
    except redis.RedisError as e:
        log.warning("Could not store a one-time code: %s", e)
        raise HTTPException(status_code=503, detail="Couldn't send a code right now. Try again shortly.")

    text = f"Your ClearCast code is {code}. It expires in 10 minutes. Don't share it with anyone."
    if not sms_enabled():
        log.warning("SMS isn't set up, so the code for %s is written here instead: %s", phone, code)
        return
    try:
        send_sms(phone, text)
    except (httpx.HTTPError, RuntimeError, ValueError) as e:
        log.warning("Could not send a one-time code to %s: %s", phone, e)
        client.delete(key)
        raise HTTPException(status_code=502, detail="Couldn't send the code by SMS. Check the number and try again.")


def check_code(key, code):
    """The stored entry if code is right; it can then not be used again. Raises otherwise."""
    try:
        raw = client.get(key)
        if raw is None:
            raise HTTPException(status_code=400, detail="This code has expired. Ask for a new one.")
        entry = json.loads(raw)
        if hmac.compare_digest(entry["hash"], code_hash(entry["phone"], code.strip())):
            client.delete(key)
            return entry
        entry["wrong"] += 1
        if entry["wrong"] >= MAX_WRONG_TRIES:
            client.delete(key)
            raise HTTPException(status_code=400, detail="Too many wrong codes. Ask for a new one.")
        client.set(key, json.dumps(entry), keepttl=True)
    except redis.RedisError as e:
        log.warning("Could not check a one-time code: %s", e)
        raise HTTPException(status_code=503, detail="Couldn't check the code right now. Try again shortly.")
    raise HTTPException(status_code=400, detail="That code isn't right. Check the SMS and try again.")
