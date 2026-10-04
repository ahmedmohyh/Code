"""SQLite persistence schema."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Session(Base):  # noqa: A001
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    created_at = Column(Float, nullable=False)
    started_at = Column(Float, nullable=False)
    ended_at = Column(Float, nullable=True)
    game_mode = Column(String, nullable=True)
    sensor_summary = Column(String, nullable=True)
    window_seconds = Column(Integer, nullable=False)
    overlap_percent = Column(Integer, nullable=False)
    sampling_rate = Column(Integer, nullable=False)
    settings_json = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False, index=True)
    started_at = Column(Float, nullable=False)
    ended_at = Column(Float, nullable=True)
    game_mode = Column(String, nullable=False)
    detected = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False, index=True)
    match_id = Column(Integer, nullable=True, index=True)
    timestamp = Column(Float, nullable=False)
    sensor_name = Column(String, nullable=False)
    n_samples = Column(Integer, nullable=False)
    ensemble_label = Column(Integer, nullable=False)
    n_votes = Column(Integer, nullable=False)
    n_for_majority = Column(Integer, nullable=False)
    votes_json = Column(Text, nullable=False)
    probabilities_json = Column(Text, nullable=True)
    features_json = Column(Text, nullable=True)


class SensorEvent(Base):
    __tablename__ = "sensor_events"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(Float, nullable=False)
    sensor_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    message = Column(Text, nullable=True)


def init_db(db_path: str) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)


def session_maker(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}")
    return sessionmaker(bind=engine)
