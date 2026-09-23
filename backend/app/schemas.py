"""Pydantic request and response models."""

import re
from typing import Optional

from pydantic import BaseModel
from pydantic import field_validator

_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")


class RegisterIn(BaseModel):
	"""Registration payload."""

	user_id: str
	password: str
	nickname: str

	@field_validator("user_id")
	@classmethod
	def check_user_id(cls, value: str) -> str:
		"""Validate the login identifier format.

		Args:
			value: Raw identifier.

		Returns:
			str: Normalized identifier.

		Raises:
			ValueError: When the identifier breaks the format rule.
		"""
		value = value.strip()
		if not _USER_ID_PATTERN.match(value):
			raise ValueError("用户ID需为3-20位字母、数字或下划线")
		return value

	@field_validator("password")
	@classmethod
	def check_password(cls, value: str) -> str:
		"""Validate the password length.

		Args:
			value: Raw password.

		Returns:
			str: Accepted password.

		Raises:
			ValueError: When the length is out of range.
		"""
		if not 6 <= len(value) <= 20:
			raise ValueError("密码需为6-20位")
		return value

	@field_validator("nickname")
	@classmethod
	def check_nickname(cls, value: str) -> str:
		"""Validate the nickname length.

		Args:
			value: Raw nickname.

		Returns:
			str: Trimmed nickname.

		Raises:
			ValueError: When the nickname is empty or too long.
		"""
		value = value.strip()
		if not 2 <= len(value) <= 12:
			raise ValueError("昵称需为2-12个字符")
		return value


class LoginIn(BaseModel):
	"""Login payload."""

	user_id: str
	password: str


class ProfileUpdateIn(BaseModel):
	"""Profile update payload."""

	nickname: Optional[str] = None
	avatar: Optional[str] = None


class UserOut(BaseModel):
	"""Public player profile."""

	user_id: str
	nickname: str
	avatar: str
	games_played: int
	games_won: int
	is_admin: bool = False


class TokenOut(BaseModel):
	"""Token issued after register or login."""

	access_token: str
	user: UserOut
