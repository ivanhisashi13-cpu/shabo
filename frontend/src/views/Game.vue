<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import Avatar from '../components/Avatar.vue'
import PlayingCard from '../components/PlayingCard.vue'
import { EMOTES, QUICK_PHRASES, emoteSrc } from '../data/emotes'
import { RULE_SECTIONS } from '../data/rules'
import { useAuthStore } from '../store/auth'
import { useGameStore } from '../store/game'

const auth = useAuthStore()
const store = useGameStore()

const boardEl = ref(null)
const flights = ref([])
const peekPicks = ref([])
const selectMode = ref('')
const picks = ref([])
const showLog = ref(false)
const caboStamp = ref('')
const caboCall = ref(null)
const chatOpen = ref(false)
const emojiOpen = ref(false)
const chatDraft = ref('')
const bubbles = ref({})
const showRules = ref(false)
const showAvatarPicker = ref(false)
const settleBanner = ref(false)
const resultShown = ref(false)
const revealStep = ref(0)

const SEAT_LAYOUT = {
	1: [{ x: 480, y: 50, dir: 'row' }],
	2: [
		{ x: 240, y: 52, dir: 'row' },
		{ x: 720, y: 52, dir: 'row' }
	],
	3: [
		{ x: 92, y: 56, dir: 'col' },
		{ x: 480, y: 50, dir: 'row' },
		{ x: 868, y: 56, dir: 'col' }
	],
	4: [
		{ x: 92, y: 52, dir: 'col' },
		{ x: 336, y: 50, dir: 'row' },
		{ x: 624, y: 50, dir: 'row' },
		{ x: 868, y: 52, dir: 'col' }
	]
}

const SPECIAL_NAME = { peek_self: '自窥 · 看自己 1 张', peek_other: '窥敌 · 看他人 1 张', swap: '换牌 · 与他人盲换' }

const g = computed(() => store.game)
const myId = computed(() => auth.myId)
const players = computed(() => (g.value ? g.value.players : []))
const me = computed(() => players.value.find((item) => item.user_id === myId.value) || null)

const opponents = computed(() => {
	const list = players.value
	const index = list.findIndex((item) => item.user_id === myId.value)
	if (index < 0) return list
	return [...list.slice(index + 1), ...list.slice(0, index)]
})

const seats = computed(() => {
	const layout = SEAT_LAYOUT[opponents.value.length] || []
	return opponents.value.map((player, index) => {
		const spot = layout[index] || { x: 480, y: 54, dir: 'row' }
		return { player, ...spot, side: spot.x < 480 ? 'right' : 'left' }
	})
})

const isMyTurn = computed(() => Boolean(g.value) && g.value.turn_user_id === myId.value)
const isMyPeek = computed(() => Boolean(g.value) && g.value.phase === 'PEEK_PHASE' && g.value.peek_user_id === myId.value)
const peekSelecting = computed(() => isMyPeek.value && g.value.sub === 'PEEK_SELECT')
const drawn = computed(() => (g.value ? g.value.drawn_card : null))
const special = computed(() => (g.value && isMyTurn.value ? g.value.special : null))
const result = computed(() => (g.value ? g.value.round_result : null))

const canAct = computed(() => isMyTurn.value && Boolean(g.value) && g.value.sub === 'WAITING_ACTION')
const canDraw = computed(() => canAct.value && !selectMode.value && !special.value)
const canTake = computed(() => canAct.value && !special.value && Boolean(g.value.discard_top))
const canShabo = computed(() => canAct.value && !selectMode.value && !special.value && !g.value.cabo_caller)

const shaboRow = computed(() => {
	const state = result.value
	if (!state || !state.shabo_user_id) return null
	return state.players.find((row) => row.user_id === state.shabo_user_id) || null
})

const winnerRow = computed(() => {
	const state = result.value
	if (!state || !state.winner_user_id) return null
	return state.players.find((row) => row.user_id === state.winner_user_id) || null
})
const isHost = computed(() => Boolean(store.room && store.room.host_user_id === myId.value))
const isAdmin = computed(() => Boolean(auth.user && auth.user.is_admin))

function triggerBotChat() {
	store.send('bot_chat')
}

const ownCards = computed(() => (me.value ? me.value.hand.filter((slot) => slot.has_card) : []))

const ownSize = computed(() => {
	const count = ownCards.value.length
	if (count <= 4) return 'own'
	if (count <= 6) return 'mid'
	return 'tight'
})

const pickedCards = computed(() => ownCards.value.filter((slot) => picks.value.includes(slot.slot)))

const pickHint = computed(() => {
	if (picks.value.length < 2) return '选 1 张即普通替换，选多张可尝试同点数一次清掉'
	const known = pickedCards.value.filter((slot) => slot.card)
	if (known.length === picks.value.length) {
		const values = new Set(known.map((slot) => slot.card.value))
		return values.size === 1 ? `同为 ${known[0].card.label}，确认即可 ${picks.value.length} 换 1` : '点数不同会亮牌并加牌，谨慎确认'
	}
	return '点数不同会亮牌并加牌，谨慎确认'
})

const opTip = computed(() => {
	if (!g.value) return null
	if (selectMode.value) return { text: pickHint.value, tone: '' }
	if (special.value) {
		return { text: `${special.value.prompt}（${special.value.step_index + 1}/${special.value.step_total}）`, tone: '' }
	}
	if (isMyTurn.value && g.value.sub === 'CARD_DRAWN' && drawn.value) return null
	if (canAct.value) return { text: '点摸牌堆摸牌，或点弃牌堆拿牌', tone: 'act' }
	return null
})

const actorName = computed(() => {
	if (!g.value) return ''
	const actorId = g.value.phase === 'PEEK_PHASE' ? g.value.peek_user_id : g.value.turn_user_id
	const player = players.value.find((item) => item.user_id === actorId)
	return player ? player.nickname : ''
})

const banner = computed(() => {
	const state = g.value
	if (!state) return ''
	if (state.round_result) return '本局结算'
	if (state.phase === 'PEEK_PHASE') {
		if (state.sub === 'REVEAL') return isMyPeek.value ? '记住你的两张牌！' : `${actorName.value} 正在看牌`
		return isMyPeek.value ? '选择 2 张手牌查看' : `等待 ${actorName.value} 看牌`
	}
	if (state.phase === 'CABO_COUNTDOWN' && !isMyTurn.value) return `SHABO 已呼叫 · ${actorName.value} 行动中`
	if (!isMyTurn.value) return `${actorName.value} 行动中`
	if (state.sub === 'REVEAL') return '看牌中，记住它！'
	if (state.sub === 'SPECIAL') return special.value?.prompt || '使用技能中'
	if (selectMode.value === 'replace') return `点手牌选择要换掉的牌（已选 ${picks.value.length} 张）`
	if (selectMode.value === 'take') return `点手牌选择要换掉的牌（已选 ${picks.value.length} 张）`
	if (state.sub === 'CARD_DRAWN') return '选择如何处理这张牌'
	return '轮到你了：点摸牌堆摸牌，或点弃牌堆拿牌'
})

function handCards(player) {
	return player.hand.filter((slot) => slot.has_card)
}

/* ----------------------------------------------------------- interactions */

function faceUp(player, slot) {
	if (!slot.has_card) return false
	if (store.revealedCard(player.user_id, slot.slot)) return true
	if (slot.public) return true
	return Boolean(store.memoryAssist && slot.known && player.user_id === myId.value)
}

function cardOf(player, slot) {
	return store.revealedCard(player.user_id, slot.slot) || slot.card
}

function ownSlotClickable(slot) {
	if (!slot.has_card) return false
	if (peekSelecting.value) return true
	if (selectMode.value) return true
	if (special.value && special.value.kind === 'own_slot') return true
	if (special.value && special.value.kind === 'swap_pick') return true
	if (special.value && special.value.kind === 'slot' && special.value.owner === myId.value) return true
	return false
}

function foeSlotClickable(player, slot) {
	if (!slot.has_card || !special.value) return false
	if (special.value.kind === 'any_foe_slot' || special.value.kind === 'swap_pick') {
		return special.value.candidates.includes(player.user_id)
	}
	return special.value.kind === 'slot' && special.value.owner === player.user_id
}

function ownSlotSelected(slot) {
	if (peekPicks.value.includes(slot.slot) || picks.value.includes(slot.slot)) return true
	const picksMap = special.value && special.value.picks
	return Boolean(special.value && special.value.kind === 'swap_pick' && picksMap && picksMap.slot_a === slot.slot)
}

function foeSlotSelected(player, slot) {
	const picksMap = special.value && special.value.picks
	if (!picksMap || !special.value || special.value.kind !== 'swap_pick') return false
	return picksMap.target === player.user_id && picksMap.slot_b === slot.slot
}

function playerClickable(player) {
	if (!special.value || special.value.kind !== 'player') return false
	return special.value.candidates.includes(player.user_id)
}

function startSelect(mode) {
	if (selectMode.value === mode) {
		cancelSelect()
		return
	}
	selectMode.value = mode
	picks.value = []
}

function cancelSelect() {
	selectMode.value = ''
	picks.value = []
}

function confirmSelect() {
	if (!picks.value.length) return
	const action = selectMode.value === 'take' ? 'take_discard' : 'replace'
	store.send(action, { slots: picks.value })
	cancelSelect()
}

function clickOwnSlot(slot) {
	if (!ownSlotClickable(slot)) return
	if (peekSelecting.value) {
		const list = peekPicks.value
		if (list.includes(slot.slot)) {
			peekPicks.value = list.filter((value) => value !== slot.slot)
			return
		}
		if (list.length >= 2) return
		peekPicks.value = [...list, slot.slot]
		if (peekPicks.value.length === 2) {
			store.send('peek_select', { slots: peekPicks.value })
			peekPicks.value = []
		}
		return
	}
	if (selectMode.value) {
		picks.value = picks.value.includes(slot.slot)
			? picks.value.filter((value) => value !== slot.slot)
			: [...picks.value, slot.slot]
		return
	}
	store.send('special_select', { slot: slot.slot })
}

function clickFoeSlot(player, slot) {
	if (!foeSlotClickable(player, slot)) return
	store.send('special_select', { target_id: player.user_id, slot: slot.slot })
}

function clickPlayer(player) {
	if (!playerClickable(player)) return
	store.send('special_select', { target_id: player.user_id })
}

function useSpecial() {
	cancelSelect()
	store.send('use_special')
}

function clickDeck() {
	if (!canDraw.value) return
	store.send('draw')
}

function clickDiscardPile() {
	if (!canTake.value) return
	startSelect('take')
}

function openRules() {
	showRules.value = true
}

async function openAvatarPicker() {
	await auth.loadAvatars()
	showAvatarPicker.value = true
}

async function pickAvatar(item) {
	if (!item || item === me.value?.avatar) {
		showAvatarPicker.value = false
		return
	}
	await auth.updateProfile({ avatar: item })
	showAvatarPicker.value = false
}

function cancelSpecial() {
	store.send('cancel_special')
}

function leave() {
	store.send('leave_room')
}

watch(
	() => (g.value ? `${g.value.phase}:${g.value.sub}:${g.value.turn_user_id}` : ''),
	() => {
		cancelSelect()
		peekPicks.value = []
	}
)

/* --------------------------------------------------------- chat & emotes */

let bubbleSeq = 0
let lastChatAt = 0

function toggleChat() {
	chatOpen.value = !chatOpen.value
	if (chatOpen.value) emojiOpen.value = false
}

function toggleEmoji() {
	emojiOpen.value = !emojiOpen.value
	if (emojiOpen.value) chatOpen.value = false
}

function sendChat(text) {
	const value = String(text || '').trim()
	if (!value) return
	store.send('chat', { text: value.slice(0, 40), kind: 'text' })
	chatDraft.value = ''
	chatOpen.value = false
}

function sendEmote(key) {
	store.send('chat', { text: key, kind: 'emoji' })
	emojiOpen.value = false
}

function showBubble(message) {
	const id = ++bubbleSeq
	const kind = message.kind === 'emoji' ? 'emoji' : 'text'
	bubbles.value = { ...bubbles.value, [message.user_id]: { id, kind, text: message.text } }
	setTimeout(() => {
		const current = bubbles.value[message.user_id]
		if (!current || current.id !== id) return
		const next = { ...bubbles.value }
		delete next[message.user_id]
		bubbles.value = next
	}, kind === 'emoji' ? 3200 : 4200)
}

watch(
	() => (store.room ? store.room.chat : null),
	(list) => {
		if (!list || !list.length) return
		for (const message of list) {
			if (!message.user_id || message.at <= lastChatAt) continue
			showBubble(message)
		}
		lastChatAt = Math.max(lastChatAt, ...list.map((item) => item.at))
	},
	{ deep: true }
)

onMounted(() => {
	const list = (store.room && store.room.chat) || []
	lastChatAt = list.length ? Math.max(...list.map((item) => item.at)) : Date.now()
	if (store.queue.length) {
		nextTick(() => pump())
	}
})

/* ------------------------------------------------------------- animations */

function anchorElement(ref) {
	if (!boardEl.value || !ref) return null
	if (ref.zone === 'slot') return boardEl.value.querySelector(`[data-slot="${ref.owner}:${ref.slot}"]`)
	return boardEl.value.querySelector(`[data-anchor="${ref.zone}"]`)
}

function localMetrics(element) {
	const board = boardEl.value
	const boardRect = board.getBoundingClientRect()
	const scaleX = boardRect.width / board.offsetWidth || 1
	const scaleY = boardRect.height / board.offsetHeight || 1
	const rect = element.getBoundingClientRect()
	return {
		x: (rect.left + rect.width / 2 - boardRect.left) / scaleX,
		y: (rect.top + rect.height / 2 - boardRect.top) / scaleY,
		h: rect.height / scaleY
	}
}

function wait(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms))
}

function nextFrame() {
	return new Promise((resolve) => {
		requestAnimationFrame(() => requestAnimationFrame(resolve))
	})
}

let flightSeq = 0

const FLIGHT_MS = 800
const DEAL_MS = 520
const REVEAL_PAUSE_MS = 220
const FLIGHT_BASE_H = 122

const flyingSlots = ref({})
const drawnFlying = ref(0)

function slotKey(owner, slot) {
	return `${owner}:${slot}`
}

function slotFlying(owner, slot) {
	return Boolean(flyingSlots.value[slotKey(owner, slot)])
}

function markSlot(key, delta) {
	const next = { ...flyingSlots.value }
	next[key] = (next[key] || 0) + delta
	if (next[key] <= 0) delete next[key]
	flyingSlots.value = next
}

async function fly(source, target, card, duration) {
	const fromEl = anchorElement(source)
	const toEl = anchorElement(target)
	if (!fromEl || !toEl) return
	const from = localMetrics(fromEl)
	const to = localMetrics(toEl)
	const id = ++flightSeq
	const hideKey = target && target.zone === 'slot' ? slotKey(target.owner, target.slot) : null
	const hideDrawn = (source && source.zone === 'drawn') || (target && target.zone === 'drawn')
	if (hideKey) markSlot(hideKey, 1)
	if (hideDrawn) drawnFlying.value += 1
	const item = {
		id,
		card: card || null,
		x: from.x,
		y: from.y,
		scale: from.h / FLIGHT_BASE_H || 1,
		duration
	}
	flights.value = [...flights.value, item]
	await nextTick()
	await nextFrame()
	const found = flights.value.find((entry) => entry.id === id)
	if (found) {
		found.x = to.x
		found.y = to.y
		found.scale = to.h / FLIGHT_BASE_H || 1
	}
	await wait(duration)
	flights.value = flights.value.filter((entry) => entry.id !== id)
	if (hideKey) markSlot(hideKey, -1)
	if (hideDrawn) drawnFlying.value = Math.max(0, drawnFlying.value - 1)
}

function isFlightEvent(event) {
	return event.kind === 'deal' || event.kind === 'move' || event.kind === 'swap'
}

function flightTasks(event) {
	if (event.kind === 'swap') {
		return [fly(event.a, event.b, null, FLIGHT_MS), fly(event.b, event.a, null, FLIGHT_MS)]
	}
	if (event.kind === 'deal') {
		return [fly({ zone: 'deck' }, event.to, null, DEAL_MS)]
	}
	return [fly(event.source, event.to, event.card, FLIGHT_MS)]
}

async function playFlightGroup(group) {
	const tasks = []
	for (const event of group) {
		tasks.push(...flightTasks(event))
	}
	await Promise.all(tasks)
}

async function playEvent(event) {
	if (event.kind === 'reshuffle') {
		store.showToast('牌堆耗尽，弃牌堆重新洗入', 'warn')
		await wait(260)
		return
	}
	if (event.kind === 'reveal') {
		await wait(REVEAL_PAUSE_MS)
		return
	}
	if (event.kind === 'peek') {
		await wait(REVEAL_PAUSE_MS)
		return
	}
	if (event.kind === 'settle') {
		await runSettle()
		return
	}
	if (event.kind === 'cabo') {
		const actor = event.actor
		const player = players.value.find((item) => item.user_id === actor)
		caboCall.value = {
			user_id: actor,
			nickname: player ? player.nickname : actor,
			avatar: player ? player.avatar : 'fox'
		}
		caboStamp.value = actor
		await wait(1700)
		if (caboCall.value && caboCall.value.user_id === actor) caboCall.value = null
		setTimeout(() => {
			if (caboStamp.value === actor) caboStamp.value = ''
		}, 1600)
		return
	}
	await wait(30)
}

let pumping = false

const maxRevealCards = computed(() => {
	if (!result.value) return 0
	return result.value.players.reduce((max, row) => Math.max(max, row.cards.length), 0)
})

const revealDone = computed(() => !result.value || revealStep.value >= maxRevealCards.value)

function cardRevealed(index) {
	return index < revealStep.value
}

function revealedScore(row) {
	let sum = 0
	const shown = Math.min(revealStep.value, row.cards.length)
	for (let index = 0; index < shown; index += 1) {
		sum += row.cards[index].value
	}
	return sum
}

let settling = false

async function runSettle() {
	if (!result.value) return
	settling = true
	resultShown.value = false
	revealStep.value = 0
	settleBanner.value = true
	await wait(1300)
	settleBanner.value = false
	resultShown.value = true
	await nextTick()
	const total = maxRevealCards.value
	for (let step = 1; step <= total; step += 1) {
		revealStep.value = step
		await wait(1000)
	}
	settling = false
}

watch(
	() => store.queue.some((event) => event.kind === 'settle'),
	(hasSettle) => {
		if (hasSettle) settling = true
	}
)

watch(
	() => result.value,
	(value) => {
		if (!value) {
			settleBanner.value = false
			resultShown.value = false
			revealStep.value = 0
			settling = false
			return
		}
		setTimeout(() => {
			if (!settling && !resultShown.value) {
				resultShown.value = true
				revealStep.value = maxRevealCards.value
			}
		}, 200)
	}
)

async function pump() {
	if (pumping) return
	pumping = true
	while (store.queue.length) {
		if (isFlightEvent(store.queue[0])) {
			const group = []
			while (store.queue.length && isFlightEvent(store.queue[0])) {
				group.push(store.queue.shift())
			}
			try {
				await playFlightGroup(group)
			} catch (error) {
				break
			}
			continue
		}
		const event = store.queue.shift()
		try {
			await playEvent(event)
		} catch (error) {
			break
		}
	}
	pumping = false
}

watch(() => store.queue.length, (length) => {
	if (length) pump()
})
</script>

<template>
	<div v-if="g" ref="boardEl" class="screen game">
		<img class="bg" src="/art/bg_game_table.png" alt="" />

		<div class="topbar">
			<button class="round" @click="leave">←</button>
			<div class="round-tag">
				第 {{ g.round }} 局 · {{ g.mode === 'MULTI' ? `${g.target_score} 分制` : '单局' }}
			</div>
			<div class="banner" :class="{ mine: isMyTurn || isMyPeek }">
				<span class="banner-text">{{ banner }}</span>
				<span v-if="store.remainSeconds" class="timer">{{ store.remainSeconds }}s</span>
			</div>
			<div class="top-spacer"></div>
		</div>

		<div
			v-for="seat in seats"
			:key="seat.player.user_id"
			class="seat"
			:class="[seat.dir, { acting: g.turn_user_id === seat.player.user_id || g.peek_user_id === seat.player.user_id }]"
			:style="{ left: `${seat.x}px`, top: `${seat.y}px`, zIndex: bubbles[seat.player.user_id] ? 95 : 10 }"
		>
			<button class="seat-head" :class="{ pickable: playerClickable(seat.player) }" @click="clickPlayer(seat.player)">
				<div class="avatar-wrap">
					<Avatar
						:avatar="seat.player.avatar"
						:size="48"
						:offline="!seat.player.online || seat.player.left"
						:active="g.turn_user_id === seat.player.user_id || g.peek_user_id === seat.player.user_id"
					/>
					<transition name="bubble">
						<div v-if="bubbles[seat.player.user_id]" class="bubble" :class="seat.side">
							<img
								v-if="bubbles[seat.player.user_id].kind === 'emoji'"
								class="bubble-emoji"
								:src="emoteSrc(bubbles[seat.player.user_id].text)"
								alt=""
							/>
							<span v-else>{{ bubbles[seat.player.user_id].text }}</span>
						</div>
					</transition>
				</div>
				<div class="seat-info">
					<div class="seat-name">{{ seat.player.nickname }}</div>
					<div class="mini">
						总分 {{ seat.player.total_score }} · {{ handCards(seat.player).length }} 张
						<span v-if="seat.player.has_called_cabo" class="called">已喊</span>
					</div>
				</div>
				<transition name="stamp">
					<div v-if="caboStamp === seat.player.user_id" class="shabo-stamp">SHABO!</div>
				</transition>
			</button>
			<div class="foe-hand" :class="seat.dir">
				<button
					v-for="slot in handCards(seat.player)"
					:key="slot.slot"
					class="slot-btn"
					:class="{ peeked: store.peekedSlot(seat.player.user_id, slot.slot) }"
					:data-slot="`${seat.player.user_id}:${slot.slot}`"
					@click="clickFoeSlot(seat.player, slot)"
				>
					<PlayingCard
						size="foe"
						:style="slotFlying(seat.player.user_id, slot.slot) ? { visibility: 'hidden' } : null"
						:card="cardOf(seat.player, slot)"
						:face-down="!faceUp(seat.player, slot)"
						:open="slot.public"
						:highlight="foeSlotClickable(seat.player, slot)"
						:selected="foeSlotSelected(seat.player, slot)"
					/>
					<transition name="peek-mark">
						<span v-if="store.peekedSlot(seat.player.user_id, slot.slot)" class="peek-mark">👁 被查看</span>
					</transition>
				</button>
			</div>
		</div>

		<div class="table-center">
			<div class="center-tray"></div>
			<button class="pile deck" :class="{ live: canDraw }" :disabled="!canDraw" @click="clickDeck">
				<div class="pile-anchor" data-anchor="deck">
					<img class="pile-img" src="/art/deck_pile.png" alt="摸牌堆" />
				</div>
				<div class="pile-label"><span class="pile-name">摸牌堆</span><b class="pile-count">{{ g.deck_count }}</b></div>
				<div v-if="canDraw" class="pile-hint">点击摸牌</div>
			</button>

			<div class="middle">
				<div class="drawn-area" data-anchor="drawn">
					<template v-if="!drawnFlying">
						<PlayingCard
							v-if="drawn"
							size="center"
							:card="drawn"
							:badge="drawn.is_special ? SPECIAL_NAME[drawn.skill] : ''"
						/>
						<PlayingCard v-else-if="g.has_drawn_card" size="center" face-down :card="null" />
						<div v-else class="drawn-placeholder">摸到的牌<br />会出现在这里</div>
					</template>
				</div>

				<div class="op-area">
					<template v-if="selectMode">
						<div class="op-row">
							<button class="btn compact green" :disabled="!picks.length" @click="confirmSelect">
								{{ picks.length > 1 ? `确认换 ${picks.length} 张` : '确认换牌' }}
							</button>
							<button class="btn compact ghost" @click="cancelSelect">取消</button>
						</div>
					</template>
					<template v-else-if="special">
						<button class="btn compact ghost" @click="cancelSpecial">取消技能</button>
					</template>
					<template v-else-if="isMyTurn && g.sub === 'CARD_DRAWN' && drawn">
						<div class="op-row">
							<button class="btn compact" @click="store.send('discard')">弃牌</button>
							<button class="btn compact green" @click="startSelect('replace')">替换手牌</button>
							<button v-if="drawn.is_special" class="btn compact yellow" @click="useSpecial">使用技能</button>
						</div>
					</template>
				</div>
			</div>

			<button class="pile discard" :class="{ live: canTake, on: selectMode === 'take' }" :disabled="!canTake" @click="clickDiscardPile">
				<div class="pile-anchor discard" data-anchor="discard">
					<PlayingCard v-if="g.discard_top" size="pile" :card="g.discard_top" hide-skill />
					<div v-else class="empty-slot pile"></div>
				</div>
				<div class="pile-label"><span class="pile-name">弃牌堆</span><b class="pile-count">{{ g.discard_count }}</b></div>
				<div v-if="canTake" class="pile-hint">{{ selectMode === 'take' ? '选手牌换' : '点击拿牌' }}</div>
			</button>
		</div>

		<transition name="fade">
			<div v-if="opTip" class="op-side-tip" :class="opTip.tone">{{ opTip.text }}</div>
		</transition>

		<button class="shabo-side" :disabled="!canShabo" @click="store.send('call_cabo')">
			<img src="/art/button_shabo_call.png" alt="SHABO" />
		</button>

		<div class="own-corner">
			<div class="own-head">
				<button class="avatar-edit" title="点击修改头像" @click="openAvatarPicker">
					<Avatar :avatar="me?.avatar" :size="48" :active="isMyTurn || isMyPeek" />
					<span class="avatar-edit-badge">✎</span>
				</button>
				<div>
					<div class="own-name">{{ me?.nickname }}（我）</div>
					<div class="mini">总分 {{ me?.total_score }} · {{ ownCards.length }} 张</div>
				</div>
				<transition name="stamp">
					<div v-if="caboStamp === myId" class="shabo-stamp own">SHABO!</div>
				</transition>
			</div>
			<div class="tool-row">
				<button class="tool" :class="{ on: chatOpen }" title="聊天" @click="toggleChat">💬</button>
				<button class="tool" :class="{ on: emojiOpen }" title="表情" @click="toggleEmoji">😄</button>
				<button v-if="isAdmin" class="tool" title="机器人随机聊天（测试）" @click="triggerBotChat">🤖</button>
				<button class="tool" :class="{ on: showLog }" title="对局记录" @click="showLog = !showLog">📜</button>
				<button class="tool" title="查看规则" @click="openRules">📖</button>
			</div>
		</div>

		<div class="own-area">
			<div class="own-hand" :class="ownSize">
				<button
					v-for="slot in ownCards"
					:key="slot.slot"
					class="slot-btn"
					:data-slot="`${myId}:${slot.slot}`"
					@click="clickOwnSlot(slot)"
				>
					<PlayingCard
						:size="ownSize"
						:style="slotFlying(myId, slot.slot) ? { visibility: 'hidden' } : null"
						:card="cardOf(me, slot)"
						:face-down="!faceUp(me, slot)"
						:open="slot.public"
						:highlight="ownSlotClickable(slot) || peekPicks.includes(slot.slot) || picks.includes(slot.slot)"
						:selected="ownSlotSelected(slot)"
						:badge="peekPicks.includes(slot.slot) || picks.includes(slot.slot) ? '已选' : ''"
					/>
					<span class="slot-index">{{ slot.slot + 1 }}</span>
				</button>
			</div>
		</div>

		<transition name="bubble">
			<div v-if="bubbles[myId]" class="bubble own-bubble">
				<img v-if="bubbles[myId].kind === 'emoji'" class="bubble-emoji" :src="emoteSrc(bubbles[myId].text)" alt="" />
				<span v-else>{{ bubbles[myId].text }}</span>
			</div>
		</transition>

		<transition name="pop-up">
			<div v-if="chatOpen" class="chat-pop panel">
				<div class="pop-title">快捷聊天</div>
				<div class="phrase-grid">
					<button v-for="text in QUICK_PHRASES" :key="text" class="phrase" @click="sendChat(text)">{{ text }}</button>
				</div>
				<div class="chat-input-row">
					<input v-model="chatDraft" maxlength="40" placeholder="说点什么…" @keyup.enter="sendChat(chatDraft)" />
					<button class="btn compact green" @click="sendChat(chatDraft)">发送</button>
				</div>
			</div>
		</transition>

		<transition name="pop-up">
			<div v-if="emojiOpen" class="emoji-pop panel">
				<button v-for="item in EMOTES" :key="item.key" class="emoji-btn" @click="sendEmote(item.key)">
					<img :src="emoteSrc(item.key)" :alt="item.name" />
					<span class="mini">{{ item.name }}</span>
				</button>
			</div>
		</transition>

		<div v-if="peekSelecting" class="peek-tip">点击你的手牌，选择 2 张记住它们（{{ peekPicks.length }}/2）</div>

		<transition name="fade">
			<div v-if="caboCall" class="cabo-call">
				<div class="cabo-card">
					<Avatar :avatar="caboCall.avatar" :size="72" />
					<div class="cabo-text">
						<div class="cabo-who">{{ caboCall.nickname }}</div>
						<div class="cabo-say">喊了 SHABO！</div>
						<div class="cabo-note">其余玩家各行动最后一回合</div>
					</div>
				</div>
			</div>
		</transition>

		<div v-if="showLog" class="log-panel panel scroll">
			<div class="log-head">
				<div class="log-title">对局记录</div>
				<button class="log-close" @click="showLog = false">×</button>
			</div>
			<div v-for="(line, index) in g.log" :key="index" class="log-line">{{ line }}</div>
		</div>

		<div class="fly-layer">
			<div
				v-for="item in flights"
				:key="item.id"
				class="flight"
				:style="{
					left: `${item.x}px`,
					top: `${item.y}px`,
					transform: `translate(-50%, -50%) scale(${item.scale})`,
					transitionDuration: `${item.duration}ms`
				}"
			>
				<PlayingCard size="center" :card="item.card" :face-down="!item.card" />
			</div>
		</div>

		<transition name="fade">
			<div v-if="settleBanner" class="settle-banner">
				<div class="settle-word">得分结算</div>
			</div>
		</transition>

		<div v-if="resultShown && result" class="mask">
			<div class="panel result">
				<div class="title">{{ result.match_over ? '对战结束' : `第 ${result.round} 局结算` }}</div>
					<transition name="fade">
						<div v-if="revealDone && shaboRow" class="shabo-hero">
							<div class="hero-avatar">
								<Avatar :avatar="shaboRow.avatar" :size="76" />
								<span class="hero-stamp">傻波儿</span>
							</div>
							<div class="hero-text">
								<div class="hero-label">这局的傻波儿是～</div>
								<div class="hero-name">{{ shaboRow.nickname }}</div>
								<div class="hero-note">
									总分 {{ shaboRow.total_score }}（全场最高）
									<template v-if="winnerRow"> · 冠军 {{ winnerRow.nickname }} {{ winnerRow.total_score }} 分</template>
								</div>
							</div>
						</div>
					</transition>
					<div class="result-rows">
						<div v-for="row in result.players" :key="row.user_id" class="result-row" :class="{ win: revealDone && row.user_id === result.winner_user_id, shabo: revealDone && row.user_id === result.shabo_user_id }">
						<Avatar :avatar="row.avatar" :size="40" />
						<div class="result-name">
							{{ row.nickname }}
							<span v-if="row.is_caller" class="caller-tag">SHABO</span>
							<span v-if="row.kamikaze" class="kamikaze-tag">神风</span>
						</div>
						<div class="result-cards">
							<PlayingCard
								v-for="(card, index) in row.cards"
								:key="index"
								class="reveal-card"
								size="foe"
								:card="card"
								:face-down="!cardRevealed(index)"
							/>
						</div>
						<div class="result-score">
							<b class="running">{{ revealedScore(row) }}</b>
							<template v-if="revealDone">
								<span v-if="row.penalty" class="penalty">+{{ row.penalty }}</span>
								= <b>{{ row.final_score }}</b>
							</template>
						</div>
						<div class="result-total">
							<transition name="fade">
								<span v-if="revealDone">总 {{ row.total_score }}</span>
							</transition>
						</div>
					</div>
				</div>
				<div class="result-actions">
					<template v-if="isHost">
						<button class="btn green" @click="store.send('next_round')">
							{{ result.match_over ? '再来一局' : '下一局' }}
						</button>
						<button class="btn ghost" @click="store.send('back_to_room')">返回房间</button>
					</template>
					<div v-else class="hint">等待房主开始下一局…</div>
				</div>
			</div>
		</div>
		<transition name="fade">
			<div v-if="showRules" class="mask" @click.self="showRules = false">
				<div class="panel rules-modal">
					<div class="rules-head">
						<div class="rules-title">SHABO 规则</div>
						<button class="log-close" @click="showRules = false">×</button>
					</div>
					<div class="rules-body scroll">
						<div v-for="section in RULE_SECTIONS" :key="section.title" class="rules-card">
							<div class="rules-card-title">{{ section.title }}</div>
							<p v-for="(line, index) in section.lines" :key="index" class="rules-line">· {{ line }}</p>
						</div>
					</div>
				</div>
			</div>
		</transition>

		<transition name="fade">
			<div v-if="showAvatarPicker" class="mask" @click.self="showAvatarPicker = false">
				<div class="panel avatar-modal">
					<div class="rules-head">
						<div class="rules-title">选择头像</div>
						<button class="log-close" @click="showAvatarPicker = false">×</button>
					</div>
					<div class="avatar-grid scroll">
						<button
							v-for="item in auth.avatars"
							:key="item"
							class="avatar-pick"
							:class="{ on: item === me?.avatar }"
							@click="pickAvatar(item)"
						>
							<Avatar :avatar="item" :size="52" />
						</button>
					</div>
				</div>
			</div>
		</transition>
	</div>
</template>

<style scoped>
.game {
	background: var(--paper);
	overflow: hidden;
}

.bg {
	position: absolute;
	inset: 0;
	width: 100%;
	height: 100%;
	object-fit: cover;
	opacity: 0.9;
}

.topbar {
	position: absolute;
	left: 0;
	right: 0;
	top: 0;
	height: 52px;
	display: flex;
	align-items: center;
	padding: 6px 12px;
	gap: 10px;
	z-index: 20;
}

.round {
	width: 44px;
	height: 44px;
	flex: none;
	border-radius: 50%;
	background: rgba(253, 250, 242, 0.92);
	border: 2px solid var(--brown-line);
	font-size: 18px;
	font-weight: 800;
	color: var(--brown-deep);
}

.round.on {
	background: var(--sage-deep);
	color: #fff;
}

.top-spacer {
	width: 44px;
	flex: none;
}

.banner {
	flex: 1;
	height: 44px;
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 14px;
	border-radius: 999px;
	background: rgba(253, 250, 242, 0.92);
	border: 2px solid var(--brown-line);
	font-size: 20px;
	font-weight: 800;
	color: var(--brown-deep);
	max-width: 520px;
	margin: 0 auto;
}

.banner.mine {
	background: var(--sage-deep);
	border-color: var(--sage-deep);
	color: #fff;
	box-shadow: 0 0 18px rgba(134, 169, 107, 0.7);
}

.timer {
	min-width: 52px;
	text-align: center;
	padding: 2px 10px;
	border-radius: 999px;
	background: var(--coral);
	color: #fff;
	font-size: var(--font-hint);
}

.round-tag {
	flex: none;
	font-size: var(--font-mini);
	color: var(--brown-deep);
	background: rgba(253, 250, 242, 0.8);
	padding: 3px 10px;
	border-radius: 999px;
	white-space: nowrap;
}

/* ------------------------------------------------------------ opponents */
.seat {
	position: absolute;
	transform: translateX(-50%);
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 6px;
	padding: 6px 10px;
	border-radius: 16px;
	background: rgba(253, 250, 242, 0.55);
	z-index: 10;
}

.seat.acting {
	background: rgba(250, 217, 138, 0.8);
	box-shadow: 0 0 16px rgba(245, 172, 106, 0.8);
}

.seat-head {
	position: relative;
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 2px;
	border-radius: 14px;
	border: 2px solid transparent;
}

.avatar-wrap {
	position: relative;
	display: inline-flex;
	flex: none;
}

.seat-head.pickable {
	border-color: var(--coral);
	background: transparent;
	animation: head-pop 0.9s ease-in-out infinite;
}

@keyframes head-pop {
	0%,
	100% {
		transform: scale(1);
		box-shadow: 0 0 0 2px rgba(226, 112, 92, 0.65);
	}
	50% {
		transform: scale(1.06);
		box-shadow: 0 0 0 6px rgba(226, 112, 92, 0.18);
	}
}

.seat-name {
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown-deep);
	max-width: 96px;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.foe-hand {
	display: grid;
	grid-template-columns: repeat(6, auto);
	gap: 5px;
}

.foe-hand.col {
	grid-template-columns: repeat(2, auto);
	gap: 6px;
}

.slot-btn {
	position: relative;
	padding: 0;
	display: block;
}

.slot-btn.peeked::after {
	content: '';
	position: absolute;
	inset: -3px;
	border: 2px solid var(--coral-deep);
	border-radius: 10px;
	box-shadow: 0 0 10px rgba(226, 112, 92, 0.65);
	pointer-events: none;
	z-index: 5;
}

.peek-mark {
	position: absolute;
	left: 50%;
	top: -10px;
	transform: translateX(-50%);
	white-space: nowrap;
	padding: 2px 8px;
	border-radius: 10px;
	background: var(--coral-deep);
	color: #fff;
	font-size: var(--font-mini);
	font-weight: 800;
	box-shadow: 0 2px 6px rgba(60, 40, 24, 0.45);
	z-index: 6;
	pointer-events: none;
}

.peek-mark-enter-active,
.peek-mark-leave-active {
	transition: opacity 0.2s ease, transform 0.2s ease;
}

.peek-mark-enter-from,
.peek-mark-leave-to {
	opacity: 0;
	transform: translateX(-50%) scale(0.7);
}

.empty-slot {
	border-radius: 8px;
	border: 2px dashed var(--brown-line);
	background: rgba(255, 255, 255, 0.25);
}

.empty-slot.foe {
	width: var(--foe-card-w);
	height: var(--foe-card-h);
}

.empty-slot.own {
	width: var(--own-card-w);
	height: var(--own-card-h);
}

.empty-slot.center {
	width: 86px;
	height: 122px;
}

.empty-slot.pile {
	width: 69px;
	height: 98px;
}

/* ---------------------------------------------------------- table center */
.table-center {
	position: absolute;
	left: 0;
	right: 0;
	top: 228px;
	height: 176px;
	display: flex;
	align-items: flex-start;
	justify-content: center;
	gap: 20px;
	z-index: 13;
}

.center-tray {
	position: absolute;
	left: 50%;
	top: -10px;
	transform: translateX(-50%);
	width: 310px;
	height: 130px;
	border-radius: 20px;
	background: linear-gradient(180deg, rgba(109, 74, 44, 0.62), rgba(60, 40, 24, 0.7));
	border: 2px solid rgba(253, 250, 242, 0.32);
	box-shadow: inset 0 2px 12px rgba(60, 40, 24, 0.5), 0 4px 12px rgba(60, 40, 24, 0.35);
	z-index: -1;
}

.pile {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 5px;
	padding: 6px;
	border: 2px solid transparent;
	border-radius: 16px;
	background: transparent;
	transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.pile.deck {
	position: relative;
	left: 70px;
}

.pile.discard {
	position: relative;
	left: -70px;
}

.pile.deck .pile-label {
	position: absolute;
	top: 50%;
	right: 100%;
	margin-right: 15px;
	transform: translateY(-50%);
	white-space: nowrap;
}

.pile.discard .pile-label {
	position: absolute;
	top: 50%;
	left: 100%;
	margin-left: 15px;
	transform: translateY(-50%);
	white-space: nowrap;
}

.pile.live {
	cursor: pointer;
	border-color: var(--orange);
	box-shadow: 0 0 0 3px rgba(245, 172, 106, 0.35);
	animation: pile-pulse 1.2s ease-in-out infinite;
}

.pile.live:active {
	transform: none;
}

.pile.on {
	border-color: var(--coral-deep);
	box-shadow: 0 0 0 3px rgba(226, 112, 92, 0.5);
	animation: none;
}

.pile[disabled] {
	cursor: default;
}

@keyframes pile-pulse {
	0%,
	100% {
		box-shadow: 0 0 0 3px rgba(245, 172, 106, 0.35);
	}
	50% {
		box-shadow: 0 0 0 7px rgba(245, 172, 106, 0.12);
	}
}

.pile-anchor {
	width: 83px;
	height: 98px;
	display: flex;
	align-items: center;
	justify-content: center;
	transform: scale(0.9);
}

.pile-anchor.discard {
	width: 74px;
	height: 98px;
}

.pile-img {
	width: auto;
	height: 98px;
	object-fit: contain;
	filter: drop-shadow(0 4px 6px rgba(109, 74, 44, 0.3));
}

.pile-label {
	display: flex;
	flex-direction: column;
	align-items: center;
	line-height: 1.15;
	font-size: var(--font-mini);
	font-weight: 700;
	color: var(--cream);
	background: var(--brown-deep);
	border: 1px solid rgba(253, 250, 242, 0.3);
	box-shadow: 0 2px 6px rgba(60, 40, 24, 0.45);
	padding: 3px 10px;
	border-radius: 12px;
}

.pile-count {
	font-size: 15px;
	font-weight: 900;
	color: var(--yellow);
}

.pile-hint {
	font-size: var(--font-mini);
	font-weight: 800;
	color: #fff;
	background: var(--orange);
	padding: 2px 10px;
	border-radius: 999px;
}

.middle {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 8px;
	width: 200px;
}

.drawn-area {
	height: 130px;
	display: flex;
	align-items: center;
	justify-content: center;
	margin-top: -10px;
	transform: scale(0.9);
}

.drawn-placeholder {
	width: 86px;
	height: 122px;
	border-radius: 10px;
	border: 2px dashed var(--brown-line);
	background: rgba(255, 255, 255, 0.2);
	display: flex;
	align-items: center;
	justify-content: center;
	text-align: center;
	font-size: var(--font-mini);
	color: var(--ink-soft);
	line-height: 1.6;
}

.op-area {
	min-height: 40px;
	width: max-content;
	max-width: 460px;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 6px;
	position: relative;
	z-index: 15;
}

.op-area .btn.compact {
	height: 33px;
	min-width: 84px;
	padding: 0 12px;
}

.op-tip {
	max-width: 340px;
	padding: 6px 14px;
	border-radius: 14px;
	background: var(--coral);
	color: #fff;
	font-size: var(--font-mini);
	font-weight: 700;
	line-height: 1.4;
	text-align: center;
}

.op-tip.act {
	background: var(--sage-deep);
}

.op-side-tip {
	position: absolute;
	right: 8px;
	top: 356px;
	width: 190px;
	padding: 8px 12px;
	border-radius: 14px;
	background: var(--coral);
	color: #fff;
	font-size: var(--font-mini);
	font-weight: 700;
	line-height: 1.4;
	text-align: center;
	box-shadow: var(--shadow-soft);
	z-index: 15;
}

.op-side-tip.act {
	background: var(--sage-deep);
}

.op-row {
	display: flex;
	align-items: center;
	gap: 8px;
	flex-wrap: nowrap;
	white-space: nowrap;
	justify-content: center;
}

.btn.compact {
	min-width: 96px;
	height: 46px;
	padding: 0 14px;
	font-size: var(--font-hint);
}

.btn.compact.on {
	background: var(--orange);
	color: #7a4a20;
}

/* ----------------------------------------------------- own corner & tools */
.own-corner {
	position: absolute;
	left: 12px;
	bottom: 10px;
	display: flex;
	flex-direction: column;
	gap: 8px;
	z-index: 14;
}

.own-head {
	position: relative;
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 6px 12px 6px 8px;
	border-radius: 16px;
	background: rgba(253, 250, 242, 0.9);
	box-shadow: var(--shadow-soft);
}

.avatar-edit {
	position: relative;
	padding: 0;
	border: none;
	background: transparent;
	border-radius: 50%;
	cursor: pointer;
	line-height: 0;
}

.avatar-edit-badge {
	position: absolute;
	right: -3px;
	bottom: -3px;
	width: 18px;
	height: 18px;
	border-radius: 50%;
	background: var(--sage-deep);
	color: #fff;
	font-size: 11px;
	display: flex;
	align-items: center;
	justify-content: center;
	box-shadow: 0 0 0 2px rgba(253, 250, 242, 0.95);
}

.tool-row {
	display: flex;
	gap: 8px;
}

.tool {
	width: 42px;
	height: 42px;
	flex: none;
	border-radius: 50%;
	border: 2px solid var(--brown-line);
	background: rgba(253, 250, 242, 0.92);
	font-size: 20px;
	line-height: 1;
	display: flex;
	align-items: center;
	justify-content: center;
	box-shadow: var(--shadow-soft);
}

.tool.on {
	background: var(--sage-deep);
	border-color: var(--sage-deep);
	box-shadow: 0 0 0 3px rgba(134, 169, 107, 0.4);
}

.own-name {
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
}

/* -------------------------------------------------------------- own hand */
.own-area {
	position: absolute;
	left: 50%;
	bottom: 8px;
	transform: translateX(-50%);
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 6px;
	z-index: 12;
}

.own-label {
	font-size: var(--font-mini);
	font-weight: 800;
	color: var(--brown-deep);
	background: rgba(253, 250, 242, 0.85);
	padding: 2px 16px;
	border-radius: 999px;
}

.own-hand {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 14px;
	transform: scale(0.84);
	transform-origin: center bottom;
}

.own-hand.mid {
	gap: 10px;
}

.own-hand.tight {
	gap: 7px;
}

.slot-index {
	position: absolute;
	left: 50%;
	top: -14px;
	transform: translateX(-50%);
	font-size: 12px;
	color: var(--ink-soft);
}

/* --------------------------------------------------------- right SHABO */
.shabo-side {
	position: absolute;
	right: 16px;
	top: 429px;
	width: 158px;
	height: 68px;
	display: flex;
	align-items: center;
	justify-content: center;
	border-radius: 999px;
	background: rgba(253, 250, 242, 0.72);
	box-shadow: var(--shadow-soft);
	z-index: 14;
}

.shabo-side img {
	width: 148px;
	object-fit: contain;
}

.shabo-side[disabled] {
	filter: grayscale(0.7);
	opacity: 0.5;
	pointer-events: none;
}

/* ---------------------------------------------------------------- extras */
.peek-tip {
	position: absolute;
	left: 50%;
	bottom: 139px;
	transform: translateX(-50%);
	padding: 8px 20px;
	border-radius: 999px;
	background: var(--coral);
	color: #fff;
	font-size: var(--font-hint);
	font-weight: 700;
	z-index: 18;
}

.cabo-call {
	position: absolute;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(253, 250, 242, 0.45);
	z-index: 60;
	pointer-events: none;
}

.cabo-card {
	display: flex;
	align-items: center;
	gap: 18px;
	padding: 18px 30px;
	border-radius: 26px;
	border: 4px solid var(--coral-deep);
	background: rgba(253, 250, 242, 0.96);
	box-shadow: 0 12px 30px rgba(109, 74, 44, 0.32);
	animation: pop 0.6s ease;
}

.cabo-text {
	display: flex;
	flex-direction: column;
	gap: 2px;
	text-align: left;
}

.cabo-who {
	font-size: 26px;
	font-weight: 800;
	color: var(--brown-deep);
}

.cabo-say {
	font-size: 46px;
	font-weight: 900;
	line-height: 1.1;
	color: var(--coral-deep);
	letter-spacing: 2px;
	animation: shout-text 0.6s ease infinite alternate;
}

.cabo-note {
	font-size: var(--font-hint);
	color: var(--ink-soft);
}

@keyframes pop {
	0% {
		transform: scale(0.4);
		opacity: 0;
	}
	30% {
		transform: scale(1.1);
		opacity: 1;
	}
	100% {
		transform: scale(1);
		opacity: 1;
	}
}

.log-panel {
	position: absolute;
	left: 50%;
	top: 64px;
	transform: translateX(-50%);
	width: 460px;
	max-height: 290px;
	padding: 12px 14px;
	font-size: var(--font-mini);
	color: var(--ink-soft);
	line-height: 1.8;
	z-index: 46;
}

.log-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 4px;
}

.log-close {
	width: 28px;
	height: 28px;
	border-radius: 50%;
	border: 2px solid var(--brown-line);
	background: var(--cream);
	color: var(--brown-deep);
	font-weight: 800;
}

.log-title {
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
	margin-bottom: 4px;
}

.rules-modal {
	width: 760px;
	max-height: 460px;
	padding: 16px 18px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.avatar-modal {
	width: 460px;
	max-width: 92%;
	padding: 16px 18px 20px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.avatar-grid {
	display: grid;
	grid-template-columns: repeat(5, 1fr);
	gap: 12px;
	max-height: 320px;
	overflow-y: auto;
	padding-right: 4px;
}

.avatar-pick {
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 6px;
	border-radius: 14px;
	border: 2px solid transparent;
	background: rgba(253, 250, 242, 0.7);
	cursor: pointer;
}

.avatar-pick.on {
	border-color: var(--sage-deep);
	box-shadow: 0 0 0 3px rgba(134, 169, 107, 0.4);
}

.rules-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.rules-title {
	font-size: var(--font-title);
	font-weight: 800;
	color: var(--brown-deep);
	letter-spacing: 2px;
}

.rules-body {
	min-height: 0;
	overflow-y: auto;
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	gap: 10px;
	align-content: start;
	padding-right: 4px;
}

.rules-card {
	padding: 10px 14px;
	border-radius: 14px;
	background: rgba(247, 239, 223, 0.9);
}

.rules-card-title {
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
	margin-bottom: 4px;
}

.rules-line {
	margin: 2px 0;
	font-size: 14px;
	line-height: 1.6;
	color: var(--ink-soft);
}

.fly-layer {
	position: absolute;
	inset: 0;
	pointer-events: none;
	z-index: 50;
}

.flight {
	position: absolute;
	transform-origin: center center;
	transition-property: left, top, transform;
	transition-timing-function: cubic-bezier(0.3, 0.7, 0.3, 1);
}

/* --------------------------------------------------------------- result */
.result {
	width: 720px;
	max-height: 480px;
	padding: 18px;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 12px;
}

.result-rows {
	width: 100%;
	display: flex;
	flex-direction: column;
	gap: 8px;
	overflow-y: auto;
	min-height: 0;
}

.shabo-hero {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 18px;
	padding: 10px 18px;
	border-radius: 20px;
	border: 3px solid var(--coral-deep);
	background: rgba(226, 112, 92, 0.16);
	animation: pop 0.6s ease;
}

.hero-avatar {
	position: relative;
	flex: none;
}

.hero-stamp {
	position: absolute;
	left: 50%;
	bottom: -10px;
	transform: translateX(-50%) rotate(-6deg);
	padding: 2px 10px;
	border-radius: 999px;
	background: var(--coral-deep);
	color: #fff;
	font-size: 12px;
	font-weight: 800;
	white-space: nowrap;
}

.hero-text {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 2px;
	text-align: left;
}

.hero-label {
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown-deep);
}

.hero-name {
	font-size: 38px;
	font-weight: 900;
	line-height: 1.2;
	color: var(--coral-deep);
	animation: shout-text 0.8s ease infinite alternate;
}

.hero-note {
	font-size: var(--font-mini);
	color: var(--ink-soft);
}

.result-row.shabo {
	background: rgba(226, 112, 92, 0.3);
}

.result-row {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 6px 10px;
	border-radius: 14px;
	background: rgba(247, 239, 223, 0.9);
}

.result-row.win {
	background: var(--sage);
}

.result-name {
	width: 104px;
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown-deep);
}

.caller-tag {
	margin-left: 4px;
	padding: 1px 6px;
	border-radius: 999px;
	background: var(--coral);
	color: #fff;
	font-size: 11px;
}

.kamikaze-tag {
	margin-left: 4px;
	padding: 1px 6px;
	border-radius: 999px;
	background: var(--brown-deep);
	color: var(--yellow);
	font-size: 11px;
	font-weight: 800;
}

.result-cards {
	display: flex;
	gap: 4px;
	flex: 1;
}

.reveal-card :deep(.flipper) {
	transition: transform 1s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.result-score .running {
	font-size: 20px;
	font-weight: 900;
	color: var(--coral-deep);
}

.result-total.pending {
	opacity: 0.35;
}

.settle-banner {
	position: absolute;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(60, 40, 24, 0.55);
	z-index: 70;
}

.settle-word {
	padding: 18px 54px;
	border-radius: 20px;
	background: linear-gradient(135deg, var(--coral), var(--orange));
	color: #fff;
	font-size: 40px;
	font-weight: 900;
	letter-spacing: 6px;
	box-shadow: 0 10px 30px rgba(60, 40, 24, 0.45);
	animation: settle-pop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes settle-pop {
	0% {
		transform: scale(0.6);
		opacity: 0;
	}
	100% {
		transform: scale(1);
		opacity: 1;
	}
}

.result-score {
	width: 120px;
	text-align: right;
	font-size: var(--font-hint);
	color: var(--ink);
}

.penalty {
	color: var(--coral-deep);
	font-weight: 700;
}

.result-total {
	width: 80px;
	text-align: right;
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
}

.result-actions {
	display: flex;
	gap: 14px;
	align-items: center;
}

/* --------------------------------------------------- chat, emotes, SHABO */
.called {
	margin-left: 4px;
	padding: 0 5px;
	border-radius: 999px;
	background: var(--coral);
	color: #fff;
	font-size: 11px;
	font-weight: 800;
}

.bubble {
	position: absolute;
	top: 2px;
	width: max-content;
	max-width: 240px;
	padding: 7px 11px;
	border-radius: 16px;
	background: rgba(253, 250, 242, 0.97);
	border: 2px solid var(--brown-line);
	color: var(--brown-deep);
	font-size: var(--font-hint);
	font-weight: 700;
	line-height: 1.4;
	white-space: pre-wrap;
	word-break: break-word;
	pointer-events: none;
	z-index: 95;
}

/* 小箭头用旋转正方形实现：与气泡同色填充，只在外露的两条边描边，
   衔接气泡的那两条边不描边；方块压入气泡内的部分控制在描边范围内，避免盖住文字/表情 */
.bubble:not(.own-bubble)::before {
	content: '';
	position: absolute;
	top: 11px;
	width: 12px;
	height: 12px;
	background: rgba(253, 250, 242, 0.97);
	pointer-events: none;
}

.bubble.right {
	left: calc(100% + 10px);
	box-shadow: -7px 5px 8px -10px rgba(78, 50, 27, 0.6), var(--shadow-float);
}

.bubble.right::before {
	left: -8px;
	border-bottom: 2px solid var(--brown-line);
	border-left: 2px solid var(--brown-line);
	border-bottom-left-radius: 3px;
	transform: rotate(45deg);
}

.bubble.left {
	right: calc(100% + 10px);
	box-shadow: 7px 5px 8px -10px rgba(78, 50, 27, 0.6), var(--shadow-float);
}

.bubble.left::before {
	right: -8px;
	border-top: 2px solid var(--brown-line);
	border-right: 2px solid var(--brown-line);
	border-top-right-radius: 3px;
	transform: rotate(45deg);
}

.bubble.own-bubble {
	left: 14px;
	top: auto;
	bottom: 128px;
	z-index: 95;
	box-shadow: var(--shadow-float);
}

.bubble-emoji {
	display: block;
	width: 56px;
	height: 56px;
	object-fit: contain;
}

.bubble-enter-active {
	transition: transform 0.24s cubic-bezier(0.2, 1.5, 0.4, 1), opacity 0.2s ease;
}

.bubble-leave-active {
	transition: transform 0.18s ease, opacity 0.18s ease;
}

.bubble-enter-from {
	opacity: 0;
	transform: scale(0.5) translateY(10px);
}

.bubble-leave-to {
	opacity: 0;
	transform: scale(0.85);
}

.shabo-stamp {
	position: absolute;
	left: 50%;
	top: -12px;
	transform: translateX(-50%);
	padding: 4px 14px;
	border-radius: 999px;
	background: var(--coral);
	color: #fff;
	font-size: 20px;
	font-weight: 900;
	letter-spacing: 1px;
	white-space: nowrap;
	text-shadow: 0 2px 0 rgba(109, 74, 44, 0.45);
	box-shadow: 0 0 0 4px rgba(226, 112, 92, 0.35), 0 6px 14px rgba(109, 74, 44, 0.4);
	animation: shout 0.6s ease-in-out infinite alternate;
	z-index: 38;
	pointer-events: none;
}

.shabo-stamp.own {
	top: -18px;
	font-size: 22px;
}

/* 文本类元素位于正常文档流中，不能带 translateX 位移，否则会整体偏左 */
@keyframes shout-text {
	from {
		transform: scale(1) rotate(-3deg);
	}
	to {
		transform: scale(1.1) rotate(3deg);
	}
}

@keyframes shout {
	from {
		transform: translateX(-50%) scale(1) rotate(-4deg);
	}
	to {
		transform: translateX(-50%) scale(1.14) rotate(4deg);
	}
}

.stamp-enter-active {
	animation: stamp-in 0.42s cubic-bezier(0.2, 1.6, 0.4, 1);
}

.stamp-leave-active {
	transition: opacity 0.3s ease, transform 0.3s ease;
}

.stamp-leave-to {
	opacity: 0;
	transform: translateX(-50%) scale(1.6);
}

@keyframes stamp-in {
	0% {
		opacity: 0;
		transform: translateX(-50%) scale(2.6) rotate(-14deg);
	}
	70% {
		opacity: 1;
		transform: translateX(-50%) scale(0.92) rotate(3deg);
	}
	100% {
		opacity: 1;
		transform: translateX(-50%) scale(1);
	}
}

.chat-pop {
	position: absolute;
	left: 12px;
	bottom: 128px;
	width: 320px;
	padding: 12px;
	display: flex;
	flex-direction: column;
	gap: 8px;
	z-index: 44;
}

.pop-title {
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
}

.phrase-grid {
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	gap: 6px;
}

.phrase {
	height: 40px;
	border-radius: 12px;
	background: var(--paper);
	border: 2px solid var(--brown-line);
	color: var(--brown-deep);
	font-size: var(--font-mini);
	font-weight: 700;
}

.chat-input-row {
	display: flex;
	gap: 6px;
}

.chat-input-row input {
	flex: 1;
	height: 44px;
	padding: 0 12px;
	border-radius: 12px;
	border: 2px solid var(--brown-line);
	background: #fff;
	font-size: var(--font-hint);
	color: var(--ink);
}

.chat-input-row .btn.compact {
	min-width: 80px;
	height: 44px;
}

.emoji-pop {
	position: absolute;
	left: 12px;
	bottom: 128px;
	width: 300px;
	padding: 10px;
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 4px;
	z-index: 44;
}

.emoji-btn {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 2px;
	padding: 4px 0;
	border-radius: 12px;
	background: transparent;
}

.emoji-btn:active {
	background: var(--paper);
}

.emoji-btn img {
	width: 48px;
	height: 48px;
	object-fit: contain;
}

.pop-up-enter-active,
.pop-up-leave-active {
	transition: transform 0.2s ease, opacity 0.2s ease;
}

.pop-up-enter-from,
.pop-up-leave-to {
	opacity: 0;
	transform: translateY(12px) scale(0.94);
}
</style>
