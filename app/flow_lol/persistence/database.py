"""SQLite persistence schema (stub for Phase 0)."""

from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Session(Base):  # noqa: A001
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    started_at = Column(Float, nullable=False)
    ended_at = Column(Float, nullable=True)
    game_mode = Column(String, nullable=True)
    sensor_summary = Column(String, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    ensemble_label = Column(Integer, nullable=True)
    ensemble_proba_flow = Column(Float, nullable=True)


def init_db(db_path: str) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)


def session_maker(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}")
    return sessionmaker(bind=engine)
