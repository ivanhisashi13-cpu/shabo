"""Offline regression checks for the SHABO rules engine.

Run with ``PYTHONPATH=backend python tests/rules_test.py``.
"""

import sys
import time
from collections import Counter

from app.game.cards import build_deck
from app.game.cards import Card
from app.game.cards import HAND_SIZE
from app.game.cards import SKILL_PEEK_OTHER
from app.game.cards import SKILL_PEEK_SELF
from app.game.cards import SKILL_SWAP
from app.game.engine import CABO_PENALTY
from app.game.engine import GameEngine
from app.game.engine import GameError
from app.game.engine import KAMIKAZE_PENALTY
from app.game.engine import MODE_MULTI
from app.game.engine import Phase
from app.game.engine import Sub

PASSED = []
FAILED = []


def check(name: str, condition: bool, detail: str = "") -> None:
	"""Record one assertion result.

	Args:
		name: Case name.
		condition: Whether the case passed.
		detail: Extra text shown on failure.
	"""
	if condition:
		PASSED.append(name)
		print(f"  PASS  {name}")
	else:
		FAILED.append(name)
		print(f"  FAIL  {name} {detail}")


def make_engine(count: int = 3, mode: str = "SINGLE") -> GameEngine:
	"""Create a started engine with deterministic players.

	Args:
		count: Player count.
		mode: Game mode.

	Returns:
		GameEngine: Engine already in the peek phase.
	"""
	members = [
		{"user_id": f"p{index}", "nickname": f"玩家{index}", "avatar": "fox"}
		for index in range(count)
	]
	engine = GameEngine(members, mode=mode, turn_timeout=30, peek_timeout=15, reveal_seconds=3)
	engine.start_round()
	return engine


def finish_peek(engine: GameEngine) -> None:
	"""Complete the opening peek phase for everyone.

	Args:
		engine: Target engine.
	"""
	guard = 0
	while engine.phase == Phase.PEEK_PHASE and guard < 40:
		guard += 1
		if engine.sub == Sub.PEEK_SELECT:
			peeker = engine.current_peeker()
			engine.submit_peek(peeker.user_id, [0, 1])
		else:
			engine.deadline = time.time() - 1
			engine.tick()


def test_deck() -> None:
	"""Validate the composition of the 54 card pool."""
	print("[牌组]")
	deck = build_deck()
	check("牌组共 54 张", len(deck) == 54, f"实际 {len(deck)}")
	values = Counter(card.value for card in deck)
	check("0 号牌 2 张", values[0] == 2, f"实际 {values[0]}")
	check("1-13 每个点数 4 张", all(values[value] == 4 for value in range(1, 14)), str(values))
	check("点数即分数", all(card.point == card.value for card in deck))
	check("7/8 为自窥", all(card.skill == SKILL_PEEK_SELF for card in deck if card.value in (7, 8)))
	check("9/10 为窥敌", all(card.skill == SKILL_PEEK_OTHER for card in deck if card.value in (9, 10)))
	check("11/12 为换牌", all(card.skill == SKILL_SWAP for card in deck if card.value in (11, 12)))
	check("13 与 0-6 无技能", all(not card.is_special for card in deck if card.value in (0, 1, 2, 3, 4, 5, 6, 13)))
	check("特殊牌共 24 张", len([card for card in deck if card.is_special]) == 24)
	check("牌 id 唯一", len({card.id for card in deck}) == 54)


def test_setup() -> None:
	"""Validate dealing and the opening peek."""
	print("[开局]")
	engine = make_engine(3)
	check("阶段进入 PEEK_PHASE", engine.phase == Phase.PEEK_PHASE)
	check("每人 4 张手牌", all(len([s for s in p.hand if s.card]) == HAND_SIZE for p in engine.players))
	check("弃牌堆初始 1 张", len(engine.discard) == 1)
	check("牌堆剩余 41 张", len(engine.deck) == 54 - 12 - 1, f"实际 {len(engine.deck)}")
	check("发牌后无人知晓任何牌", all(not slot.revealed_to for p in engine.players for slot in p.hand))

	peeker = engine.current_peeker()
	try:
		engine.submit_peek(peeker.user_id, [0, 0])
		check("拒绝重复槽位", False)
	except GameError:
		check("拒绝重复槽位", True)

	other = [p for p in engine.players if p.user_id != peeker.user_id][0]
	try:
		engine.submit_peek(other.user_id, [0, 1])
		check("拒绝非当前偷看者", False)
	except GameError:
		check("拒绝非当前偷看者", True)

	engine.submit_peek(peeker.user_id, [0, 2])
	check("偷看后仅自己可见 2 张",
		sorted(i for i, s in enumerate(peeker.hand) if peeker.user_id in s.revealed_to) == [0, 2])
	check("偷看后进入展示态", engine.sub == Sub.REVEAL)

	finish_peek(engine)
	check("全员偷看后进入 PLAYING_PHASE", engine.phase == Phase.PLAYING_PHASE)
	check("回合起始为 WAITING_ACTION", engine.sub == Sub.WAITING_ACTION)


def test_basic_actions() -> None:
	"""Validate draw, discard and replace."""
	print("[摸牌 / 弃牌 / 替换]")
	engine = make_engine(3)
	finish_peek(engine)

	actor = engine.current_player()
	other = [p for p in engine.players if p.user_id != actor.user_id][0]
	try:
		engine.action_draw(other.user_id)
		check("非当前玩家不能摸牌", False)
	except GameError:
		check("非当前玩家不能摸牌", True)

	deck_before = len(engine.deck)
	engine.action_draw(actor.user_id)
	check("摸牌后牌堆减 1", len(engine.deck) == deck_before - 1)
	check("摸牌后状态 CARD_DRAWN", engine.sub == Sub.CARD_DRAWN)
	drawn = engine.drawn_card
	engine.action_discard(actor.user_id)
	check("弃牌进入弃牌堆顶", engine.discard[-1] is drawn)
	check("弃牌后轮转到下一位", engine.current_player().user_id != actor.user_id)

	actor2 = engine.current_player()
	engine.action_draw(actor2.user_id)
	drawn2 = engine.drawn_card
	old_card = actor2.hand[2].card
	engine.action_replace(actor2.user_id, 2)
	check("替换后新牌在槽位", actor2.hand[2].card is drawn2)
	check("替换后旧牌进入弃牌堆", engine.discard[-1] is old_card)
	check("替换后新牌仅自己可见", actor2.hand[2].revealed_to == {actor2.user_id})


def test_take_from_discard() -> None:
	"""Validate taking the discard top into a hand slot."""
	print("[弃牌堆取牌]")
	engine = make_engine(3)
	finish_peek(engine)
	actor = engine.current_player()
	top = engine.discard[-1]
	old_card = actor.hand[1].card
	discard_before = len(engine.discard)

	engine.action_take_discard(actor.user_id, 1)
	check("弃牌堆顶进入手牌", actor.hand[1].card is top)
	check("旧手牌进入弃牌堆顶", engine.discard[-1] is old_card)
	check("弃牌堆数量不变", len(engine.discard) == discard_before, f"实际 {len(engine.discard)}")
	check("取牌为明牌，全员可见", actor.hand[1].revealed_to == {p.user_id for p in engine.players})
	check("取牌后回合结束", engine.current_player().user_id != actor.user_id)

	actor2 = engine.current_player()
	engine.action_draw(actor2.user_id)
	try:
		engine.action_take_discard(actor2.user_id, 0)
		check("摸牌后不能再取弃牌堆", False)
	except GameError:
		check("摸牌后不能再取弃牌堆", True)


def test_multi_replace_match() -> None:
	"""Validate replacing several equal cards with one drawn card."""
	print("[多张换牌 · 点数相同]")
	engine = make_engine(3)
	finish_peek(engine)
	actor = engine.current_player()
	actor.hand[0].card = Card(5, "spade")
	actor.hand[1].card = Card(5, "heart")
	actor.hand[2].card = Card(9, "club")

	engine.action_draw(actor.user_id)
	drawn = engine.drawn_card
	engine.action_replace(actor.user_id, slots=[1, 0])
	check("新牌落在首个选中的槽位", actor.hand[1].card is drawn, str(actor.hand[1].card))
	check("另一张相同点数的牌清空", actor.hand[0].card is None)
	check("手牌数量减少到 3", len(actor.hand_values()) == 3, str(actor.hand_values()))
	check("两张相同点数都进弃牌堆", all(card.value == 5 for card in engine.discard[-2:]))
	check("多张换牌后回合结束", engine.current_player().user_id != actor.user_id)


def test_multi_replace_mismatch() -> None:
	"""Validate the penalty when the revealed cards differ."""
	print("[多张换牌 · 点数不同]")
	engine = make_engine(3)
	finish_peek(engine)
	actor = engine.current_player()
	everyone = {item.user_id for item in engine.players}
	for index, value in enumerate((2, 3, 4, 6)):
		actor.hand[index].card = Card(value, "spade", index)

	deck_before = len(engine.deck)
	engine.action_draw(actor.user_id)
	drawn = engine.drawn_card
	engine.action_replace(actor.user_id, slots=[0, 1, 2])
	check("亮出的牌全员可见", all(actor.hand[index].revealed_to == everyone for index in (0, 1, 2)))
	check("原有手牌保持不动", [actor.hand[index].card.value for index in range(4)] == [2, 3, 4, 6])
	check("摸到的牌收进手牌", actor.hand[4].card is drawn)
	check("额外罚牌 N-2 张", len(actor.hand) == 6, f"实际 {len(actor.hand)}")
	check("罚牌无人知晓", actor.hand[5].revealed_to == set())
	check("牌堆共少 2 张", len(engine.deck) == deck_before - 2, f"实际 {len(engine.deck)}")
	check("手牌总数变成 6", len(actor.hand_values()) == 6)

	actor2 = engine.current_player()
	actor2.hand[0].card = Card(1, "spade")
	actor2.hand[1].card = Card(13, "heart")
	engine.action_take_discard(actor2.user_id, slots=[0, 1])
	check("弃牌堆取牌配对失败也会加牌", len(actor2.hand_values()) == 5, str(actor2.hand_values()))
	check("取来的明牌全员可见", actor2.hand[4].revealed_to == everyone)


def test_skill_peek_self() -> None:
	"""Validate the 7/8 self peek skill."""
	print("[技能 7 / 8 自窥]")
	engine = make_engine(3)
	finish_peek(engine)
	actor = engine.current_player()

	engine.action_draw(actor.user_id)
	engine.drawn_card = Card(7, "spade")
	engine.action_use_special(actor.user_id)
	check("7 号进入目标选择", engine.sub == Sub.SPECIAL and engine.special["skill"] == SKILL_PEEK_SELF)
	engine.special_select(actor.user_id, slot_index=3)
	check("7 号看到自己的牌", actor.user_id in actor.hand[3].revealed_to)
	check("7 号自身进入弃牌堆", engine.discard[-1].value == 7)
	check("7 号后进入展示态", engine.sub == Sub.REVEAL)
	engine.deadline = time.time() - 1
	engine.tick()
	check("展示结束后回合切换", engine.current_player().user_id != actor.user_id)

	actor2 = engine.current_player()
	engine.action_draw(actor2.user_id)
	engine.drawn_card = Card(8, "heart")
	engine.action_use_special(actor2.user_id)
	engine.special_select(actor2.user_id, slot_index=2)
	check("8 号同为自窥", actor2.user_id in actor2.hand[2].revealed_to)


def test_skill_peek_other() -> None:
	"""Validate the 9/10 opponent peek skill."""
	print("[技能 9 / 10 窥敌]")
	engine = make_engine(3)
	finish_peek(engine)
	actor = engine.current_player()
	target = [p for p in engine.players if p.user_id != actor.user_id][0]

	engine.action_draw(actor.user_id)
	engine.drawn_card = Card(9, "club")
	engine.action_use_special(actor.user_id)
	check("9 号为窥敌", engine.special["skill"] == SKILL_PEEK_OTHER)
	engine.special_select(actor.user_id, target_id=target.user_id)
	engine.special_select(actor.user_id, slot_index=3)
	check("9 号看到对手的牌", actor.user_id in target.hand[3].revealed_to)
	check("9 号不泄露给被看者", target.user_id not in target.hand[3].revealed_to)
	snapshot = engine.snapshot_for(target.user_id)
	target_view = [row for row in snapshot["players"] if row["user_id"] == target.user_id][0]
	check("被偷看者快照仍看不到自己的牌", target_view["hand"][3]["card"] is None)

	engine.deadline = time.time() - 1
	engine.tick()
	actor2 = engine.current_player()
	target2 = [p for p in engine.players if p.user_id != actor2.user_id][0]
	engine.action_draw(actor2.user_id)
	engine.drawn_card = Card(10, "diamond")
	engine.action_use_special(actor2.user_id)
	engine.special_select(actor2.user_id, target_id=target2.user_id)
	engine.special_select(actor2.user_id, slot_index=2)
	check("10 号同为窥敌", actor2.user_id in target2.hand[2].revealed_to)


def test_skill_swap() -> None:
	"""Validate the 11/12 blind swap skill."""
	print("[技能 11 / 12 换牌]")
	engine = make_engine(3)
	finish_peek(engine)
	actor = engine.current_player()
	target = [p for p in engine.players if p.user_id != actor.user_id][0]

	actor.hand[0].revealed_to = {actor.user_id}
	mine = actor.hand[0].card
	theirs = target.hand[2].card
	engine.action_draw(actor.user_id)
	engine.drawn_card = Card(11, "spade")
	engine.action_use_special(actor.user_id)
	engine.special_select(actor.user_id, slot_index=0)
	engine.special_select(actor.user_id, target_id=target.user_id)
	engine.special_select(actor.user_id, slot_index=2)
	check("11 号完成交换", actor.hand[0].card is theirs and target.hand[2].card is mine)
	check("11 号可见性跟随牌移动", actor.user_id in target.hand[2].revealed_to)
	check("11 号换回的牌未知（盲换）", actor.user_id not in actor.hand[0].revealed_to)
	check("11 号后回合结束", engine.current_player().user_id != actor.user_id)

	actor2 = engine.current_player()
	rival = [p for p in engine.players if p.user_id != actor2.user_id][0]
	engine.action_draw(actor2.user_id)
	engine.drawn_card = Card(12, "heart")
	engine.action_use_special(actor2.user_id)
	check("12 号同为换牌", engine.special["skill"] == SKILL_SWAP)
	engine.special_select(actor2.user_id, slot_index=1)
	engine.special_select(actor2.user_id, target_id=rival.user_id)
	engine.special_select(actor2.user_id, slot_index=1)
	check("12 号换牌成功", engine.current_player().user_id != actor2.user_id)


def test_two_player_autofill() -> None:
	"""Validate the two player shortcuts of the targeted skills."""
	print("[两人局特殊规则]")
	engine = make_engine(2)
	finish_peek(engine)
	actor = engine.current_player()
	rival = [p for p in engine.players if p.user_id != actor.user_id][0]

	engine.action_draw(actor.user_id)
	engine.drawn_card = Card(9, "spade")
	engine.action_use_special(actor.user_id)
	step = engine.snapshot_for(actor.user_id)["special"]
	check("两人局窥敌跳过选人", step["kind"] == "slot" and step["owner"] == rival.user_id)

	engine.special_select(actor.user_id, slot_index=0)
	engine.deadline = time.time() - 1
	engine.tick()

	actor2 = engine.current_player()
	rival2 = [p for p in engine.players if p.user_id != actor2.user_id][0]
	engine.action_draw(actor2.user_id)
	engine.drawn_card = Card(11, "club")
	engine.action_use_special(actor2.user_id)
	engine.special_select(actor2.user_id, slot_index=0)
	step = engine.snapshot_for(actor2.user_id)["special"]
	check("两人局换牌自动锁定对手", step["kind"] == "slot" and step["owner"] == rival2.user_id, str(step))


def test_turn_order() -> None:
	"""Validate that turns rotate strictly by seat order."""
	print("[回合顺序]")
	engine = make_engine(3)
	finish_peek(engine)
	order = []
	for _ in range(6):
		actor = engine.current_player()
		order.append(actor.user_id)
		engine.action_draw(actor.user_id)
		engine.action_discard(actor.user_id)
	seats = [item.user_id for item in engine.players]
	start = seats.index(order[0])
	expected = [seats[(start + step) % 3] for step in range(6)]
	check("三人局按座位循环", order == expected, f"实际 {order}")

	engine = make_engine(2)
	finish_peek(engine)
	actor = engine.current_player()
	rival = [item for item in engine.players if item.user_id != actor.user_id][0]
	engine.set_online(rival.user_id, False)
	engine.action_draw(actor.user_id)
	engine.action_discard(actor.user_id)
	check("离线玩家仍然轮到", engine.current_player().user_id == rival.user_id, engine.current_player().user_id)
	engine.deadline = time.time() - 1
	engine.tick()
	guard = 0
	while engine.current_player().user_id == rival.user_id and guard < 6:
		guard += 1
		engine.deadline = time.time() - 1
		engine.tick()
	check("离线玩家超时后交还回合", engine.current_player().user_id == actor.user_id)


def test_cabo_and_score() -> None:
	"""Validate the CABO countdown and the settlement rules."""
	print("[SHABO 呼叫与结算]")
	engine = make_engine(3)
	finish_peek(engine)
	caller = engine.current_player()
	others = [p for p in engine.players if p.user_id != caller.user_id]

	for index, value in enumerate((2, 3, 4, 5)):
		caller.hand[index].card = Card(value, "spade")
	for index in range(HAND_SIZE):
		others[0].hand[index].card = Card(1, "heart")
		others[1].hand[index].card = Card(0, "joker", index)

	engine.call_cabo(caller.user_id)
	check("呼叫后进入 CABO_COUNTDOWN", engine.phase == Phase.CABO_COUNTDOWN)
	check("剩余回合为其余玩家", len(engine.countdown_remaining) == 2)
	try:
		engine.call_cabo(engine.current_player().user_id)
		check("倒计时阶段禁止再次呼叫", False)
	except GameError:
		check("倒计时阶段禁止再次呼叫", True)

	guard = 0
	while engine.phase == Phase.CABO_COUNTDOWN and guard < 10:
		guard += 1
		current = engine.current_player()
		engine.action_draw(current.user_id)
		engine.action_discard(current.user_id)

	check("倒计时结束后结算", engine.phase == Phase.SETTLING)
	rows = {row["user_id"]: row for row in engine.round_result["players"]}
	check("呼叫者基础分 14", rows[caller.user_id]["base_score"] == 14, str(rows[caller.user_id]))
	check("呼叫失败 +10 惩罚", rows[caller.user_id]["penalty"] == CABO_PENALTY == 10)
	check("全 0 分为第一名", rows[others[1].user_id]["rank"] == 1, str(rows[others[1].user_id]))
	check("四张 1 基础分 4", rows[others[0].user_id]["base_score"] == 4)


def test_cabo_success() -> None:
	"""Validate that a successful CABO call takes no penalty."""
	print("[SHABO 呼叫成功]")
	engine = make_engine(2)
	finish_peek(engine)
	caller = engine.current_player()
	rival = [p for p in engine.players if p.user_id != caller.user_id][0]
	for index in range(HAND_SIZE):
		caller.hand[index].card = Card(0, "joker", index)
		rival.hand[index].card = Card(9, "heart")

	engine.call_cabo(caller.user_id)
	current = engine.current_player()
	engine.action_draw(current.user_id)
	engine.action_discard(current.user_id)
	rows = {row["user_id"]: row for row in engine.round_result["players"]}
	check("呼叫成功无惩罚", rows[caller.user_id]["penalty"] == 0)
	check("单局模式一局即结束", engine.match_over is True)
	check("胜者为最低分", engine.winner_user_id == caller.user_id)


def test_kamikaze() -> None:
	"""Validate the kamikaze hand of 12, 12, 13, 13."""
	print("[神风翻盘]")
	engine = make_engine(3)
	finish_peek(engine)
	hero = engine.current_player()
	others = [p for p in engine.players if p.user_id != hero.user_id]

	for index, value in enumerate((12, 12, 13, 13)):
		hero.hand[index].card = Card(value, "spade", index)
	for index in range(HAND_SIZE):
		others[0].hand[index].card = Card(0, "joker", index)
		others[1].hand[index].card = Card(3, "heart")

	engine.call_cabo(hero.user_id)
	guard = 0
	while engine.phase == Phase.CABO_COUNTDOWN and guard < 10:
		guard += 1
		current = engine.current_player()
		engine.action_draw(current.user_id)
		engine.action_discard(current.user_id)

	rows = {row["user_id"]: row for row in engine.round_result["players"]}
	check("神风玩家被标记", rows[hero.user_id]["kamikaze"] is True)
	check("神风玩家本局 0 分", rows[hero.user_id]["final_score"] == 0, str(rows[hero.user_id]))
	check("神风覆盖 SHABO 惩罚", rows[hero.user_id]["penalty"] == 0)
	check("其余玩家 +50", rows[others[0].user_id]["final_score"] == KAMIKAZE_PENALTY,
		str(rows[others[0].user_id]))
	check("其余玩家手牌分照算", rows[others[1].user_id]["final_score"] == 12 + KAMIKAZE_PENALTY,
		str(rows[others[1].user_id]))
	check("神风玩家获胜", engine.round_result["players"][0]["user_id"] == hero.user_id)


def test_reshuffle_and_timeout() -> None:
	"""Validate deck recycling and turn timeout auto play."""
	print("[洗牌与超时]")
	engine = make_engine(2)
	finish_peek(engine)
	engine.discard.extend(engine.deck)
	engine.deck = []
	actor = engine.current_player()
	engine.action_draw(actor.user_id)
	check("牌堆耗尽后自动洗牌", len(engine.deck) > 0)
	check("弃牌堆保留顶部 1 张后重洗", len(engine.discard) >= 1)

	engine.action_discard(actor.user_id)
	actor2 = engine.current_player()
	engine.deadline = time.time() - 1
	discard_before = len(engine.discard)
	engine.tick()
	check("回合超时自动摸牌并弃牌", len(engine.discard) == discard_before + 1)
	check("超时后轮转", engine.current_player().user_id != actor2.user_id)


def test_multi_round() -> None:
	"""Validate accumulated scoring up to the target score."""
	print("[累计 100 分]")
	engine = make_engine(2, mode=MODE_MULTI)
	engine.target_score = 100
	finish_peek(engine)
	caller = engine.current_player()
	rival = [p for p in engine.players if p.user_id != caller.user_id][0]
	for index in range(HAND_SIZE):
		caller.hand[index].card = Card(0, "joker", index)
		rival.hand[index].card = Card(9, "heart")
	engine.call_cabo(caller.user_id)
	current = engine.current_player()
	engine.action_draw(current.user_id)
	engine.action_discard(current.user_id)
	check("多局模式累计总分", rival.total_score == 36, f"实际 {rival.total_score}")
	check("未达 100 分继续比赛", engine.match_over is False)

	rival.total_score = 96
	engine.start_round()
	finish_peek(engine)
	caller2 = engine.current_player()
	rival2 = [p for p in engine.players if p.user_id != caller2.user_id][0]
	caller2.total_score = 40
	rival2.total_score = 96
	for index in range(HAND_SIZE):
		caller2.hand[index].card = Card(0, "joker", index)
		rival2.hand[index].card = Card(2, "club")
	engine.call_cabo(caller2.user_id)
	current = engine.current_player()
	engine.action_draw(current.user_id)
	engine.action_discard(current.user_id)
	check("有人累计到 100 分整场结束", engine.match_over is True,
		f"{caller2.total_score} / {rival2.total_score}")
	check("累计最低者获胜", engine.winner_user_id == min(engine.players, key=lambda p: p.total_score).user_id)
	worst = max(engine.players, key=lambda p: p.total_score)
	check("结算标记总分最高者为傻波儿", engine.round_result["shabo_user_id"] == worst.user_id,
		str(engine.round_result["shabo_user_id"]))


def test_leaving() -> None:
	"""Validate that a leaver ends a two player round."""
	print("[离场处理]")
	engine = make_engine(2)
	finish_peek(engine)
	victim = engine.players[1]
	engine.player_left(victim.user_id)
	check("两人局有人离场即结算", engine.phase == Phase.SETTLING)
	check("离场玩家不计入结算", all(row["user_id"] != victim.user_id for row in engine.round_result["players"]))


def main() -> int:
	"""Run every regression case.

	Returns:
		int: Process exit code.
	"""
	test_deck()
	test_setup()
	test_basic_actions()
	test_take_from_discard()
	test_multi_replace_match()
	test_multi_replace_mismatch()
	test_skill_peek_self()
	test_skill_peek_other()
	test_skill_swap()
	test_two_player_autofill()
	test_turn_order()
	test_cabo_and_score()
	test_cabo_success()
	test_kamikaze()
	test_reshuffle_and_timeout()
	test_multi_round()
	test_leaving()

	print()
	print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
	for name in FAILED:
		print(f"  未通过: {name}")
	return 1 if FAILED else 0


if __name__ == "__main__":
	sys.exit(main())
