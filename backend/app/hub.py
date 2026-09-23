"""WebSocket connection registry and broadcast helpers."""

import asyncio
import logging
from typing import Dict
from typing import List
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionHub:
	"""Tracks one live socket per authenticated player."""

	def __init__(self) -> None:
		"""Create an empty hub."""
		self._sockets: Dict[str, WebSocket] = {}
		self._lock = asyncio.Lock()

	async def register(self, user_id: str, websocket: WebSocket) -> Optional[WebSocket]:
		"""Attach a socket to a player, replacing any previous one.

		Args:
			user_id: Player identifier.
			websocket: Newly authenticated socket.

		Returns:
			Optional[WebSocket]: The displaced socket, or ``None``.
		"""
		async with self._lock:
			previous = self._sockets.get(user_id)
			self._sockets[user_id] = websocket
			return previous

	async def unregister(self, user_id: str, websocket: WebSocket) -> None:
		"""Detach a socket if it is still the active one.

		Args:
			user_id: Player identifier.
			websocket: Socket being closed.
		"""
		async with self._lock:
			if self._sockets.get(user_id) is websocket:
				self._sockets.pop(user_id, None)

	def is_online(self, user_id: str) -> bool:
		"""Tell whether a player has a live socket.

		Args:
			user_id: Player identifier.

		Returns:
			bool: ``True`` when connected.
		"""
		return user_id in self._sockets

	def online_ids(self) -> List[str]:
		"""Return all connected player identifiers.

		Returns:
			List[str]: Connected identifiers.
		"""
		return list(self._sockets.keys())

	async def send(self, user_id: str, payload: dict) -> None:
		"""Send a JSON payload to one player, ignoring dead sockets.

		Args:
			user_id: Target player.
			payload: JSON serializable message.
		"""
		websocket = self._sockets.get(user_id)
		if websocket is None:
			return
		try:
			await websocket.send_json(payload)
		except (RuntimeError, ConnectionError) as error:
			logger.info("向 %s 推送失败: %s", user_id, error)
			self._sockets.pop(user_id, None)


hub = ConnectionHub()
