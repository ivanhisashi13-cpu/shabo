"""Room lifecycle management for online matches."""

import random
import string
import time
from typing import Dict
from typing import List
from typing import Optional

from app.config import settings
from app.game.engine import GameEngine
from app.game.engine import MODE_MULTI
from app.game.engine import MODE_SINGLE
from app.models import AVATAR_PRESETS

ROOM_MIN_PLAYERS = 2
ROOM_MAX_PLAYERS = 5
ROOM_CODE_LENGTH = 6
MAX_CHAT_HISTORY = 30
CHAT_KIND_TEXT = "text"
CHAT_KIND_EMOJI = "emoji"
EMOJI_KEYS = ("lol", "wow", "angry", "boom", "smirk", "cry", "clap", "thumb")

STATUS_WAITING = "waiting"
STATUS_PLAYING = "playing"


class RoomError(Exception):
	"""Raised when a room operation is not allowed."""


class Room:
	"""A joinable match room."""

	def __init__(self, code: str, host_user_id: str, max_players: int, mode: str) -> None:
		"""Create an empty room.

		Args:
			code: Six digit room code.
			host_user_id: Creator identifier.
			max_players: Player capacity between 2 and 5.
			mode: ``SINGLE`` or ``MULTI``.
		"""
		self.code = code
		self.host_user_id = host_user_id
		self.max_players = max_players
		self.mode = mode
		self.status = STATUS_WAITING
		self.members: List[dict] = []
		self.chat: List[dict] = []
		self.engine: Optional[GameEngine] = None

	def member(self, user_id: str) -> Optional[dict]:
		"""Look up a member record.

		Args:
			user_id: Player identifier.

		Returns:
			Optional[dict]: Member record, or ``None``.
		"""
		for item in self.members:
			if item["user_id"] == user_id:
				return item
		return None

	def member_ids(self) -> List[str]:
		"""Return all member identifiers in seat order.

		Returns:
			List[str]: Member identifiers.
		"""
		return [item["user_id"] for item in self.members]

	def is_full(self) -> bool:
		"""Tell whether the room reached capacity.

		Returns:
			bool: ``True`` when no seat is free.
		"""
		return len(self.members) >= self.max_players

	def add_member(self, user_id: str, nickname: str, avatar: str) -> None:
		"""Seat a player in the room.

		Args:
			user_id: Player identifier.
			nickname: Display name.
			avatar: Avatar key.

		Raises:
			RoomError: When the room is full or the match already started.
		"""
		if self.member(user_id) is not None:
			return
		if self.status == STATUS_PLAYING:
			raise RoomError("房间对局中，无法加入")
		if self.is_full():
			raise RoomError("房间人数已满")
		self.members.append({
			"user_id": user_id,
			"nickname": nickname,
			"avatar": avatar,
			"ready": user_id == self.host_user_id,
			"online": True,
			"is_bot": False,
		})

	def human_members(self) -> List[dict]:
		"""Return only the real (non bot) members.

		Returns:
			List[dict]: Members backed by a real account.
		"""
		return [item for item in self.members if not item.get("is_bot")]

	def add_bot(self) -> str:
		"""Seat a random behaviour bot in a free slot.

		Returns:
			str: The generated bot identifier.

		Raises:
			RoomError: When the match started or the room is full.
		"""
		if self.status == STATUS_PLAYING:
			raise RoomError("对局进行中，无法添加机器人")
		if self.is_full():
			raise RoomError("房间人数已满")
		bot_count = sum(1 for item in self.members if item.get("is_bot"))
		bot_id = "bot_" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
		self.members.append({
			"user_id": bot_id,
			"nickname": f"机器人{bot_count + 1}",
			"avatar": random.choice(AVATAR_PRESETS),
			"ready": True,
			"online": True,
			"is_bot": True,
		})
		return bot_id

	def remove_bot(self, bot_id: str) -> None:
		"""Remove a seated bot.

		Args:
			bot_id: Bot identifier.

		Raises:
			RoomError: When the match started or the id is not a bot.
		"""
		if self.status == STATUS_PLAYING:
			raise RoomError("对局进行中，无法移除机器人")
		item = self.member(bot_id)
		if item is None or not item.get("is_bot"):
			raise RoomError("该机器人不存在")
		self.members = [entry for entry in self.members if entry["user_id"] != bot_id]

	def bot_ids(self) -> List[str]:
		"""Return all seated bot identifiers.

		Returns:
			List[str]: Bot identifiers.
		"""
		return [item["user_id"] for item in self.members if item.get("is_bot")]

	def remove_member(self, user_id: str) -> None:
		"""Remove a player and hand the host role over when needed.

		Args:
			user_id: Player identifier.
		"""
		self.members = [item for item in self.members if item["user_id"] != user_id]
		if self.host_user_id == user_id and self.members:
			humans = self.human_members()
			new_host = humans[0] if humans else self.members[0]
			self.host_user_id = new_host["user_id"]
			new_host["ready"] = True

	def set_ready(self, user_id: str, ready: bool) -> None:
		"""Update the ready flag of a member.

		Args:
			user_id: Player identifier.
			ready: Desired ready state.

		Raises:
			RoomError: When the player is not seated.
		"""
		item = self.member(user_id)
		if item is None:
			raise RoomError("你不在该房间中")
		item["ready"] = True if user_id == self.host_user_id else ready

	def all_ready(self) -> bool:
		"""Tell whether every non host member is ready.

		Returns:
			bool: ``True`` when the match may start.
		"""
		return all(item["ready"] or item["user_id"] == self.host_user_id for item in self.members)

	def can_start(self) -> bool:
		"""Tell whether the host may start a match.

		Returns:
			bool: ``True`` when enough players are ready.
		"""
		return (
			self.status == STATUS_WAITING
			and len(self.members) >= ROOM_MIN_PLAYERS
			and self.all_ready()
		)

	def add_chat(self, user_id: Optional[str], nickname: str, text: str,
		kind: str = CHAT_KIND_TEXT) -> dict:
		"""Append a chat, emoji or system line.

		Args:
			user_id: Author identifier, ``None`` for system lines.
			nickname: Author display name.
			text: Message body, or an emoji key for emoji messages.
			kind: ``text`` or ``emoji``.

		Returns:
			dict: The stored message.

		Raises:
			RoomError: When an emoji key is unknown.
		"""
		if kind == CHAT_KIND_EMOJI and text not in EMOJI_KEYS:
			raise RoomError("不支持的表情")
		message = {
			"user_id": user_id,
			"nickname": nickname,
			"text": text[:100],
			"kind": kind,
			"at": int(time.time() * 1000),
		}
		self.chat.append(message)
		if len(self.chat) > MAX_CHAT_HISTORY:
			self.chat = self.chat[-MAX_CHAT_HISTORY:]
		return message

	def start_game(self) -> None:
		"""Create the engine and deal the first round.

		Raises:
			RoomError: When the room is not ready to start.
		"""
		if not self.can_start():
			raise RoomError("需要至少 2 名玩家且全部准备完毕")
		self.engine = GameEngine(
			[
				{"user_id": item["user_id"], "nickname": item["nickname"], "avatar": item["avatar"]}
				for item in self.members
			],
			mode=self.mode,
			turn_timeout=settings.turn_timeout_seconds,
			peek_timeout=settings.peek_timeout_seconds,
			reveal_seconds=settings.reveal_seconds,
			target_score=settings.target_score,
		)
		for item in self.members:
			self.engine.set_online(item["user_id"], item["online"])
		self.engine.start_round()
		self.status = STATUS_PLAYING

	def back_to_lobby(self) -> None:
		"""Drop the finished game and reset ready flags."""
		self.engine = None
		self.status = STATUS_WAITING
		for item in self.members:
			item["ready"] = item["user_id"] == self.host_user_id or item.get("is_bot", False)

	def to_state(self) -> dict:
		"""Serialize the room view.

		Returns:
			dict: Room state for clients.
		"""
		return {
			"code": self.code,
			"host_user_id": self.host_user_id,
			"max_players": self.max_players,
			"mode": self.mode,
			"status": self.status,
			"members": [dict(item) for item in self.members],
			"can_start": self.can_start(),
			"chat": list(self.chat[-20:]),
		}


class RoomManager:
	"""In-memory registry of active rooms."""

	def __init__(self) -> None:
		"""Create an empty registry."""
		self.rooms: Dict[str, Room] = {}
		self.user_room: Dict[str, str] = {}

	def _new_code(self) -> str:
		"""Generate an unused six digit room code.

		Returns:
			str: Room code.
		"""
		while True:
			code = "".join(random.choice(string.digits) for _ in range(ROOM_CODE_LENGTH))
			if code not in self.rooms:
				return code

	def create(self, host_user_id: str, nickname: str, avatar: str, max_players: int,
		mode: str) -> Room:
		"""Create a room and seat the host.

		Args:
			host_user_id: Creator identifier.
			nickname: Creator display name.
			avatar: Creator avatar key.
			max_players: Capacity between 2 and 5.
			mode: ``SINGLE`` or ``MULTI``.

		Returns:
			Room: The created room.

		Raises:
			RoomError: When the capacity is out of range.
		"""
		if not ROOM_MIN_PLAYERS <= max_players <= ROOM_MAX_PLAYERS:
			raise RoomError(f"房间人数需在 {ROOM_MIN_PLAYERS}-{ROOM_MAX_PLAYERS} 之间")
		normalized_mode = mode if mode in (MODE_SINGLE, MODE_MULTI) else MODE_SINGLE

		self.leave(host_user_id)
		room = Room(self._new_code(), host_user_id, max_players, normalized_mode)
		room.add_member(host_user_id, nickname, avatar)
		self.rooms[room.code] = room
		self.user_room[host_user_id] = room.code
		return room

	def get(self, code: str) -> Optional[Room]:
		"""Fetch a room by code.

		Args:
			code: Room code.

		Returns:
			Optional[Room]: Matching room, or ``None``.
		"""
		return self.rooms.get(code)

	def room_of(self, user_id: str) -> Optional[Room]:
		"""Fetch the room a player currently occupies.

		Args:
			user_id: Player identifier.

		Returns:
			Optional[Room]: Matching room, or ``None``.
		"""
		code = self.user_room.get(user_id)
		return self.rooms.get(code) if code else None

	def join(self, code: str, user_id: str, nickname: str, avatar: str) -> Room:
		"""Seat a player in an existing room.

		Args:
			code: Room code.
			user_id: Player identifier.
			nickname: Display name.
			avatar: Avatar key.

		Returns:
			Room: The joined room.

		Raises:
			RoomError: When the room is missing, full or in progress.
		"""
		room = self.rooms.get(code)
		if room is None:
			raise RoomError("房间不存在")
		if room.status == STATUS_PLAYING and room.member(user_id) is None:
			raise RoomError("房间对局中，无法加入")

		current = self.room_of(user_id)
		if current is not None and current.code != code:
			self.leave(user_id)

		room.add_member(user_id, nickname, avatar)
		self.user_room[user_id] = room.code
		return room

	def leave(self, user_id: str) -> Optional[Room]:
		"""Remove a player from their current room.

		Args:
			user_id: Player identifier.

		Returns:
			Optional[Room]: The room left, or ``None`` when idle.
		"""
		room = self.room_of(user_id)
		if room is None:
			return None

		if room.engine is not None and room.status == STATUS_PLAYING:
			room.engine.player_left(user_id)
		room.remove_member(user_id)
		self.user_room.pop(user_id, None)

		if not room.human_members():
			room.members = []
			self.rooms.pop(room.code, None)
		return room

	def update_profile(self, user_id: str, nickname: str, avatar: str) -> None:
		"""Refresh cached profile fields everywhere.

		Args:
			user_id: Player identifier.
			nickname: New display name.
			avatar: New avatar key.
		"""
		room = self.room_of(user_id)
		if room is None:
			return
		item = room.member(user_id)
		if item is not None:
			item["nickname"] = nickname
			item["avatar"] = avatar
		if room.engine is not None:
			player = room.engine.player(user_id)
			if player is not None:
				player.nickname = nickname
				player.avatar = avatar


room_manager = RoomManager()
