"""Random behaviour driver for bot players.

Bots keep their moves intentionally simple: they never use skill cards or take
multi card combos. On their turn they randomly draw, take the discard top,
discard or replace a single slot, and occasionally call SHABO. The driver is
polled by the WebSocket ticker so bot pacing stays independent of the human
turn timer.
"""

import logging
import random
import time
from typing import TYPE_CHECKING
from typing import List

from app.game.engine import GameError
from app.game.engine import Phase
from app.game.engine import Sub
from app.game.room import CHAT_KIND_EMOJI
from app.game.room import CHAT_KIND_TEXT
from app.game.room import EMOJI_KEYS

if TYPE_CHECKING:
	from app.game.engine import GameEngine
	from app.game.engine import PlayerState
	from app.game.room import Room

logger = logging.getLogger(__name__)

BOT_MIN_DELAY = 0.6
BOT_MAX_DELAY = 1.3
TAKE_DISCARD_CHANCE = 0.25
REPLACE_CHANCE = 0.5
CALL_CABO_CHANCE = 0.08

BOT_CHAT_LINES = (
	"稳住，能赢！",
	"这张我要了",
	"别看我的牌～",
	"手气真差",
	"快点吧",
	"再来一局",
	"哈哈哈哈",
	"危险了这波",
)
BOT_CHAT_EMOJI_CHANCE = 0.5


def _filled_slots(player: "PlayerState") -> list:
	"""Return the indexes of the player's non empty hand slots.

	Args:
		player: Bot player state.

	Returns:
		list: Indexes that still hold a card.
	"""
	return [index for index, slot in enumerate(player.hand) if slot.card is not None]


def _play_step(engine: "GameEngine", bot: "PlayerState") -> bool:
	"""Run one random legal action for a bot during the playing phase.

	Args:
		engine: Active game engine.
		bot: Bot player holding the turn.

	Returns:
		bool: ``True`` when an action was performed.
	"""
	if engine.sub == Sub.WAITING_ACTION:
		if (
			engine.phase == Phase.PLAYING_PHASE
			and engine.cabo_caller is None
			and random.random() < CALL_CABO_CHANCE
		):
			engine.call_cabo(bot.user_id)
			return True
		filled = _filled_slots(bot)
		if engine.discard and filled and random.random() < TAKE_DISCARD_CHANCE:
			engine.action_take_discard(bot.user_id, random.choice(filled), None)
			return True
		engine.action_draw(bot.user_id)
		return True

	if engine.sub == Sub.CARD_DRAWN:
		filled = _filled_slots(bot)
		if filled and random.random() < REPLACE_CHANCE:
			engine.action_replace(bot.user_id, random.choice(filled), None)
		else:
			engine.action_discard(bot.user_id)
		return True

	return False


def maybe_act(room: "Room") -> bool:
	"""Let one bot take a single step if it is its turn and the delay elapsed.

	Args:
		room: Room whose engine may contain bots.

	Returns:
		bool: ``True`` when the game state changed and must be broadcast.
	"""
	engine = room.engine
	if engine is None or engine.phase in (Phase.SETTLING, Phase.INITIALIZING):
		return False

	bot_ids = set(room.bot_ids())
	if not bot_ids:
		return False

	now = time.monotonic()
	next_at = getattr(room, "bot_next_act", 0.0)
	if now < next_at:
		return False

	acted = False
	try:
		if engine.phase == Phase.PEEK_PHASE and engine.sub == Sub.PEEK_SELECT:
			peeker = engine.current_peeker()
			if peeker is not None and peeker.user_id in bot_ids:
				slots = random.sample(range(len(peeker.hand)), 2)
				engine.submit_peek(peeker.user_id, slots)
				acted = True
		elif engine.sub in (Sub.WAITING_ACTION, Sub.CARD_DRAWN):
			current = engine.current_player()
			if current is not None and current.user_id in bot_ids:
				acted = _play_step(engine, current)
	except GameError as error:
		logger.info("机器人行动被拒绝（房间 %s）: %s", room.code, error)
		acted = False

	if acted:
		room.bot_next_act = now + random.uniform(BOT_MIN_DELAY, BOT_MAX_DELAY)
	else:
		room.bot_next_act = now + BOT_MIN_DELAY
	return acted


def random_chat(room: "Room", bot_ids: List[str]) -> None:
	"""Make each given bot post one random text or emoji chat line.

	Used by the admin-only test trigger to exercise the chat bubble UI
	without needing several human testers online at once.

	Args:
		room: Room whose chat log receives the messages.
		bot_ids: Bot member identifiers to speak for.
	"""
	for bot_id in bot_ids:
		bot = room.member(bot_id)
		if bot is None or not bot.get("is_bot"):
			continue
		if random.random() < BOT_CHAT_EMOJI_CHANCE:
			room.add_chat(bot_id, bot["nickname"], random.choice(EMOJI_KEYS), CHAT_KIND_EMOJI)
		else:
			room.add_chat(bot_id, bot["nickname"], random.choice(BOT_CHAT_LINES), CHAT_KIND_TEXT)
