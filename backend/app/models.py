"""Database models for the SHABO game server."""

import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String

from app.database import Base

AVATAR_PRESETS = (
	"fox", "panda", "owl", "cat", "wolf", "bear",
	"rabbit", "tiger", "penguin", "koala", "deer", "dragon",
	"whale",
)


class User(Base):
	"""A registered player account."""

	__tablename__ = "users"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(String(16), unique=True, nullable=False, index=True)
	password_hash = Column(String(255), nullable=False)
	nickname = Column(String(32), nullable=False)
	avatar = Column(String(32), nullable=False, default="fox")
	games_played = Column(Integer, nullable=False, default=0)
	games_won = Column(Integer, nullable=False, default=0)
	shabo_count = Column(Integer, nullable=False, default=0)
	best_multi_score = Column(Integer, nullable=True)
	season_key = Column(String(7), nullable=True)
	season_wins = Column(Integer, nullable=False, default=0)
	season_shabo = Column(Integer, nullable=False, default=0)
	season_low = Column(Integer, nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)


class SeasonRecord(Base):
	"""Archived standings of a player for one finished season."""

	__tablename__ = "season_records"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(String(16), nullable=False, index=True)
	season_key = Column(String(7), nullable=False, index=True)
	wins = Column(Integer, nullable=False, default=0)
	wins_rank = Column(Integer, nullable=True)
	best_multi_score = Column(Integer, nullable=True)
	low_rank = Column(Integer, nullable=True)
	shabo_count = Column(Integer, nullable=False, default=0)
	shabo_rank = Column(Integer, nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)


class AppState(Base):
	"""Simple key/value store for server-wide runtime state."""

	__tablename__ = "app_state"

	key = Column(String(32), primary_key=True)
	value = Column(String(64), nullable=False)
