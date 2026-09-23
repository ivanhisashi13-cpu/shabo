"""Password hashing and JWT helpers."""

import datetime
from typing import Optional

from jose import jwt
from jose import JWTError
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw_password: str) -> str:
	"""Hash a plaintext password.

	Args:
		raw_password: Plaintext password.

	Returns:
		str: Bcrypt hash.
	"""
	return _pwd_context.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
	"""Check a plaintext password against a stored hash.

	Args:
		raw_password: Plaintext password.
		password_hash: Stored bcrypt hash.

	Returns:
		bool: ``True`` when the password matches.
	"""
	return _pwd_context.verify(raw_password, password_hash)


def create_access_token(user_id: str) -> str:
	"""Issue a signed access token for a player.

	Args:
		user_id: Public player identifier.

	Returns:
		str: Encoded JWT.
	"""
	expire = datetime.datetime.utcnow() + datetime.timedelta(days=settings.token_expire_days)
	payload = {"sub": user_id, "exp": expire}
	return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Optional[str]:
	"""Decode a token and return the player identifier.

	Args:
		token: Encoded JWT.

	Returns:
		Optional[str]: Player identifier, or ``None`` when invalid.
	"""
	try:
		payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
	except JWTError:
		return None
	subject = payload.get("sub")
	return subject if isinstance(subject, str) else None
