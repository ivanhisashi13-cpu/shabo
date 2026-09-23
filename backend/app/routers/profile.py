"""Profile endpoints for nickname and avatar updates."""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.game.room import room_manager
from app.models import AVATAR_PRESETS
from app.models import SeasonRecord
from app.models import User
from app.routers.auth import to_user_out
from app.schemas import ProfileUpdateIn
from app.schemas import UserOut
from app.season import ensure_season

router = APIRouter(prefix="/api", tags=["profile"])

LEADERBOARD_LIMIT = 20


@router.get("/avatars")
def list_avatars() -> dict:
	"""Return the selectable avatar keys.

	Returns:
		dict: ``{"avatars": [...]}``.
	"""
	return {"avatars": list(AVATAR_PRESETS)}


@router.get("/leaderboard")
def read_leaderboard(
	user: User = Depends(get_current_user),
	db: Session = Depends(get_db),
) -> dict:
	"""Return the top players of each ranking board plus the caller's rank.

	Three boards are provided: most wins, lowest completed 100-point score,
	and most times becoming the round loser (shabo).

	Args:
		user: Authenticated requester.
		db: Database session.

	Returns:
		dict: ``{"boards": {name: {"top": [...], "me": {...}|None}}}``.
	"""
	def entry(row: User, value) -> dict:
		return {
			"user_id": row.user_id,
			"nickname": row.nickname,
			"avatar": row.avatar,
			"value": value,
		}

	def build(rows: list, value_of) -> dict:
		top = []
		me = None
		for index, row in enumerate(rows):
			item = {"rank": index + 1, **entry(row, value_of(row))}
			if index < LEADERBOARD_LIMIT:
				top.append(item)
			if row.user_id == user.user_id:
				me = item
		return {"top": top, "me": me}

	season_key = ensure_season(db)
	win_rows = (
		db.query(User)
		.filter(User.season_wins > 0)
		.order_by(User.season_wins.desc(), User.games_played.asc())
		.all()
	)
	low_rows = (
		db.query(User)
		.filter(User.season_low.isnot(None))
		.order_by(User.season_low.asc())
		.all()
	)
	shabo_rows = (
		db.query(User)
		.filter(User.season_shabo > 0)
		.order_by(User.season_shabo.desc())
		.all()
	)

	return {
		"season": season_key,
		"boards": {
			"wins": build(win_rows, lambda row: row.season_wins),
			"low": build(low_rows, lambda row: row.season_low),
			"shabo": build(shabo_rows, lambda row: row.season_shabo or 0),
		},
	}


@router.get("/users/{user_id}/stats")
def read_stats(
	user_id: str,
	_: User = Depends(get_current_user),
	db: Session = Depends(get_db),
) -> dict:
	"""Return the public record card of any registered player.

	Args:
		user_id: Target player identifier.
		_: Authenticated requester (login required).
		db: Database session.

	Returns:
		dict: Record fields including shabo count and best multi score.

	Raises:
		HTTPException: When the player does not exist.
	"""
	target = db.query(User).filter(User.user_id == user_id).first()
	if target is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="玩家不存在")
	season_key = ensure_season(db)
	records = (
		db.query(SeasonRecord)
		.filter(SeasonRecord.user_id == user_id)
		.order_by(SeasonRecord.season_key.desc())
		.all()
	)
	return {
		"user_id": target.user_id,
		"nickname": target.nickname,
		"avatar": target.avatar,
		"games_played": target.games_played,
		"games_won": target.games_won,
		"shabo_count": target.shabo_count or 0,
		"best_multi_score": target.best_multi_score,
		"season": {
			"key": season_key,
			"wins": target.season_wins or 0,
			"shabo_count": target.season_shabo or 0,
			"best_multi_score": target.season_low,
		},
		"history": [
			{
				"season": record.season_key,
				"wins": record.wins,
				"wins_rank": record.wins_rank,
				"best_multi_score": record.best_multi_score,
				"low_rank": record.low_rank,
				"shabo_count": record.shabo_count,
				"shabo_rank": record.shabo_rank,
			}
			for record in records
		],
	}


@router.put("/users/me", response_model=UserOut)
def update_me(
	payload: ProfileUpdateIn,
	user: User = Depends(get_current_user),
	db: Session = Depends(get_db),
) -> UserOut:
	"""Update the nickname or avatar of the signed-in player.

	Args:
		payload: Fields to change.
		user: Authenticated player.
		db: Database session.

	Returns:
		UserOut: Updated public profile.

	Raises:
		HTTPException: When a submitted field is invalid.
	"""
	if payload.nickname is not None:
		nickname = payload.nickname.strip()
		if not 2 <= len(nickname) <= 12:
			raise HTTPException(
				status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
				detail="昵称需为2-12个字符",
			)
		user.nickname = nickname

	if payload.avatar is not None:
		if payload.avatar not in AVATAR_PRESETS:
			raise HTTPException(
				status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
				detail="头像不存在",
			)
		user.avatar = payload.avatar

	db.commit()
	db.refresh(user)
	room_manager.update_profile(user.user_id, user.nickname, user.avatar)
	return to_user_out(user)
