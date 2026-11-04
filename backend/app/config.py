"""Settings, read from the environment (see docker-compose.yml and the root .env)."""
import os

DATABASE_URL = os.environ["DATABASE_URL"]
ML_SERVICE_URL = os.environ["ML_SERVICE_URL"]
POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL_MINUTES", "15"))

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

# A short secret can be guessed offline from any login token, which would let someone forge logins
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters long.")
