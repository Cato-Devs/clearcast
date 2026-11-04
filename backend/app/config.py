"""Settings, read from the environment (see docker-compose.yml and the root .env)."""
import os

DATABASE_URL = os.environ["DATABASE_URL"]
ML_SERVICE_URL = os.environ["ML_SERVICE_URL"]
POLL_INTERVAL_MINUTES = int(os.environ.get("POLL_INTERVAL_MINUTES", "15"))
