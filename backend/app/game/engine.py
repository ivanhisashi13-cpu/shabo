"""Authoritative SHABO game engine.

Implements the house rules: a 54 card deck (two 0 jokers plus 1-13 in four
suits), four opening hand slots, an opening peek of two cards, draw-or-take-from
-discard turns with optional multi card replacement, the skills of 7/8 (self
peek), 9/10 (peek opponent) and 11/12 (blind swap), the SHABO call with its +10
penalty, the kamikaze hand and the accumulation mode that ends at the target
score.
"""

import random
import time
from typing import Dict
from typing import List
from typing import Optional

from app.game.cards import build_deck
from app.game.cards import Card
from app.game.cards import HAND_SIZE
from app.game.cards import INITIAL_PEEK_COUNT
from app.game.cards import label_of
from app.game.cards import SKILL_PEEK_OTHER
from app.game.cards import SKILL_PEEK_SELF
from app.game.cards import SKILL_SWAP

CABO_PENALTY = 10
KAMIKAZE_PENALTY = 50
KAMIKAZE_HAND = (12, 12, 13, 13)
MAX_LOG_ENTRIES = 30
MODE_SINGLE = "SINGLE"
MODE_MULTI = "MULTI"


class GameError(Exception):
	"""Raised when a player attempts an illegal action."""


class Phase:
	"""Game phase constants."""

	INITIALIZING = "INITIALIZING"
	PEEK_PHASE = "PEEK_PHASE"
	PLAYING_PHASE = "PLAYING_PHASE"
	CABO_COUNTDOWN = "CABO_COUNTDOWN"
	SETTLING = "SETTLING"


class Sub:
	"""Turn sub state constants."""

	IDLE = "IDLE"
	PEEK_SELECT = "PEEK_SELECT"
	REVEAL = "REVEAL"
	WAITING_ACTION = "WAITING_ACTION"
	CARD_DRAWN = "CARD_DRAWN"
	SPECIAL = "SPECIAL"


class HandSlot:
	"""One hand slot of a player."""

	__slots__ = ("card", "revealed_to")

	def __init__(self, card: Optional[Card] = None, revealed_to: Optional[set] = None) -> None:
		"""Create a slot.

		Args:
			card: Card placed in the slot, or ``None`` for an empty slot.
			revealed_to: Identifiers of the players that know this card.
		"""
		self.card: Optional[Card] = card
		self.revealed_to: set = set(revealed_to) if revealed_to else set()


class PlayerState:
	"""Per player mutable state inside a game."""

	def __init__(self, user_id: str, nickname: str, avatar: str, seat_index: int) -> None:
		"""Create a player slot.

		Args:
			user_id: Public player identifier.
			nickname: Display name.
			avatar: Avatar key.
			seat_index: Seat order index.
		"""
		self.user_id = user_id
		self.nickname = nickname
		self.avatar = avatar
		self.seat_index = seat_index
		self.hand: List[HandSlot] = [HandSlot() for _ in range(HAND_SIZE)]
		self.total_score = 0
		self.online = True
		self.left = False
		self.peek_done = False
		self.has_called_cabo = False

	def base_score(self) -> int:
		"""Return the sum of the points currently held.

		Returns:
			int: Sum of all occupied slots.
		"""
		return sum(slot.card.point for slot in self.hand if slot.card is not None)

	def hand_values(self) -> List[int]:
		"""Return the values of the occupied slots.

		Returns:
			List[int]: Card values still held.
		"""
		return [slot.card.value for slot in self.hand if slot.card is not None]

	def is_kamikaze(self) -> bool:
		"""Tell whether the hand matches the kamikaze pattern.

		Returns:
			bool: ``True`` when the hand is exactly 12, 12, 13, 13.
		"""
		return tuple(sorted(self.hand_values())) == KAMIKAZE_HAND

	def reset_hand(self) -> None:
		"""Clear every slot before a new round."""
		self.hand = [HandSlot() for _ in range(HAND_SIZE)]
		self.peek_done = False
		self.has_called_cabo = False


class GameEngine:
	"""Multi round SHABO game bound to one room."""

	def __init__(
		self,
		members: List[dict],
		mode: str = MODE_SINGLE,
		turn_timeout: int = 30,
		peek_timeout: int = 15,
		reveal_seconds: int = 3,
		target_score: int = 100,
	) -> None:
		"""Create the engine and its player slots.

		Args:
			members: Ordered room members as ``{user_id, nickname, avatar}``.
			mode: ``SINGLE`` for one round or ``MULTI`` for accumulated rounds.
			turn_timeout: Seconds a player may hold a turn.
			peek_timeout: Seconds allowed for one opening peek turn.
			reveal_seconds: Seconds a revealed card stays face up.
			target_score: Accumulated score that ends a ``MULTI`` match.
		"""
		self.players: List[PlayerState] = [
			PlayerState(item["user_id"], item["nickname"], item["avatar"], index)
			for index, item in enumerate(members)
		]
		self.mode = mode if mode in (MODE_SINGLE, MODE_MULTI) else MODE_SINGLE
		self.turn_timeout = turn_timeout
		self.peek_timeout = peek_timeout
		self.reveal_seconds = reveal_seconds
		self.target_score = target_score

		self.round_number = 0
		self.phase = Phase.INITIALIZING
		self.sub = Sub.IDLE
		self.deck: List[Card] = []
		self.discard: List[Card] = []
		self.current_index = 0
		self.peek_index = 0
		self.drawn_card: Optional[Card] = None
		self.special: Optional[dict] = None
		self.cabo_caller: Optional[str] = None
		self.countdown_remaining: List[str] = []
		self.deadline: float = 0.0
		self.phase_seconds: int = 0
		self.log: List[str] = []
		self.events: List[dict] = []
		self.event_seq = 0
		self.round_result: Optional[dict] = None
		self.match_over = False
		self.winner_user_id: Optional[str] = None

	# ------------------------------------------------------------------ utils

	def player(self, user_id: str) -> Optional[PlayerState]:
		"""Look up a player slot.

		Args:
			user_id: Player identifier.

		Returns:
			Optional[PlayerState]: Matching player, or ``None``.
		"""
		for item in self.players:
			if item.user_id == user_id:
				return item
		return None

	def _require_player(self, user_id: str) -> PlayerState:
		"""Look up a player or fail.

		Args:
			user_id: Player identifier.

		Returns:
			PlayerState: Matching player.

		Raises:
			GameError: When the player is not in this game.
		"""
		found = self.player(user_id)
		if found is None or found.left:
			raise GameError("你不在本局对战中")
		return found

	def active_players(self) -> List[PlayerState]:
		"""Return the players still in the round.

		Returns:
			List[PlayerState]: Players that have not left.
		"""
		return [item for item in self.players if not item.left]

	def current_player(self) -> Optional[PlayerState]:
		"""Return the player holding the turn.

		Returns:
			Optional[PlayerState]: Current player, or ``None``.
		"""
		if not self.players:
			return None
		return self.players[self.current_index % len(self.players)]

	def _emit(self, kind: str, **payload) -> None:
		"""Append an animation event for the clients.

		Args:
			kind: Event kind understood by the frontend.
			payload: Event fields such as ``from``, ``to`` and ``card``.
		"""
		self.event_seq += 1
		event = {"seq": self.event_seq, "kind": kind}
		event.update(payload)
		self.events.append(event)

	def drain_events(self) -> List[dict]:
		"""Return buffered events and clear the buffer.

		Returns:
			List[dict]: Events emitted since the last drain.
		"""
		events = self.events
		self.events = []
		return events

	def _add_log(self, text: str) -> None:
		"""Append a line to the visible action log.

		Args:
			text: Chinese log text.
		"""
		self.log.append(text)
		if len(self.log) > MAX_LOG_ENTRIES:
			self.log = self.log[-MAX_LOG_ENTRIES:]

	def _set_deadline(self, seconds: int) -> None:
		"""Arm the phase timer.

		Args:
			seconds: Seconds from now.
		"""
		self.phase_seconds = seconds
		self.deadline = time.time() + seconds

	@staticmethod
	def _slot_ref(user_id: str, slot_index: int) -> dict:
		"""Build a hand slot anchor reference.

		Args:
			user_id: Slot owner.
			slot_index: Slot position.

		Returns:
			dict: Anchor description for the frontend.
		"""
		return {"zone": "slot", "owner": user_id, "slot": slot_index}

	# ----------------------------------------------------------- round setup

	def start_round(self) -> None:
		"""Shuffle, deal and enter the opening peek phase.

		Raises:
			GameError: When fewer than two players remain.
		"""
		players = self.active_players()
		if len(players) < 2:
			raise GameError("至少需要 2 名玩家才能开始")

		self.round_number += 1
		self.deck = build_deck()
		self.discard = []
		self.drawn_card = None
		self.special = None
		self.cabo_caller = None
		self.countdown_remaining = []
		self.round_result = None
		self.match_over = False
		self.winner_user_id = None
		self.log = []
		self.phase = Phase.INITIALIZING

		for item in players:
			item.reset_hand()

		for slot_index in range(HAND_SIZE):
			for item in players:
				card = self.deck.pop()
				item.hand[slot_index].card = card
				self._emit(
					"deal",
					to=self._slot_ref(item.user_id, slot_index),
					visible_to=[],
				)

		first_card = self.deck.pop()
		self.discard.append(first_card)
		self._emit(
			"move",
			source={"zone": "deck"},
			to={"zone": "discard"},
			card=first_card.to_dict(),
			visible_to="all",
		)

		self.current_index = self.players.index(random.choice(players))
		self.phase = Phase.PEEK_PHASE
		self.peek_index = 0
		self._add_log(f"第 {self.round_number} 局开始，{self.current_player().nickname} 先手")
		self._begin_peek_turn()

	def peek_order(self) -> List[PlayerState]:
		"""Return the peek order starting from the first acting player.

		Returns:
			List[PlayerState]: Players in peek order.
		"""
		players = self.active_players()
		if not players:
			return []
		start = self.current_player()
		if start is None or start.left:
			return players
		offset = players.index(start)
		return players[offset:] + players[:offset]

	def current_peeker(self) -> Optional[PlayerState]:
		"""Return the player expected to submit an opening peek.

		Returns:
			Optional[PlayerState]: Current peeker, or ``None``.
		"""
		order = self.peek_order()
		if self.peek_index >= len(order):
			return None
		return order[self.peek_index]

	def _begin_peek_turn(self) -> None:
		"""Start the peek turn of the next player, auto resolving offline ones."""
		while True:
			peeker = self.current_peeker()
			if peeker is None:
				self._begin_playing()
				return
			if peeker.peek_done:
				self.peek_index += 1
				continue
			self.sub = Sub.PEEK_SELECT
			self._set_deadline(self.peek_timeout)
			if not peeker.online:
				self._auto_peek(peeker)
				return
			return

	def _auto_peek(self, peeker: PlayerState) -> None:
		"""Pick two random slots for a player who cannot act.

		Args:
			peeker: Player to resolve.
		"""
		candidates = [index for index in range(len(peeker.hand)) if peeker.user_id not in peeker.hand[index].revealed_to]
		if len(candidates) < INITIAL_PEEK_COUNT:
			candidates = list(range(len(peeker.hand)))
		slots = random.sample(candidates, INITIAL_PEEK_COUNT)
		self._apply_peek(peeker, slots, auto=True)

	def _apply_peek(self, peeker: PlayerState, slots: List[int], auto: bool = False) -> None:
		"""Reveal the chosen opening cards to their owner.

		Args:
			peeker: Player performing the peek.
			slots: Two slot indexes.
			auto: Whether the server picked the slots.
		"""
		for slot_index in slots:
			slot = peeker.hand[slot_index]
			slot.revealed_to.add(peeker.user_id)
			self._emit(
				"reveal",
				owner=peeker.user_id,
				slot=slot_index,
				card=slot.card.to_dict() if slot.card else None,
				visible_to=[peeker.user_id],
				seconds=self.reveal_seconds,
			)
			self._emit(
				"peek",
				viewer=peeker.user_id,
				owner=peeker.user_id,
				slot=slot_index,
				visible_to="all",
				seconds=self.reveal_seconds,
			)
		peeker.peek_done = True
		self.sub = Sub.REVEAL
		self._set_deadline(self.reveal_seconds)
		suffix = "（超时随机）" if auto else ""
		self._add_log(f"{peeker.nickname} 查看了 2 张手牌{suffix}")

	def submit_peek(self, user_id: str, slots: List[int]) -> None:
		"""Handle the opening peek submission of a player.

		Args:
			user_id: Acting player.
			slots: Exactly two distinct slot indexes.

		Raises:
			GameError: When the submission is not legal right now.
		"""
		player = self._require_player(user_id)
		if self.phase != Phase.PEEK_PHASE or self.sub != Sub.PEEK_SELECT:
			raise GameError("当前不是偷看阶段")
		peeker = self.current_peeker()
		if peeker is None or peeker.user_id != user_id:
			raise GameError("还没轮到你偷看")
		unique = sorted(set(int(value) for value in slots))
		if len(unique) != INITIAL_PEEK_COUNT or any(value < 0 or value >= len(player.hand) for value in unique):
			raise GameError("请选择 2 张不同的手牌")
		self._apply_peek(player, unique)

	def _begin_playing(self) -> None:
		"""Leave the peek phase and start the first real turn."""
		self.phase = Phase.PLAYING_PHASE
		self._begin_turn()

	# ------------------------------------------------------------- turn flow

	def _begin_turn(self) -> None:
		"""Open a fresh turn for the current player."""
		if not self.deck:
			self._add_log("牌堆已抽完，直接进入结算（无人喊 SHABO）")
			self._settle()
			return
		self.drawn_card = None
		self.special = None
		self.sub = Sub.WAITING_ACTION
		self._set_deadline(self.turn_timeout)
		player = self.current_player()
		if player is not None:
			self._emit("turn", actor=player.user_id, visible_to="all")

	def _next_active_index(self, from_index: int) -> int:
		"""Find the next seat that can act, strictly in seat order.

		Offline players keep their turn so the order never changes; their turn
		is auto resolved by :meth:`tick` when the timer expires.

		Args:
			from_index: Seat index to start searching after.

		Returns:
			int: Seat index of the next player.
		"""
		count = len(self.players)
		for step in range(1, count + 1):
			index = (from_index + step) % count
			if not self.players[index].left:
				return index
		return from_index

	def _end_turn(self) -> None:
		"""Close the current turn and hand over to the next player."""
		self.drawn_card = None
		self.special = None

		if self.phase == Phase.CABO_COUNTDOWN:
			current = self.current_player()
			if current is not None and current.user_id in self.countdown_remaining:
				self.countdown_remaining.remove(current.user_id)
			self.countdown_remaining = [
				user_id for user_id in self.countdown_remaining
				if (self.player(user_id) is not None and not self.player(user_id).left)
			]
			if not self.countdown_remaining:
				self._settle()
				return
			next_id = self.countdown_remaining[0]
			self.current_index = self.players.index(self.player(next_id))
			self._begin_turn()
			return

		if len(self.active_players()) < 2:
			self._settle()
			return

		self.current_index = self._next_active_index(self.current_index)
		self._begin_turn()

	def _ensure_deck(self) -> None:
		"""Deck is never reshuffled: once drawn out the round goes to settlement."""
		return

	def _check_turn(self, user_id: str, expected_sub: str) -> PlayerState:
		"""Validate that a player may act in the expected sub state.

		Args:
			user_id: Acting player.
			expected_sub: Required sub state.

		Returns:
			PlayerState: The acting player.

		Raises:
			GameError: When it is not this player's turn or the state differs.
		"""
		player = self._require_player(user_id)
		if self.phase not in (Phase.PLAYING_PHASE, Phase.CABO_COUNTDOWN):
			raise GameError("当前阶段无法执行该操作")
		current = self.current_player()
		if current is None or current.user_id != user_id:
			raise GameError("还没轮到你行动")
		if self.sub != expected_sub:
			raise GameError("当前状态无法执行该操作")
		return player

	def action_draw(self, user_id: str) -> None:
		"""Draw the top card of the deck.

		Args:
			user_id: Acting player.

		Raises:
			GameError: When drawing is not allowed right now.
		"""
		player = self._check_turn(user_id, Sub.WAITING_ACTION)
		self._ensure_deck()
		if not self.deck:
			raise GameError("牌堆已空")
		self.drawn_card = self.deck.pop()
		self.sub = Sub.CARD_DRAWN
		self._emit(
			"move",
			source={"zone": "deck"},
			to={"zone": "drawn"},
			card=self.drawn_card.to_dict(),
			visible_to=[user_id],
		)
		self._add_log(f"{player.nickname} 从牌堆摸了一张牌")

	def action_discard(self, user_id: str) -> None:
		"""Discard the drawn card without using it.

		Args:
			user_id: Acting player.

		Raises:
			GameError: When no card is pending.
		"""
		player = self._check_turn(user_id, Sub.CARD_DRAWN)
		card = self.drawn_card
		self.discard.append(card)
		self._emit(
			"move",
			source={"zone": "drawn"},
			to={"zone": "discard"},
			card=card.to_dict(),
			visible_to="all",
		)
		self._add_log(f"{player.nickname} 弃掉了 {self._card_label(card)}")
		self._end_turn()

	def _normalize_slots(self, player: PlayerState, raw) -> List[int]:
		"""Validate a slot selection coming from a client.

		Args:
			player: Owner of the slots.
			raw: Either one index or a list of indexes.

		Returns:
			List[int]: Unique indexes in the order the player picked them.

		Raises:
			GameError: When the selection is empty or points at empty slots.
		"""
		if raw is None:
			raise GameError("请选择要替换的手牌")
		values = raw if isinstance(raw, (list, tuple)) else [raw]
		picked: List[int] = []
		for item in values:
			try:
				index = int(item)
			except (TypeError, ValueError) as error:
				raise GameError("手牌位置不合法") from error
			if not 0 <= index < len(player.hand):
				raise GameError("手牌位置不合法")
			if player.hand[index].card is None:
				raise GameError("该手牌位置是空的")
			if index not in picked:
				picked.append(index)
		if not picked:
			raise GameError("请选择要替换的手牌")
		return picked

	def _place_card(self, player: PlayerState, card: Card, targets: List[int],
		source: dict, public: bool) -> None:
		"""Put an incoming card into the hand, honouring the multi card rule.

		One selected slot behaves like a plain replacement. Several selected
		slots are turned face up for everybody: matching values are all
		discarded at once, mismatching values keep the cards and force the
		player to also take the incoming card plus ``len(targets) - 2`` penalty
		cards from the deck.

		Args:
			player: Acting player.
			card: Incoming card from the deck or from the discard pile.
			targets: Validated slot indexes.
			source: Anchor of the incoming card for the animations.
			public: Whether the incoming card is known by everybody.
		"""
		audience = {item.user_id for item in self.active_players()}
		owner_visibility = set(audience) if public else {player.user_id}

		if len(targets) == 1:
			index = targets[0]
			slot = player.hand[index]
			old_card = slot.card
			slot.card = card
			slot.revealed_to = set(owner_visibility)
			self.discard.append(old_card)
			self._emit(
				"move",
				source=source,
				to=self._slot_ref(player.user_id, index),
				card=card.to_dict(),
				visible_to="all" if public else [player.user_id],
			)
			self._emit(
				"move",
				source=self._slot_ref(player.user_id, index),
				to={"zone": "discard"},
				card=old_card.to_dict(),
				visible_to="all",
			)
			self._add_log(
				f"{player.nickname} 换掉了第 {index + 1} 张手牌，弃出 {self._card_label(old_card)}"
			)
			return

		values = [player.hand[index].card.value for index in targets]
		for index in targets:
			slot = player.hand[index]
			slot.revealed_to = set(audience)
			self._emit(
				"reveal",
				owner=player.user_id,
				slot=index,
				card=slot.card.to_dict(),
				visible_to="all",
				seconds=self.reveal_seconds,
			)

		shown = "、".join(self._card_label(player.hand[index].card) for index in targets)
		if len(set(values)) == 1:
			first = targets[0]
			for index in targets:
				slot = player.hand[index]
				old_card = slot.card
				slot.card = None
				slot.revealed_to = set()
				self.discard.append(old_card)
				self._emit(
					"move",
					source=self._slot_ref(player.user_id, index),
					to={"zone": "discard"},
					card=old_card.to_dict(),
					visible_to="all",
				)
			player.hand[first].card = card
			player.hand[first].revealed_to = set(owner_visibility)
			self._emit(
				"move",
				source=source,
				to=self._slot_ref(player.user_id, first),
				card=card.to_dict(),
				visible_to="all" if public else [player.user_id],
			)
			self._add_log(
				f"{player.nickname} 亮出 {shown}，点数相同，{len(targets)} 张一次换成 1 张，"
				f"手牌剩 {len(player.hand_values())} 张"
			)
			return

		new_index = len(player.hand)
		player.hand.append(HandSlot(card, owner_visibility))
		self._emit(
			"move",
			source=source,
			to=self._slot_ref(player.user_id, new_index),
			card=card.to_dict(),
			visible_to="all" if public else [player.user_id],
		)

		extra = 0
		for _ in range(max(0, len(targets) - 2)):
			self._ensure_deck()
			if not self.deck:
				break
			penalty_card = self.deck.pop()
			penalty_index = len(player.hand)
			player.hand.append(HandSlot(penalty_card))
			self._emit(
				"move",
				source={"zone": "deck"},
				to=self._slot_ref(player.user_id, penalty_index),
				card=penalty_card.to_dict(),
				visible_to=[],
			)
			extra += 1

		suffix = f"，并额外摸了 {extra} 张罚牌" if extra else ""
		self._add_log(
			f"{player.nickname} 亮出 {shown}，点数不同，只能把这张牌收进手牌{suffix}，"
			f"手牌变成 {len(player.hand_values())} 张"
		)

	def action_replace(self, user_id: str, slot_index=None, slots=None) -> None:
		"""Replace one or several hand cards with the drawn card.

		Args:
			user_id: Acting player.
			slot_index: Single slot index kept for compatibility.
			slots: Slot indexes chosen by the player.

		Raises:
			GameError: When the selection is invalid or no card is pending.
		"""
		player = self._check_turn(user_id, Sub.CARD_DRAWN)
		targets = self._normalize_slots(player, slots if slots is not None else slot_index)
		card = self.drawn_card
		self.drawn_card = None
		self._place_card(player, card, targets, {"zone": "drawn"}, public=False)
		self._end_turn()

	def action_take_discard(self, user_id: str, slot_index=None, slots=None) -> None:
		"""Take the discard top and swap it into one or several hand slots.

		The taken card is public, so every player learns that slot. Skills are
		never triggered by a card taken from the discard pile.

		Args:
			user_id: Acting player.
			slot_index: Single slot index kept for compatibility.
			slots: Slot indexes chosen by the player.

		Raises:
			GameError: When the pile is empty or the selection is invalid.
		"""
		player = self._check_turn(user_id, Sub.WAITING_ACTION)
		if not self.discard:
			raise GameError("弃牌堆是空的")
		targets = self._normalize_slots(player, slots if slots is not None else slot_index)
		taken = self.discard.pop()
		self._add_log(f"{player.nickname} 从弃牌堆拿走 {self._card_label(taken)}")
		self._place_card(player, taken, targets, {"zone": "discard"}, public=True)
		self._end_turn()

	# --------------------------------------------------------- special cards

	def action_use_special(self, user_id: str) -> None:
		"""Start the special effect flow of the drawn card.

		Args:
			user_id: Acting player.

		Raises:
			GameError: When the drawn card has no special effect.
		"""
		self._check_turn(user_id, Sub.CARD_DRAWN)
		card = self.drawn_card
		if card is None or not card.is_special:
			raise GameError("这张牌没有特殊效果")

		self.special = {
			"point": card.point,
			"skill": card.skill,
			"steps": self._special_steps(card.skill, user_id),
			"index": 0,
			"picks": {},
		}
		self.sub = Sub.SPECIAL
		self._autofill_special(user_id)

	def _special_steps(self, skill: str, user_id: str) -> List[dict]:
		"""Build the ordered selection steps of a skill.

		Args:
			skill: One of the ``SKILL_*`` constants.
			user_id: Acting player.

		Returns:
			List[dict]: Step descriptors.
		"""
		if skill == SKILL_PEEK_SELF:
			return [{"kind": "own_slot", "key": "slot_a", "prompt": "选择你要查看的 1 张手牌"}]
		if skill == SKILL_PEEK_OTHER:
			return [
				{"kind": "any_foe_slot", "key": "slot_b", "prompt": "选择要查看的对方 1 张手牌"},
			]
		return [
			{"kind": "swap_pick", "prompt": "点选你的 1 张牌和任意对手的 1 张牌进行交换"},
		]

	def _step_candidates(self, step: dict, user_id: str) -> List[str]:
		"""Return the legal player choices of a selection step.

		Args:
			step: Step descriptor.
			user_id: Acting player.

		Returns:
			List[str]: Candidate player identifiers.
		"""
		picks = self.special["picks"] if self.special else {}
		excluded = set()
		if step.get("exclude_self"):
			excluded.add(user_id)
		if step.get("exclude_key") and picks.get(step["exclude_key"]):
			excluded.add(picks[step["exclude_key"]])
		return [item.user_id for item in self.active_players() if item.user_id not in excluded]

	def _autofill_special(self, user_id: str) -> None:
		"""Skip selection steps that have a single legal answer."""
		while self.special is not None and self.special["index"] < len(self.special["steps"]):
			step = self.special["steps"][self.special["index"]]
			if step["kind"] != "player":
				return
			candidates = self._step_candidates(step, user_id)
			if len(candidates) != 1:
				return
			self.special["picks"][step["key"]] = candidates[0]
			self.special["index"] += 1
		if self.special is not None:
			self._resolve_special(user_id)

	def special_select(self, user_id: str, target_id: Optional[str] = None,
		slot_index: Optional[int] = None) -> None:
		"""Submit one selection step of the special effect flow.

		Args:
			user_id: Acting player.
			target_id: Chosen player for ``player`` steps.
			slot_index: Chosen slot for slot steps.

		Raises:
			GameError: When the selection does not match the pending step.
		"""
		player = self._check_turn(user_id, Sub.SPECIAL)
		if self.special is None:
			raise GameError("当前没有待处理的特效")

		step = self.special["steps"][self.special["index"]]
		if step["kind"] == "swap_pick":
			if target_id and target_id != user_id:
				owner = self.player(target_id)
				if owner is None or owner.left:
					raise GameError("该手牌不可选择")
				if slot_index is None:
					raise GameError("请选择一张手牌")
				slot_index = int(slot_index)
				if not 0 <= slot_index < len(owner.hand) or owner.hand[slot_index].card is None:
					raise GameError("该手牌不可选择")
				self.special["picks"]["target"] = target_id
				self.special["picks"]["slot_b"] = slot_index
			else:
				if slot_index is None:
					raise GameError("请选择一张手牌")
				slot_index = int(slot_index)
				if not 0 <= slot_index < len(player.hand) or player.hand[slot_index].card is None:
					raise GameError("该手牌不可选择")
				self.special["picks"]["slot_a"] = slot_index
			picks = self.special["picks"]
			if "slot_a" in picks and "target" in picks and "slot_b" in picks:
				self.special["index"] += 1
				self._autofill_special(user_id)
			return
		if step["kind"] == "player":
			if not target_id or target_id not in self._step_candidates(step, user_id):
				raise GameError("目标玩家不合法")
			self.special["picks"][step["key"]] = target_id
		elif step["kind"] == "any_foe_slot":
			if not target_id or target_id == user_id:
				raise GameError("请选择其他玩家的手牌")
			owner = self.player(target_id)
			if owner is None or owner.left:
				raise GameError("该手牌不可选择")
			if slot_index is None:
				raise GameError("请选择一张手牌")
			slot_index = int(slot_index)
			if not 0 <= slot_index < len(owner.hand):
				raise GameError("手牌位置不合法")
			if owner.hand[slot_index].card is None:
				raise GameError("该手牌不可选择")
			self.special["picks"]["target"] = target_id
			self.special["picks"][step["key"]] = slot_index
		else:
			if slot_index is None:
				raise GameError("请选择一张手牌")
			slot_index = int(slot_index)
			owner_id = user_id if step["kind"] == "own_slot" else self.special["picks"].get(step["owner_key"])
			owner = self.player(owner_id) if owner_id else None
			if owner is None or owner.left:
				raise GameError("该手牌不可选择")
			if not 0 <= slot_index < len(owner.hand):
				raise GameError("手牌位置不合法")
			if owner.hand[slot_index].card is None:
				raise GameError("该手牌不可选择")
			self.special["picks"][step["key"]] = slot_index

		self.special["index"] += 1
		self._autofill_special(user_id)

	def cancel_special(self, user_id: str) -> None:
		"""Abort the special flow and return to the post draw options.

		Args:
			user_id: Acting player.

		Raises:
			GameError: When no special flow is running.
		"""
		self._check_turn(user_id, Sub.SPECIAL)
		self.special = None
		self.sub = Sub.CARD_DRAWN

	def _resolve_special(self, user_id: str) -> None:
		"""Apply the finished special effect and close the turn.

		Args:
			user_id: Acting player.
		"""
		player = self._require_player(user_id)
		picks = self.special["picks"]
		skill = self.special["skill"]
		card = self.drawn_card
		self.special = None

		if card is not None:
			self.discard.append(card)
			self._emit(
				"move",
				source={"zone": "drawn"},
				to={"zone": "discard"},
				card=card.to_dict(),
				visible_to="all",
			)
		self.drawn_card = None

		if skill == SKILL_PEEK_SELF:
			self._reveal_to(player, player, picks["slot_a"], "自己")
			return
		if skill == SKILL_PEEK_OTHER:
			target = self.player(picks["target"])
			self._reveal_to(player, target, picks["slot_b"], target.nickname)
			return

		target = self.player(picks["target"])
		self._swap_slots(player, picks["slot_a"], target, picks["slot_b"])
		self._add_log(f"{player.nickname} 与 {target.nickname} 盲换了 1 张手牌")
		self._end_turn()

	def _reveal_to(self, viewer: PlayerState, owner: PlayerState, slot_index: int,
		owner_label: str) -> None:
		"""Show one card to a single player for the reveal window.

		Args:
			viewer: Player allowed to see the card.
			owner: Owner of the card.
			slot_index: Slot position.
			owner_label: Name used in the log line.
		"""
		slot = owner.hand[slot_index]
		slot.revealed_to.add(viewer.user_id)
		self._emit(
			"reveal",
			owner=owner.user_id,
			slot=slot_index,
			card=slot.card.to_dict() if slot.card else None,
			visible_to=[viewer.user_id],
			seconds=self.reveal_seconds,
		)
		if viewer.user_id != owner.user_id:
			self._emit(
				"peek",
				viewer=viewer.user_id,
				owner=owner.user_id,
				slot=slot_index,
				visible_to="all",
				seconds=self.reveal_seconds,
			)
		self.sub = Sub.REVEAL
		self._set_deadline(self.reveal_seconds)
		self._add_log(f"{viewer.nickname} 查看了 {owner_label} 的 1 张手牌")

	def _swap_slots(self, first: PlayerState, first_slot: int, second: PlayerState,
		second_slot: int) -> None:
		"""Exchange two hand cards keeping their visibility.

		Args:
			first: First owner.
			first_slot: Slot index of the first owner.
			second: Second owner.
			second_slot: Slot index of the second owner.
		"""
		slot_a = first.hand[first_slot]
		slot_b = second.hand[second_slot]
		slot_a.card, slot_b.card = slot_b.card, slot_a.card
		slot_a.revealed_to, slot_b.revealed_to = slot_b.revealed_to, slot_a.revealed_to
		self._emit(
			"swap",
			a=self._slot_ref(first.user_id, first_slot),
			b=self._slot_ref(second.user_id, second_slot),
			visible_to="all",
		)

	# ------------------------------------------------------------ cabo & end

	def call_cabo(self, user_id: str) -> None:
		"""Declare CABO and start the final round of turns.

		Args:
			user_id: Acting player.

		Raises:
			GameError: When calling is not allowed right now.
		"""
		player = self._check_turn(user_id, Sub.WAITING_ACTION)
		if self.phase != Phase.PLAYING_PHASE:
			raise GameError("本局已经有人呼叫过 SHABO")
		if self.cabo_caller is not None:
			raise GameError("本局已经有人呼叫过 SHABO")

		self.cabo_caller = user_id
		player.has_called_cabo = True
		self.phase = Phase.CABO_COUNTDOWN

		others = [item for item in self.active_players() if item.user_id != user_id]
		order = sorted(others, key=lambda item: (item.seat_index - player.seat_index) % len(self.players))
		self.countdown_remaining = [item.user_id for item in order]

		self._emit("cabo", actor=user_id, visible_to="all")
		self._add_log(f"{player.nickname} 呼叫了 SHABO！其余玩家各行动最后一回合")
		self._end_turn()

	def _settle(self) -> None:
		"""Compute the round result and update the accumulated scores."""
		self.phase = Phase.SETTLING
		self.sub = Sub.IDLE
		self.drawn_card = None
		self.special = None
		self.deadline = 0.0
		self.phase_seconds = 0

		players = self.active_players()
		rows = []
		base_scores = {item.user_id: item.base_score() for item in players}
		lowest = min(base_scores.values()) if base_scores else 0
		kamikaze_ids = [item.user_id for item in players if item.is_kamikaze()]
		kamikaze_penalty = KAMIKAZE_PENALTY * len(kamikaze_ids)

		if kamikaze_ids:
			names = "、".join(self.player(user_id).nickname for user_id in kamikaze_ids)
			self._add_log(f"神风翻盘！{names} 本局 0 分，其余玩家各 +{kamikaze_penalty} 分")

		for item in players:
			base = base_scores[item.user_id]
			if kamikaze_ids:
				penalty = 0 if item.user_id in kamikaze_ids else kamikaze_penalty
				final = 0 if item.user_id in kamikaze_ids else base + penalty
			elif item.user_id == self.cabo_caller:
				if base > lowest:
					penalty = CABO_PENALTY
					final = base + penalty
				else:
					penalty = 0
					final = 0
			else:
				penalty = 0
				final = base
			item.total_score += final
			rows.append({
				"user_id": item.user_id,
				"nickname": item.nickname,
				"avatar": item.avatar,
				"cards": [slot.card.to_dict() for slot in item.hand if slot.card is not None],
				"base_score": base,
				"penalty": penalty,
				"final_score": final,
				"total_score": item.total_score,
				"is_caller": item.user_id == self.cabo_caller,
				"kamikaze": item.user_id in kamikaze_ids,
			})

		if not kamikaze_ids and self.cabo_caller is not None:
			caller = self.player(self.cabo_caller)
			caller_base = base_scores.get(self.cabo_caller, 0)
			if caller_base > lowest:
				self._add_log(f"{caller.nickname} 喊了 SHABO 但不是最低分，本局 +{CABO_PENALTY} 分")
			else:
				self._add_log(f"{caller.nickname} 喊了 SHABO 且是最低分，本局记 0 分")

		rows.sort(key=lambda row: row["final_score"])
		rank = 0
		previous = None
		for index, row in enumerate(rows):
			if previous is None or row["final_score"] != previous:
				rank = index + 1
				previous = row["final_score"]
			row["rank"] = rank

		if self.mode == MODE_MULTI:
			self.match_over = any(item.total_score >= self.target_score for item in players)
			if self.match_over:
				best = min(players, key=lambda item: item.total_score)
				self.winner_user_id = best.user_id
		else:
			self.match_over = True
			self.winner_user_id = rows[0]["user_id"] if rows else None

		shabo_user_id = None
		if self.match_over and players:
			worst = max(players, key=lambda item: item.total_score)
			shabo_user_id = worst.user_id
			self._add_log(f"整场结束！本场傻波儿是 {worst.nickname}（总分 {worst.total_score}）")

		self.round_result = {
			"round": self.round_number,
			"cabo_caller": self.cabo_caller,
			"players": rows,
			"kamikaze": kamikaze_ids,
			"match_over": self.match_over,
			"winner_user_id": self.winner_user_id,
			"shabo_user_id": shabo_user_id,
			"mode": self.mode,
			"target_score": self.target_score,
		}
		self._add_log("本局结算完成")
		self._emit("settle", visible_to="all")

	# -------------------------------------------------------------- lifecycle

	def set_online(self, user_id: str, online: bool) -> None:
		"""Update the connection flag of a player.

		Args:
			user_id: Player identifier.
			online: Whether the socket is alive.
		"""
		player = self.player(user_id)
		if player is None:
			return
		player.online = online
		if online:
			return
		if self.phase == Phase.PEEK_PHASE and self.sub == Sub.PEEK_SELECT:
			peeker = self.current_peeker()
			if peeker is not None and peeker.user_id == user_id:
				self._auto_peek(peeker)

	def player_left(self, user_id: str) -> None:
		"""Remove a player from the running round.

		Args:
			user_id: Player identifier.
		"""
		player = self.player(user_id)
		if player is None or player.left:
			return
		player.left = True
		player.online = False
		for slot in player.hand:
			slot.card = None
		self._add_log(f"{player.nickname} 离开了对局")

		if user_id in self.countdown_remaining:
			self.countdown_remaining.remove(user_id)

		if self.phase in (Phase.SETTLING, Phase.INITIALIZING):
			return

		if len(self.active_players()) < 2:
			self._settle()
			return

		if self.phase == Phase.PEEK_PHASE:
			if self.current_peeker() is None or self.current_peeker().user_id == user_id:
				self.peek_index += 1
				self._begin_peek_turn()
			return

		current = self.current_player()
		if current is not None and current.user_id == user_id:
			self._end_turn()

	def tick(self, now: Optional[float] = None) -> bool:
		"""Advance timers and auto resolve timeouts.

		Args:
			now: Current epoch seconds, defaults to ``time.time()``.

		Returns:
			bool: ``True`` when the state changed and must be broadcast.
		"""
		now = now if now is not None else time.time()
		if self.phase in (Phase.SETTLING, Phase.INITIALIZING):
			return False
		if not self.deadline or now < self.deadline:
			return False

		if self.phase == Phase.PEEK_PHASE:
			if self.sub == Sub.PEEK_SELECT:
				peeker = self.current_peeker()
				if peeker is None:
					self._begin_playing()
					return True
				self._auto_peek(peeker)
				return True
			self.peek_index += 1
			self._begin_peek_turn()
			return True

		if self.sub == Sub.REVEAL:
			self._end_turn()
			return True

		current = self.current_player()
		if current is None:
			return False

		if self.sub == Sub.SPECIAL:
			self.special = None
			self.sub = Sub.CARD_DRAWN
		if self.sub == Sub.WAITING_ACTION:
			self._ensure_deck()
			if self.deck:
				self.drawn_card = self.deck.pop()
				self.sub = Sub.CARD_DRAWN
				self._emit(
					"move",
					source={"zone": "deck"},
					to={"zone": "drawn"},
					card=self.drawn_card.to_dict(),
					visible_to=[current.user_id],
				)
		if self.sub == Sub.CARD_DRAWN and self.drawn_card is not None:
			card = self.drawn_card
			self.discard.append(card)
			self._emit(
				"move",
				source={"zone": "drawn"},
				to={"zone": "discard"},
				card=card.to_dict(),
				visible_to="all",
			)
			self._add_log(f"{current.nickname} 回合超时，系统自动摸牌并弃牌")
			self._end_turn()
			return True

		self._add_log(f"{current.nickname} 回合超时")
		self._end_turn()
		return True

	# ------------------------------------------------------------ serializing

	@staticmethod
	def _card_label(card: Optional[Card]) -> str:
		"""Return a short readable card label.

		Args:
			card: Card to describe.

		Returns:
			str: Label such as ``黑桃K(13分)``.
		"""
		if card is None:
			return "空"
		suit_names = {"spade": "黑桃", "heart": "红心", "club": "梅花", "diamond": "方块", "joker": "王牌"}
		return f"{suit_names.get(card.suit, '')}{label_of(card.value)}({card.point}分)"

	def _hand_view(self, owner: PlayerState, viewer_id: str) -> List[dict]:
		"""Serialize one hand for a specific viewer.

		Args:
			owner: Hand owner.
			viewer_id: Player receiving the snapshot.

		Returns:
			List[dict]: Slot descriptions with hidden cards stripped.
		"""
		view = []
		audience = {item.user_id for item in self.active_players()}
		for index, slot in enumerate(owner.hand):
			known = slot.card is not None and viewer_id in slot.revealed_to
			public = slot.card is not None and audience.issubset(slot.revealed_to)
			view.append({
				"slot": index,
				"has_card": slot.card is not None,
				"known": known,
				"public": public,
				"card": slot.card.to_dict() if known and slot.card else None,
			})
		return view

	def _special_view(self, viewer_id: str) -> Optional[dict]:
		"""Serialize the pending special selection for its owner.

		Args:
			viewer_id: Player receiving the snapshot.

		Returns:
			Optional[dict]: Step descriptor, or ``None``.
		"""
		current = self.current_player()
		if self.special is None or current is None:
			return None
		if current.user_id != viewer_id:
			return {
				"point": self.special["point"],
				"skill": self.special["skill"],
				"step_index": self.special["index"],
				"step_total": len(self.special["steps"]),
				"prompt": "",
				"kind": "",
				"candidates": [],
				"owner": None,
				"picks": {},
			}
		step = self.special["steps"][self.special["index"]]
		owner = viewer_id if step["kind"] == "own_slot" else self.special["picks"].get(step.get("owner_key", ""))
		if step["kind"] == "player":
			candidates = self._step_candidates(step, viewer_id)
		elif step["kind"] in ("any_foe_slot", "swap_pick"):
			candidates = [item.user_id for item in self.active_players() if item.user_id != viewer_id]
		else:
			candidates = []
		return {
			"point": self.special["point"],
			"skill": self.special["skill"],
			"step_index": self.special["index"],
			"step_total": len(self.special["steps"]),
			"prompt": step["prompt"],
			"kind": step["kind"],
			"candidates": candidates,
			"owner": owner,
			"picks": dict(self.special["picks"]),
		}

	def snapshot_for(self, viewer_id: str) -> dict:
		"""Build the complete game state for one player.

		Args:
			viewer_id: Player receiving the snapshot.

		Returns:
			dict: Authoritative state with private data filtered out.
		"""
		current = self.current_player()
		discard_top = self.discard[-1] if self.discard else None
		is_viewer_turn = current is not None and current.user_id == viewer_id
		peeker = self.current_peeker() if self.phase == Phase.PEEK_PHASE else None

		return {
			"round": self.round_number,
			"mode": self.mode,
			"target_score": self.target_score,
			"phase": self.phase,
			"sub": self.sub,
			"turn_user_id": current.user_id if current else None,
			"peek_user_id": peeker.user_id if peeker else None,
			"deadline_ms": int(self.deadline * 1000) if self.deadline else 0,
			"phase_seconds": self.phase_seconds,
			"deck_count": len(self.deck),
			"discard_count": len(self.discard),
			"discard_top": discard_top.to_dict() if discard_top else None,
			"drawn_card": self.drawn_card.to_dict() if (self.drawn_card and is_viewer_turn) else None,
			"has_drawn_card": self.drawn_card is not None,
			"cabo_caller": self.cabo_caller,
			"countdown_remaining": list(self.countdown_remaining),
			"special": self._special_view(viewer_id),
			"players": [
				{
					"user_id": item.user_id,
					"nickname": item.nickname,
					"avatar": item.avatar,
					"seat_index": item.seat_index,
					"online": item.online,
					"left": item.left,
					"total_score": item.total_score,
					"peek_done": item.peek_done,
					"has_called_cabo": item.has_called_cabo,
					"hand": self._hand_view(item, viewer_id),
				}
				for item in self.players
			],
			"round_result": self.round_result,
			"match_over": self.match_over,
			"winner_user_id": self.winner_user_id,
			"log": list(self.log[-12:]),
		}
