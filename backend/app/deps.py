"""Shared FastAPI dependencies."""

from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token


def get_current_user(
	authorization: str = Header(default=""),
	db: Session = Depends(get_db),
) -> User:
	"""Resolve the authenticated player from the Authorization header.

	Args:
		authorization: Raw ``Bearer <token>`` header value.
		db: Database session.

	Returns:
		User: Authenticated player.

	Raises:
		HTTPException: When the token is missing, invalid or orphaned.
	"""
	if not authorization.lower().startswith("bearer "):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

	token = authorization.split(" ", 1)[1].strip()
	user_id = decode_access_token(token)
	if not user_id:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

	user = db.query(User).filter(User.user_id == user_id).first()
	if user is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在")
	return user
