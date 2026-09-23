"""Account registration and login endpoints."""

import random

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.deps import get_current_user
from app.models import AVATAR_PRESETS
from app.models import User
from app.schemas import LoginIn
from app.schemas import RegisterIn
from app.schemas import TokenOut
from app.schemas import UserOut
from app.security import create_access_token
from app.security import hash_password
from app.security import verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def to_user_out(user: User) -> UserOut:
	"""Convert a model row to its public schema.

	Args:
		user: Database row.

	Returns:
		UserOut: Public profile.
	"""
	return UserOut(
		user_id=user.user_id,
		nickname=user.nickname,
		avatar=user.avatar,
		games_played=user.games_played,
		games_won=user.games_won,
		is_admin=user.user_id in settings.admin_user_ids,
	)


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
	"""Create an account and log the player in.

	Args:
		payload: Registration fields.
		db: Database session.

	Returns:
		TokenOut: Access token and profile.

	Raises:
		HTTPException: When the identifier is taken.
	"""
	exists = db.query(User).filter(User.user_id == payload.user_id).first()
	if exists is not None:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该用户ID已被注册")

	user = User(
		user_id=payload.user_id,
		password_hash=hash_password(payload.password),
		nickname=payload.nickname,
		avatar=random.choice(AVATAR_PRESETS),
	)
	db.add(user)
	db.commit()
	db.refresh(user)
	return TokenOut(access_token=create_access_token(user.user_id), user=to_user_out(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
	"""Authenticate a player.

	Args:
		payload: Login fields.
		db: Database session.

	Returns:
		TokenOut: Access token and profile.

	Raises:
		HTTPException: When the account is missing or the password is wrong.
	"""
	user = db.query(User).filter(User.user_id == payload.user_id.strip()).first()
	if user is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
	if not verify_password(payload.password, user.password_hash):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码错误")
	return TokenOut(access_token=create_access_token(user.user_id), user=to_user_out(user))


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> UserOut:
	"""Return the signed-in player profile.

	Args:
		user: Authenticated player.

	Returns:
		UserOut: Public profile.
	"""
	return to_user_out(user)
