"""Database connection and tables."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


class Base(DeclarativeBase):
    pass


class Prediction(Base):
    """One location, event and hour, as defined in docs/prediction-format.md."""

    __tablename__ = "predictions"
    __table_args__ = (
        # The collector runs several times an hour: a repeat run updates the row, not adds one.
        # This also creates the index that makes finding the latest prediction fast.
        UniqueConstraint("location", "event", "issued_at", name="uq_prediction_location_event_issued"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32))
    probability: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(16))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_version: Mapped[str] = mapped_column(String(32))


class Collection(Base):
    """One run of the collector, so admins can see whether the system is healthy."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total: Mapped[int] = mapped_column(Integer, default=0)
    saved: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[list] = mapped_column(JSON, default=list)


class PredictionSnapshot(Base):
    """What each collection predicted. Predictions keep only the newest value for an hour; this
    keeps them all, so alerts can wait for a band to hold and band changes can be measured."""

    __tablename__ = "prediction_snapshots"
    __table_args__ = (Index("ix_snapshot_latest", "location", "event", "collection_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    location: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(32))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    band: Mapped[str] = mapped_column(String(16))
    probability: Mapped[float] = mapped_column(Float)


class ApiCall(Base):
    """One call to a live weather API (see live_weather.py)."""

    __tablename__ = "api_calls"
    __table_args__ = (Index("ix_api_call_latest", "source", "location", "called_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(16))  # openweather or tomorrow
    location: Mapped[str] = mapped_column(String(64))
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    ok: Mapped[bool] = mapped_column(Boolean)
    status_code: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(64))
    reading: Mapped[dict | None] = mapped_column(JSON)  # the mapped fields, not the raw response
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(String(64))  # for example "light rain"


class CurrentWeather(Base):
    """The newest hour of weather each collection gave the models, for the current weather page."""

    __tablename__ = "current_weather"
    __table_args__ = (Index("ix_current_weather_latest", "location", "collection_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    location: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # the data hour
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # when the live reading was taken
    values: Mapped[dict] = mapped_column(JSON)
    sources: Mapped[dict] = mapped_column(JSON)  # field -> openweather, tomorrow or open_meteo
    description: Mapped[str | None] = mapped_column(String(64))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)  # optional, stored in lower case
    phone: Mapped[str | None] = mapped_column(String(16), unique=True)  # like +254712345678; the admin may have none
    password_hash: Mapped[str] = mapped_column(String(255))  # never the password itself
    home_location: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subscription(Base):
    """A user's alert. The kinds are "always" (an event becomes likely), "daily" (a briefing at
    a set time) and "trip" (a check on one place and time)."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    location: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # "always" alerts
    event: Mapped[str | None] = mapped_column(String(32))
    min_band: Mapped[str] = mapped_column(String(16), default="likely")
    notified_rank: Mapped[int] = mapped_column(Integer, default=0)  # the band last alerted on

    # "daily" briefings
    minutes_eat: Mapped[int | None] = mapped_column(Integer)  # minutes after midnight, East Africa Time
    last_sent_date: Mapped[date | None] = mapped_column(Date)

    # "trip" checks
    trip_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trip_ranks: Mapped[dict | None] = mapped_column(JSON)  # the bands last reported; None = not checked yet

    user: Mapped[User] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))
    location: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_status: Mapped[str | None] = mapped_column(String(16))  # None, pending, sent, not_configured or failed
    # None (no phone), pending, sent, failed, not_configured or limit (daily SMS limit reached)
    sms_status: Mapped[str | None] = mapped_column(String(16))

    user: Mapped[User] = relationship()


def create_tables():
    """Create missing tables, and add columns that came after a table was first created."""
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true"))
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE"))
        # Sign-up by phone number, with email optional
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(16)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS users_phone_key ON users (phone)"))
        connection.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
        connection.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS sms_status VARCHAR(16)"))
