"""FastAPI application entry point for the SHABO game server."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base
from app.database import engine
from app.database import ensure_schema
from app.game.room import room_manager
from app.routers import auth
from app.routers import profile
from app.ws import router as ws_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="SHABO 联机对局服务", version="1.0.0")

app.add_middleware(
	CORSMiddleware,
	allow_origin_regex=".*",
	allow_credentials=False,
	allow_methods=["*"],
	allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
ensure_schema()

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(ws_router)


@app.get("/api/health")
def health() -> dict:
	"""Report service liveness and live room statistics.

	Returns:
		dict: Health payload.
	"""
	return {
		"status": "ok",
		"rooms": len(room_manager.rooms),
		"players_in_rooms": len(room_manager.user_room),
	}
