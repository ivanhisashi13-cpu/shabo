"""Database engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def ensure_schema() -> None:
	"""Add newly introduced columns to the users table when missing.

	SQLAlchemy ``create_all`` never alters existing tables, so this keeps
	deployed SQLite databases in sync with the current model definition.
	"""
	inspector = inspect(engine)
	if "users" not in inspector.get_table_names():
		return
	columns = {column["name"] for column in inspector.get_columns("users")}
	statements = []
	if "shabo_count" not in columns:
		statements.append("ALTER TABLE users ADD COLUMN shabo_count INTEGER NOT NULL DEFAULT 0")
	if "best_multi_score" not in columns:
		statements.append("ALTER TABLE users ADD COLUMN best_multi_score INTEGER")
	if "season_key" not in columns:
		statements.append("ALTER TABLE users ADD COLUMN season_key VARCHAR(7)")
	if "season_wins" not in columns:
		statements.append("ALTER TABLE users ADD COLUMN season_wins INTEGER NOT NULL DEFAULT 0")
	if "season_shabo" not in columns:
		statements.append("ALTER TABLE users ADD COLUMN season_shabo INTEGER NOT NULL DEFAULT 0")
	if "season_low" not in columns:
		statements.append("ALTER TABLE users ADD COLUMN season_low INTEGER")
	if not statements:
		return
	with engine.begin() as connection:
		for statement in statements:
			connection.execute(text(statement))


def get_db():
	"""Yield a database session for request scope.

	Yields:
		Session: Active SQLAlchemy session closed after use.
	"""
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
