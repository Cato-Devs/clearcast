"""Settings, read from the environment (see docker-compose.yml and the root .env)."""
import os

DATABASE_URL = os.environ["DATABASE_URL"]
ML_SERVICE_URL = os.environ["ML_SERVICE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL_MINUTES", "15"))

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

# A short secret can be guessed offline from any login token, which would let someone forge logins
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters long.")

# The admin account is created from these when the backend starts. There is no public admin sign-up.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Live weather is optional: without a key, that source is skipped and Open-Meteo's estimates are used
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip()
TOMORROW_API_KEY = os.environ.get("TOMORROW_API_KEY", "").strip()

# Email is optional: without SMTP_HOST, alerts still appear in the app
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM") or SMTP_USER or "alerts@clearcast.local"
