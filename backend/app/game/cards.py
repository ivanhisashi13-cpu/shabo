"""Card pool definition for SHABO (54 cards: two 0 jokers plus 1-13 in four suits)."""

import random
from typing import Dict
from typing import List

SUITS = ("spade", "heart", "club", "diamond")

SKILL_NONE = "none"
SKILL_PEEK_SELF = "peek_self"
SKILL_PEEK_OTHER = "peek_other"
SKILL_SWAP = "swap"

SKILL_LABELS: Dict[str, str] = {
	SKILL_NONE: "",
	SKILL_PEEK_SELF: "自窥",
	SKILL_PEEK_OTHER: "窥敌",
	SKILL_SWAP: "换牌",
}

JOKER_COUNT = 2
MAX_VALUE = 13
HAND_SIZE = 4
INITIAL_PEEK_COUNT = 2

VALUE_LABELS: Dict[int, str] = {0: "0", 1: "A", 11: "J", 12: "Q", 13: "K"}


def skill_of(value: int) -> str:
	"""Return the skill carried by a card value.

	Args:
		value: Card value between 0 and 13.

	Returns:
		str: One of the ``SKILL_*`` constants.
	"""
	if value in (7, 8):
		return SKILL_PEEK_SELF
	if value in (9, 10):
		return SKILL_PEEK_OTHER
	if value in (11, 12):
		return SKILL_SWAP
	return SKILL_NONE


def label_of(value: int) -> str:
	"""Return the short face label of a card value.

	Args:
		value: Card value between 0 and 13.

	Returns:
		str: Label such as ``A``, ``7`` or ``K``.
	"""
	return VALUE_LABELS.get(value, str(value))


class Card:
	"""A single playing card."""

	__slots__ = ("id", "value", "suit")

	def __init__(self, value: int, suit: str, copy_index: int = 0) -> None:
		"""Create a card.

		Args:
			value: Card value between 0 and 13, also its score.
			suit: One of ``SUITS`` or ``joker``.
			copy_index: Index used to keep joker identifiers unique.
		"""
		self.id = f"{value}_{suit}_{copy_index}"
		self.value = value
		self.suit = suit

	@property
	def point(self) -> int:
		"""Return the score of the card.

		Returns:
			int: Card value, 0-13.
		"""
		return self.value

	@property
	def skill(self) -> str:
		"""Return the skill of the card.

		Returns:
			str: One of the ``SKILL_*`` constants.
		"""
		return skill_of(self.value)

	@property
	def is_special(self) -> bool:
		"""Tell whether the card triggers a skill.

		Returns:
			bool: ``True`` for values 7-12.
		"""
		return self.skill != SKILL_NONE

	def to_dict(self) -> dict:
		"""Serialize the card for clients.

		Returns:
			dict: ``{id, value, suit, label, skill, skill_label, is_special}``.
		"""
		return {
			"id": self.id,
			"value": self.value,
			"suit": self.suit,
			"label": label_of(self.value),
			"skill": self.skill,
			"skill_label": SKILL_LABELS[self.skill],
			"is_special": self.is_special,
		}


def build_deck() -> List[Card]:
	"""Build the shuffled 54 card deck.

	Returns:
		List[Card]: Shuffled cards, the end of the list is the top of the pile.
	"""
	deck = [Card(0, "joker", index) for index in range(JOKER_COUNT)]
	deck.extend(
		Card(value, suit)
		for value in range(1, MAX_VALUE + 1)
		for suit in SUITS
	)
	random.shuffle(deck)
	return deck
