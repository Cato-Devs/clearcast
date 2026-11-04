"""Database connection and tables."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


class Base(DeclarativeBase):
    pass


class Prediction(Base):
    """One location, event and hour, as defined in docs/prediction-format.md."""

    __tablename__ = "predictions"
    __table_args__ = (
        # The collector runs several times an hour: a repeat run updates the row, not adds one
        # This also creates the index that makes finding the latest prediction fast
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
