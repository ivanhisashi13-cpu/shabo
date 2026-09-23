"""Application settings loaded from environment variables."""

import os


class Settings:
	"""Runtime configuration for the SHABO game server."""

	def __init__(self) -> None:
		"""Read configuration from the process environment."""
		self.database_url: str = os.getenv("DATABASE_URL", "sqlite:////data/shabo.db")
		self.secret_key: str = os.getenv("SECRET_KEY", "shabo-dev-secret-change-me")
		self.algorithm: str = "HS256"
		self.token_expire_days: int = int(os.getenv("TOKEN_EXPIRE_DAYS", "30"))
		self.turn_timeout_seconds: int = int(os.getenv("TURN_TIMEOUT_SECONDS", "30"))
		self.peek_timeout_seconds: int = int(os.getenv("PEEK_TIMEOUT_SECONDS", "15"))
		self.reveal_seconds: int = int(os.getenv("REVEAL_SECONDS", "3"))
		self.target_score: int = int(os.getenv("TARGET_SCORE", "100"))
		self.admin_user_ids: set = {
			item.strip() for item in os.getenv("ADMIN_USER_IDS", "ivan").split(",") if item.strip()
		}


settings = Settings()
