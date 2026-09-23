"""Season rollover and archival helpers.

Seasons follow the calendar month in UTC+8. When the month changes the current
standings of every ranking board are archived into ``SeasonRecord`` and the
per-user seasonal counters are reset so the new season starts clean.
"""

import datetime

from sqlalchemy.orm import Session

from app.models import AppState
from app.models import SeasonRecord
from app.models import User

_SEASON_STATE_KEY = "current_season"
_CST = datetime.timezone(datetime.timedelta(hours=8))


def current_season_key() -> str:
	"""Return the active season identifier formatted as ``YYYY-MM``.

	Returns:
		str: Season key derived from the current UTC+8 calendar month.
	"""
	now = datetime.datetime.now(_CST)
	return f"{now.year:04d}-{now.month:02d}"


def _rank_map(ordered: list) -> dict:
	"""Build a ``{user_id: rank}`` mapping from an ordered value list.

	Args:
		ordered: List of ``(user_id, value)`` already sorted best first.

	Returns:
		dict: Standard competition ranking keyed by user id.
	"""
	ranks = {}
	previous = None
	rank = 0
	for index, (user_id, value) in enumerate(ordered):
		if previous is None or value != previous:
			rank = index + 1
			previous = value
		ranks[user_id] = rank
	return ranks


def _archive_season(db: Session, season_key: str) -> None:
	"""Archive the standings of the ending season for every participant.

	Args:
		db: Active database session.
		season_key: The season that just ended.
	"""
	users = db.query(User).all()
	participants = [
		user for user in users
		if (user.season_wins or 0) > 0
		or user.season_low is not None
		or (user.season_shabo or 0) > 0
	]
	if not participants:
		return

	wins_rank = _rank_map(sorted(
		[(u.user_id, u.season_wins or 0) for u in participants if (u.season_wins or 0) > 0],
		key=lambda item: -item[1],
	))
	low_rank = _rank_map(sorted(
		[(u.user_id, u.season_low) for u in participants if u.season_low is not None],
		key=lambda item: item[1],
	))
	shabo_rank = _rank_map(sorted(
		[(u.user_id, u.season_shabo or 0) for u in participants if (u.season_shabo or 0) > 0],
		key=lambda item: -item[1],
	))

	for user in participants:
		db.add(SeasonRecord(
			user_id=user.user_id,
			season_key=season_key,
			wins=user.season_wins or 0,
			wins_rank=wins_rank.get(user.user_id),
			best_multi_score=user.season_low,
			low_rank=low_rank.get(user.user_id),
			shabo_count=user.season_shabo or 0,
			shabo_rank=shabo_rank.get(user.user_id),
		))


def ensure_season(db: Session) -> str:
	"""Roll the season over when the calendar month has changed.

	Archives the previous standings and resets seasonal counters on rollover.

	Args:
		db: Active database session.

	Returns:
		str: The active season key after any rollover.
	"""
	current = current_season_key()
	state = db.query(AppState).filter(AppState.key == _SEASON_STATE_KEY).first()
	if state is None:
		db.add(AppState(key=_SEASON_STATE_KEY, value=current))
		db.commit()
		return current
	if state.value == current:
		return current

	_archive_season(db, state.value)
	db.query(User).update({
		User.season_key: current,
		User.season_wins: 0,
		User.season_shabo: 0,
		User.season_low: None,
	})
	state.value = current
	db.commit()
	return current
