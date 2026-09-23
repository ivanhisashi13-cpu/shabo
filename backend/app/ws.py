"""WebSocket endpoint carrying the whole realtime game protocol."""

import asyncio
import logging
from typing import List
from typing import Optional

from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from app.database import SessionLocal
from app.config import settings
from app.game import bots
from app.game.engine import GameError
from app.game.engine import MODE_MULTI
from app.game.engine import MODE_SINGLE
from app.game.room import Room
from app.game.room import room_manager
from app.game.room import RoomError
from app.game.room import CHAT_KIND_EMOJI
from app.game.room import CHAT_KIND_TEXT
from app.game.room import ROOM_MAX_PLAYERS
from app.game.room import ROOM_MIN_PLAYERS
from app.game.room import STATUS_WAITING
from app.season import ensure_season
from app.hub import hub
from app.models import User
from app.security import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter()

TICK_INTERVAL_SECONDS = 0.4
KEEPALIVE_SECONDS = 20
_ticker_task: Optional[asyncio.Task] = None
_keepalive_task: Optional[asyncio.Task] = None


def filter_events(events: List[dict], viewer_id: str) -> List[dict]:
	"""Strip private card data from animation events.

	Args:
		events: Raw engine events.
		viewer_id: Player receiving the events.

	Returns:
		List[dict]: Events safe to send to this player.
	"""
	visible_events = []
	for event in events:
		audience = event.get("visible_to", "all")
		allowed = audience == "all" or viewer_id in audience
		if event["kind"] == "reveal" and not allowed:
			continue
		item = {key: value for key, value in event.items() if key != "visible_to"}
		if not allowed and "card" in item:
			item["card"] = None
		visible_events.append(item)
	return visible_events


def build_state(room: Room, viewer_id: str, events: List[dict]) -> dict:
	"""Build the full state message for one player.

	Args:
		room: Room to serialize.
		viewer_id: Player receiving the snapshot.
		events: Engine events emitted with this update.

	Returns:
		dict: ``room_state`` payload.
	"""
	return {
		"type": "room_state",
		"room": room.to_state(),
		"game": room.engine.snapshot_for(viewer_id) if room.engine else None,
		"events": filter_events(events, viewer_id),
	}


async def push_room(room: Room) -> None:
	"""Broadcast the current room state to every member.

	Args:
		room: Room to broadcast.
	"""
	events = room.engine.drain_events() if room.engine else []
	for member in room.members:
		await hub.send(member["user_id"], build_state(room, member["user_id"], events))


async def push_idle(user_id: str) -> None:
	"""Tell a player that they are not in any room.

	Args:
		user_id: Target player.
	"""
	await hub.send(user_id, {"type": "room_state", "room": None, "game": None, "events": []})


def record_match_stats(room: Room) -> None:
	"""Persist played and won counters after a finished match.

	Args:
		room: Room holding the finished engine.
	"""
	engine = room.engine
	if engine is None or engine.round_result is None or not engine.match_over:
		return
	result = engine.round_result
	winner_id = engine.winner_user_id
	shabo_id = result.get("shabo_user_id")
	mode = result.get("mode")
	rows = {row["user_id"]: row for row in result["players"]}
	player_ids = list(rows.keys())
	session = SessionLocal()
	try:
		ensure_season(session)
		for user_id in player_ids:
			user = session.query(User).filter(User.user_id == user_id).first()
			if user is None:
				continue
			user.games_played += 1
			if user_id == winner_id:
				user.games_won += 1
				user.season_wins = (user.season_wins or 0) + 1
			if user_id == shabo_id:
				user.shabo_count = (user.shabo_count or 0) + 1
				user.season_shabo = (user.season_shabo or 0) + 1
			if mode == MODE_MULTI:
				total = rows[user_id]["total_score"]
				if user.best_multi_score is None or total < user.best_multi_score:
					user.best_multi_score = total
				if user.season_low is None or total < user.season_low:
					user.season_low = total
		session.commit()
	except Exception as error:  # noqa: BLE001 - statistics must never break the match
		session.rollback()
		logger.warning("战绩写入失败: %s", error)
	finally:
		session.close()


async def ticker_loop() -> None:
	"""Advance every running game clock and broadcast on change."""
	while True:
		await asyncio.sleep(TICK_INTERVAL_SECONDS)
		for room in list(room_manager.rooms.values()):
			engine = room.engine
			if engine is None:
				continue
			try:
				changed = engine.tick()
				changed = bots.maybe_act(room) or changed
			except Exception as error:  # noqa: BLE001 - keep other rooms alive
				logger.exception("房间 %s 定时推进失败: %s", room.code, error)
				continue
			if not changed:
				continue
			if engine.round_result is not None and engine.match_over:
				record_match_stats(room)
			await push_room(room)


def ensure_ticker() -> None:
	"""Start the shared background tasks once."""
	global _ticker_task
	global _keepalive_task
	if _ticker_task is None or _ticker_task.done():
		_ticker_task = asyncio.create_task(ticker_loop())
	if _keepalive_task is None or _keepalive_task.done():
		_keepalive_task = asyncio.create_task(keepalive_loop())


async def keepalive_loop() -> None:
	"""Send a periodic ping downstream so idle sockets are not dropped.

	The browser throttles client side timers when a tab is in the background,
	so a server driven ping keeps the connection alive through proxies and NAT
	regardless of tab focus. The client ignores these frames.
	"""
	while True:
		await asyncio.sleep(KEEPALIVE_SECONDS)
		for user_id in hub.online_ids():
			await hub.send(user_id, {"type": "ping"})


async def authenticate(websocket: WebSocket) -> Optional[dict]:
	"""Wait for the auth frame and resolve the account.

	Args:
		websocket: Freshly accepted socket.

	Returns:
		Optional[dict]: ``{user_id, nickname, avatar}``, or ``None`` when rejected.
	"""
	try:
		message = await asyncio.wait_for(websocket.receive_json(), timeout=15)
	except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
		return None
	if message.get("type") != "auth":
		return None

	user_id = decode_access_token(str(message.get("token") or ""))
	if not user_id:
		await websocket.send_json({"type": "error", "message": "登录状态已失效，请重新登录"})
		return None

	session = SessionLocal()
	try:
		user = session.query(User).filter(User.user_id == user_id).first()
		if user is None:
			await websocket.send_json({"type": "error", "message": "账号不存在"})
			return None
		return {
			"user_id": user.user_id,
			"nickname": user.nickname,
			"avatar": user.avatar,
			"is_admin": user.user_id in settings.admin_user_ids,
		}
	finally:
		session.close()


async def handle_lobby_action(identity: dict, message: dict) -> bool:
	"""Handle room level commands.

	Args:
		identity: Authenticated player record.
		message: Incoming frame.

	Returns:
		bool: ``True`` when the frame was consumed.

	Raises:
		RoomError: When the room operation is illegal.
		GameError: When the match operation is illegal.
	"""
	user_id = identity["user_id"]
	action = message.get("type")

	if action == "create_room":
		max_players = int(message.get("max_players") or ROOM_MAX_PLAYERS)
		max_players = max(ROOM_MIN_PLAYERS, min(ROOM_MAX_PLAYERS, max_players))
		mode = MODE_MULTI if message.get("mode") == MODE_MULTI else MODE_SINGLE
		room = room_manager.create(user_id, identity["nickname"], identity["avatar"], max_players, mode)
		room.add_chat(None, "系统", f"{identity['nickname']} 创建了房间")
		await push_room(room)
		return True

	if action == "join_room":
		code = str(message.get("code") or "").strip()
		room = room_manager.join(code, user_id, identity["nickname"], identity["avatar"])
		room.add_chat(None, "系统", f"{identity['nickname']} 加入了房间")
		await push_room(room)
		return True

	if action == "leave_room":
		room = room_manager.leave(user_id)
		await push_idle(user_id)
		if room is not None and room.members:
			room.add_chat(None, "系统", f"{identity['nickname']} 离开了房间")
			await push_room(room)
		return True

	if action == "invite":
		target_id = str(message.get("user_id") or "").strip()
		room = room_manager.room_of(user_id)
		if room is None:
			raise RoomError("你还没有加入房间")
		if not hub.is_online(target_id):
			raise RoomError("对方当前不在线")
		await hub.send(target_id, {
			"type": "invite",
			"code": room.code,
			"from_nickname": identity["nickname"],
		})
		await hub.send(user_id, {"type": "notice", "message": "邀请已发送"})
		return True

	if action == "invite_response":
		if not message.get("accept"):
			return True
		code = str(message.get("code") or "").strip()
		room = room_manager.join(code, user_id, identity["nickname"], identity["avatar"])
		room.add_chat(None, "系统", f"{identity['nickname']} 接受邀请加入了房间")
		await push_room(room)
		return True

	return False


async def handle_room_action(identity: dict, room: Room, message: dict) -> bool:
	"""Handle commands that require a seat in a room.

	Args:
		identity: Authenticated player record.
		room: Room the player belongs to.
		message: Incoming frame.

	Returns:
		bool: ``True`` when the frame was consumed.

	Raises:
		RoomError: When the room operation is illegal.
		GameError: When the match operation is illegal.
	"""
	user_id = identity["user_id"]
	action = message.get("type")

	if action == "ready":
		room.set_ready(user_id, bool(message.get("ready", True)))
		await push_room(room)
		return True

	if action == "chat":
		kind = CHAT_KIND_EMOJI if message.get("kind") == CHAT_KIND_EMOJI else CHAT_KIND_TEXT
		text = str(message.get("text") or "").strip()
		if text:
			room.add_chat(user_id, identity["nickname"], text, kind)
			await push_room(room)
		return True

	if action == "start_game":
		if room.host_user_id != user_id:
			raise RoomError("只有房主可以开始游戏")
		room.start_game()
		ensure_ticker()
		await push_room(room)
		return True

	if action == "add_bot":
		if not identity.get("is_admin"):
			raise RoomError("只有管理员可以添加机器人")
		if room.host_user_id != user_id:
			raise RoomError("只有房主可以添加机器人")
		bot_id = room.add_bot()
		bot = room.member(bot_id)
		room.add_chat(None, "系统", f"管理员添加了机器人 {bot['nickname']}")
		await push_room(room)
		return True

	if action == "bot_chat":
		if not identity.get("is_admin"):
			raise RoomError("只有管理员可以触发机器人聊天")
		bot_ids = room.bot_ids()
		if not bot_ids:
			raise RoomError("房间内没有机器人")
		bots.random_chat(room, bot_ids)
		await push_room(room)
		return True

	if action == "remove_bot":
		if not identity.get("is_admin"):
			raise RoomError("只有管理员可以移除机器人")
		if room.host_user_id != user_id:
			raise RoomError("只有房主可以移除机器人")
		bot_id = str(message.get("bot_id") or "").strip()
		bot = room.member(bot_id)
		room.remove_bot(bot_id)
		if bot is not None:
			room.add_chat(None, "系统", f"管理员移除了机器人 {bot['nickname']}")
		await push_room(room)
		return True

	if action == "kick":
		if room.host_user_id != user_id:
			raise RoomError("只有房主可以踢出玩家")
		if room.status != STATUS_WAITING:
			raise RoomError("对局进行中无法踢人")
		target_id = str(message.get("user_id") or "").strip()
		if not target_id or target_id == user_id:
			raise RoomError("无效的踢出目标")
		target = room.member(target_id)
		if target is None:
			raise RoomError("该玩家不在房间内")
		if target.get("is_bot"):
			raise RoomError("请使用移除机器人操作")
		target_nickname = target["nickname"]
		room_manager.leave(target_id)
		await hub.send(target_id, {"type": "notice", "message": "你已被房主移出房间"})
		await push_idle(target_id)
		if room.members:
			room.add_chat(None, "系统", f"房主移出了 {target_nickname}")
			await push_room(room)
		return True

	if action == "next_round":
		if room.host_user_id != user_id:
			raise RoomError("只有房主可以开始下一局")
		if room.engine is None:
			raise RoomError("当前没有对局")
		if room.engine.match_over:
			room.back_to_lobby()
			room.start_game()
		else:
			room.engine.start_round()
		ensure_ticker()
		await push_room(room)
		return True

	if action == "back_to_room":
		if room.host_user_id != user_id:
			raise RoomError("只有房主可以结束对局")
		room.back_to_lobby()
		await push_room(room)
		return True

	engine = room.engine
	if engine is None:
		return False

	if action == "peek_select":
		engine.submit_peek(user_id, list(message.get("slots") or []))
	elif action == "draw":
		engine.action_draw(user_id)
	elif action == "discard":
		engine.action_discard(user_id)
	elif action == "replace":
		engine.action_replace(user_id, message.get("slot"), message.get("slots"))
	elif action == "take_discard":
		engine.action_take_discard(user_id, message.get("slot"), message.get("slots"))
	elif action == "use_special":
		engine.action_use_special(user_id)
	elif action == "special_select":
		engine.special_select(user_id, message.get("target_id"), message.get("slot"))
	elif action == "cancel_special":
		engine.cancel_special(user_id)
	elif action == "call_cabo":
		engine.call_cabo(user_id)
	else:
		return False

	if engine.round_result is not None and engine.match_over:
		record_match_stats(room)
	await push_room(room)
	return True


@router.websocket("/ws")
async def game_socket(websocket: WebSocket) -> None:
	"""Serve one player connection for the whole session.

	Args:
		websocket: Incoming socket.
	"""
	await websocket.accept()
	identity = await authenticate(websocket)
	if identity is None:
		await websocket.close()
		return

	user_id = identity["user_id"]
	previous = await hub.register(user_id, websocket)
	if previous is not None:
		try:
			await previous.close(code=4001)
		except RuntimeError:
			pass

	ensure_ticker()
	await websocket.send_json({"type": "authed", "user": identity})

	room = room_manager.room_of(user_id)
	if room is not None:
		member = room.member(user_id)
		if member is not None:
			member["online"] = True
		if room.engine is not None:
			room.engine.set_online(user_id, True)
		await push_room(room)
	else:
		await push_idle(user_id)

	try:
		while True:
			message = await websocket.receive_json()
			action = message.get("type")

			if action == "ping":
				await websocket.send_json({"type": "pong"})
				continue

			live_room = room_manager.room_of(user_id)
			if live_room is not None:
				live_member = live_room.member(user_id)
				if live_member is not None and not live_member["online"]:
					live_member["online"] = True
					if live_room.engine is not None:
						live_room.engine.set_online(user_id, True)

			if action == "sync":
				current = room_manager.room_of(user_id)
				if current is None:
					await push_idle(user_id)
				else:
					await hub.send(user_id, build_state(current, user_id, []))
				continue

			try:
				handled = await handle_lobby_action(identity, message)
				if not handled:
					current = room_manager.room_of(user_id)
					if current is None:
						raise RoomError("你还没有加入房间")
					handled = await handle_room_action(identity, current, message)
				if not handled:
					await websocket.send_json({"type": "error", "message": "不支持的操作"})
			except (RoomError, GameError) as error:
				await websocket.send_json({"type": "error", "message": str(error)})
	except (WebSocketDisconnect, ValueError, RuntimeError):
		pass
	finally:
		await hub.unregister(user_id, websocket)
		replaced = hub.is_online(user_id)
		current = room_manager.room_of(user_id)
		if current is not None and not replaced:
			member = current.member(user_id)
			if member is not None:
				member["online"] = False
			if current.engine is not None:
				current.engine.set_online(user_id, False)
			await push_room(current)
