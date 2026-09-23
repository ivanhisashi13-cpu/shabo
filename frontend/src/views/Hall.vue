<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import Avatar from '../components/Avatar.vue'
import { emoteSrc } from '../data/emotes'
import { useAuthStore } from '../store/auth'
import { useGameStore } from '../store/game'

const auth = useAuthStore()
const game = useGameStore()
const router = useRouter()

const dialog = ref('')
const joinCode = ref('')
const inviteId = ref('')
const chatText = ref('')
const showProfile = ref(false)
const nickDraft = ref('')
const avatarDraft = ref('')
const savingProfile = ref(false)
const statsData = ref(null)
const statsLoading = ref(false)
const showRank = ref(false)
const rankLoading = ref(false)
const rankBoards = ref(null)
const rankSeason = ref('')
const rankTab = ref('wins')
const badgeZoom = ref('')

const RANK_TABS = [
	{ key: 'wins', label: '胜场榜', unit: '胜', badge: '/art/shabo_champion_badge_s1.png' },
	{ key: 'low', label: '极限榜', unit: '分', badge: '/art/shabo_geek_badge_s1.png' },
	{ key: 'shabo', label: '傻波榜', unit: '次', badge: '/art/shabo_king_badge_s1.png' }
]

const QUICK_CHAT = ['开局！', '快点呀', '我准备好了', '这把稳了', '手滑了…', '再来一局']

const room = computed(() => game.room)
const members = computed(() => (room.value ? room.value.members : []))
const me = computed(() => members.value.find((item) => item.user_id === auth.myId) || null)
const isHost = computed(() => Boolean(room.value && room.value.host_user_id === auth.myId))
const isAdmin = computed(() => Boolean(auth.user && auth.user.is_admin))
const canManageBots = computed(
	() => isAdmin.value && isHost.value && Boolean(room.value) && room.value.status === 'waiting'
)
const canAddBot = computed(() => canManageBots.value && members.value.length < room.value.max_players)

function addBot() {
	game.send('add_bot')
}

function removeBot(botId) {
	game.send('remove_bot', { bot_id: botId })
}

function canKick(item) {
	return Boolean(
		isHost.value &&
		room.value &&
		room.value.status === 'waiting' &&
		!item.is_bot &&
		item.user_id !== auth.myId
	)
}

function kickMember(item) {
	game.send('kick', { user_id: item.user_id })
}

function createRoom() {
	game.send('create_room', { max_players: 5, mode: 'MULTI' })
	dialog.value = ''
}

function joinRoom() {
	const code = joinCode.value.trim()
	if (code.length !== 6) {
		game.showToast('请输入 6 位房间号')
		return
	}
	game.send('join_room', { code })
	dialog.value = ''
	joinCode.value = ''
}

function invite() {
	const target = inviteId.value.trim()
	if (!target) {
		game.showToast('请输入对方用户ID')
		return
	}
	game.send('invite', { user_id: target })
	dialog.value = ''
	inviteId.value = ''
}

function toggleReady() {
	game.send('ready', { ready: !(me.value && me.value.ready) })
}

function sendChat(text) {
	const value = (text || chatText.value).trim()
	if (!value) return
	game.send('chat', { text: value })
	chatText.value = ''
}

function copyCode() {
	if (!room.value) return
	navigator.clipboard?.writeText(room.value.code)
	game.showToast('房间号已复制', 'ok')
}

function logout() {
	auth.logout()
	router.push({ name: 'login' })
}

async function openProfile() {
	await auth.loadAvatars()
	nickDraft.value = auth.user?.nickname || ''
	avatarDraft.value = auth.user?.avatar || ''
	showProfile.value = true
}

function onMemberClick(item) {
	if (item.is_bot) {
		game.showToast('机器人没有战绩')
		return
	}
	openStats(item)
}

async function openStats(item) {
	statsData.value = { nickname: item.nickname, avatar: item.avatar, loading: true }
	statsLoading.value = true
	try {
		const data = await auth.fetchStats(item.user_id)
		statsData.value = data
	} catch (error) {
		game.showToast('战绩加载失败')
		statsData.value = null
	} finally {
		statsLoading.value = false
	}
}

function openMyStats() {
	openStats({ user_id: auth.myId, nickname: auth.user?.nickname, avatar: auth.user?.avatar })
}

const currentBoard = computed(() => (rankBoards.value ? rankBoards.value[rankTab.value] : null))
const currentTab = computed(() => RANK_TABS.find((tab) => tab.key === rankTab.value) || RANK_TABS[0])
const currentUnit = computed(() => currentTab.value.unit || '')
const meInTop = computed(() => {
	const board = currentBoard.value
	if (!board || !board.me) return false
	return board.top.some((row) => row.user_id === board.me.user_id)
})

async function openRank() {
	showRank.value = true
	rankLoading.value = true
	try {
		const data = await auth.fetchLeaderboard()
		rankBoards.value = data.boards
		rankSeason.value = data.season
	} catch (error) {
		game.showToast('排行榜加载失败')
		showRank.value = false
	} finally {
		rankLoading.value = false
	}
}

async function saveProfile() {
	const nickname = nickDraft.value.trim()
	if (nickname.length < 2 || nickname.length > 12) {
		game.showToast('昵称需 2-12 个字符')
		return
	}
	savingProfile.value = true
	try {
		await auth.updateProfile({ nickname, avatar: avatarDraft.value })
		if (game.room) game.send('sync')
		if (statsData.value && statsData.value.user_id === auth.myId) {
			statsData.value = { ...statsData.value, nickname, avatar: avatarDraft.value }
		}
		showProfile.value = false
	} catch (error) {
		game.showToast('保存失败，请重试')
	} finally {
		savingProfile.value = false
	}
}
</script>

<template>
	<div class="screen hall">
		<div class="topbar">
			<button class="round" @click="logout">←</button>
			<div class="page-title">房间大厅</div>
				<div class="top-right">
					<button class="round" title="排行榜" @click="openRank">榜</button>
					<button class="round" @click="router.push({ name: 'rules' })">?</button>
				<button class="me" title="查看我的战绩" @click="openMyStats">
					<Avatar :avatar="auth.user?.avatar" :size="40" />
					<div class="me-text">
						<div class="me-name">{{ auth.user?.nickname }}</div>
						<div class="mini">ID {{ auth.myId }}</div>
					</div>
				</button>
			</div>
		</div>

		<div class="columns">
			<div class="col-left panel">
				<div class="col-head">
					<span>玩家列表</span>
					<span class="mini">{{ members.length }}/{{ room ? room.max_players : '-' }}</span>
				</div>
				<div class="list scroll">
					<div
						v-for="item in members"
						:key="item.user_id"
						class="member"
						:class="{ mine: item.user_id === auth.myId, ready: item.ready, editable: !item.is_bot }"
						@click="onMemberClick(item)"
					>
						<Avatar :avatar="item.avatar" :size="42" :offline="!item.online" />
						<div class="member-text">
							<div class="member-name">
								{{ item.nickname }}
								<span v-if="item.user_id === room?.host_user_id" class="host-tag">房主</span>
								<span v-if="item.is_bot" class="bot-tag">机器人</span>
							</div>
							<div class="mini">ID {{ item.user_id }}</div>
						</div>
						<button v-if="item.is_bot && canManageBots" class="bot-remove" @click.stop="removeBot(item.user_id)">×</button>
						<template v-else>
							<span class="state" :class="{ on: item.ready }">{{ item.ready ? '已准备' : '等待中' }}</span>
							<button v-if="canKick(item)" class="kick-btn" title="移出房间" @click.stop="kickMember(item)">踢</button>
						</template>
					</div>
					<div v-if="!members.length" class="empty hint">还没有加入房间<br />先创建或加入一个房间吧</div>
				</div>
			</div>

			<div class="col-center panel">
				<div class="center-title">房间信息</div>
				<template v-if="room">
					<div class="code-label hint">房间号</div>
					<button class="code" @click="copyCode">{{ room.code }}</button>
					<div class="hint">点击复制 · {{ room.mode === 'MULTI' ? '累计赛（先到 100 分结束）' : '单局赛' }}</div>
					<div class="counter">玩家 {{ members.length }}/{{ room.max_players }}</div>
					<div class="chatbox scroll">
						<div v-for="(line, index) in room.chat" :key="index" class="chat-line">
							<b>{{ line.nickname }}</b>：
							<img v-if="line.kind === 'emoji'" class="chat-emoji" :src="emoteSrc(line.text)" alt="" />
							<template v-else>{{ line.text }}</template>
						</div>
					</div>
				</template>
				<div v-else class="no-room">
					<img class="logo" src="/art/shabo_logo.png" alt="SHABO" />
					<div class="hint">SHABO 傻波儿 · 2-5 人记忆卡牌对战</div>
				</div>
			</div>

			<div class="col-right">
				<button class="btn yellow full" @click="createRoom">＋ 创建房间</button>
				<button class="btn full" @click="dialog = 'join'">＋ 加入房间</button>
				<button class="btn ghost full" :disabled="!room" @click="dialog = 'invite'">邀请ID</button>
				<button v-if="isAdmin" class="btn orange full" :disabled="!canAddBot" @click="addBot">＋ 添加机器人</button>
				<button
					class="btn orange full"
					:disabled="!room || isHost"
					@click="toggleReady"
				>
					{{ me && me.ready ? '取消准备' : '准备' }}
				</button>
				<button
					class="btn green full"
					:disabled="!room || !isHost || !room.can_start"
					@click="game.send('start_game')"
				>
					开局
				</button>
				<button class="btn ghost full small" :disabled="!room" @click="game.send('leave_room')">退出房间</button>
			</div>
		</div>

		<div class="chatbar">
			<button v-for="text in QUICK_CHAT" :key="text" class="quick" :disabled="!room" @click="sendChat(text)">
				{{ text }}
			</button>
			<input v-model="chatText" class="input chat-input" placeholder="说点什么…" maxlength="60" @keyup.enter="sendChat()" />
		</div>

			<div v-if="dialog" class="mask" @click.self="dialog = ''">
				<div class="panel dialog">
					<template v-if="dialog === 'join'">
					<div class="title">加入房间</div>
					<input v-model="joinCode" class="input code-input" placeholder="6 位房间号" maxlength="6" inputmode="numeric" />
					<div class="dialog-actions">
						<button class="btn green" @click="joinRoom">加入</button>
						<button class="btn ghost" @click="dialog = ''">取消</button>
					</div>
				</template>

				<template v-else>
					<div class="title">邀请好友</div>
					<input v-model="inviteId" class="input code-input" placeholder="对方用户ID" maxlength="20" />
					<div class="dialog-actions">
						<button class="btn green" @click="invite">发送邀请</button>
						<button class="btn ghost" @click="dialog = ''">取消</button>
					</div>
				</template>
				</div>
			</div>

			<div v-if="showRank" class="mask" @click.self="showRank = false">
				<div class="panel dialog rank-dialog">
					<div class="rank-reward">
						<div class="reward-title">赛季奖励</div>
						<div class="reward-note">每赛季各榜第一名<br />可获得专属徽章</div>
						<div class="reward-item">
							<img
								class="reward-badge"
								:src="currentTab.badge"
								:alt="currentTab.label"
								title="点击查看大图"
								@click="badgeZoom = currentTab.badge"
							/>
							<div class="reward-label">{{ currentTab.label }}冠军</div>
						</div>
					</div>
					<div class="rank-main">
						<div class="rank-head">
							<div class="title">排行榜<span v-if="rankSeason" class="rank-season">{{ rankSeason }} 赛季</span></div>
							<button class="log-close" @click="showRank = false">×</button>
						</div>
						<div class="rank-tabs">
							<button
								v-for="tab in RANK_TABS"
								:key="tab.key"
								class="rank-tab"
								:class="{ on: rankTab === tab.key }"
								@click="rankTab = tab.key"
							>
								{{ tab.label }}
							</button>
						</div>
						<div v-if="rankLoading" class="hint">加载中…</div>
						<template v-else-if="currentBoard">
							<div class="rank-list scroll">
								<div
									v-for="row in currentBoard.top"
									:key="row.user_id"
									class="rank-row"
									:class="{ mine: row.user_id === auth.myId, top3: row.rank <= 3 }"
								>
									<div class="rank-no" :class="`r${row.rank <= 3 ? row.rank : 0}`">{{ row.rank }}</div>
									<Avatar :avatar="row.avatar" :size="34" />
								<div class="rank-name">{{ row.nickname }}</div>
								<div class="rank-value">{{ row.value }}<span class="rank-unit">{{ currentUnit }}</span></div>
								</div>
								<div v-if="!currentBoard.top.length" class="empty hint">暂时还没有上榜的玩家</div>
							</div>
							<div v-if="currentBoard.me && !meInTop" class="rank-row mine me-fixed">
								<div class="rank-no">{{ currentBoard.me.rank }}</div>
								<Avatar :avatar="currentBoard.me.avatar" :size="34" />
								<div class="rank-name">{{ currentBoard.me.nickname }}</div>
								<div class="rank-value">{{ currentBoard.me.value }}<span class="rank-unit">{{ currentUnit }}</span></div>
							</div>
							<div v-else-if="!currentBoard.me" class="hint me-note">你还没有该榜单的记录</div>
						</template>
					</div>
				</div>
			</div>

			<div v-if="badgeZoom" class="mask badge-zoom" @click="badgeZoom = ''">
				<img class="badge-zoom-img" :src="badgeZoom" alt="专属徽章" />
			</div>

			<div v-if="statsData" class="mask" @click.self="statsData = null">
				<div class="panel dialog stats-dialog">
					<div class="stats-head">
						<Avatar :avatar="statsData.avatar" :size="56" />
						<div class="stats-name">{{ statsData.nickname }}</div>
					</div>
					<div v-if="statsLoading" class="hint">加载中…</div>
					<template v-else>
						<div class="stats-section-title">
							生涯战绩
							<span v-if="statsData.season" class="season-tag">本赛季 {{ statsData.season.key }}</span>
						</div>
						<div class="stats-grid three">
							<div class="stat-cell">
								<div class="stat-num">{{ statsData.games_won }}</div>
								<div class="stat-label">生涯胜场</div>
							</div>
							<div class="stat-cell">
								<div class="stat-num shabo">{{ statsData.shabo_count }}</div>
								<div class="stat-label">成为傻波次数</div>
							</div>
							<div class="stat-cell">
								<div class="stat-num">{{ statsData.best_multi_score == null ? '—' : statsData.best_multi_score }}</div>
								<div class="stat-label">生涯最低分</div>
							</div>
						</div>
						<div v-if="statsData.season" class="season-line">
							本赛季：胜场 <b>{{ statsData.season.wins }}</b> · 傻波 <b>{{ statsData.season.shabo_count }}</b> ·
							最低分 <b>{{ statsData.season.best_multi_score == null ? '—' : statsData.season.best_multi_score }}</b>
						</div>
						<div class="stats-section-title">历史赛季排名</div>
						<div class="history-list scroll">
							<div v-for="row in statsData.history" :key="row.season" class="history-row">
								<span class="history-season">{{ row.season }}</span>
								<span class="history-cell">胜场 {{ row.wins_rank ? '#' + row.wins_rank : '—' }}<i>({{ row.wins }})</i></span>
								<span class="history-cell">最低 {{ row.low_rank ? '#' + row.low_rank : '—' }}<i>({{ row.best_multi_score == null ? '—' : row.best_multi_score }})</i></span>
								<span class="history-cell">傻波 {{ row.shabo_rank ? '#' + row.shabo_rank : '—' }}<i>({{ row.shabo_count }})</i></span>
							</div>
							<div v-if="!statsData.history || !statsData.history.length" class="empty hint">还没有历史赛季记录</div>
						</div>
					</template>
					<div class="dialog-actions">
						<button v-if="statsData.user_id === auth.myId" class="btn green" @click="openProfile">修改资料</button>
						<button class="btn ghost" @click="statsData = null">关闭</button>
					</div>
				</div>
			</div>

			<div v-if="showProfile" class="mask" @click.self="showProfile = false">
				<div class="panel dialog profile-dialog">
					<div class="title">修改资料</div>
					<input
						v-model="nickDraft"
						class="input"
						placeholder="昵称 2-12 个字符"
						maxlength="12"
						@keyup.enter="saveProfile"
					/>
					<div class="avatar-grid scroll">
						<button
							v-for="item in auth.avatars"
							:key="item"
							class="avatar-pick"
							:class="{ on: item === avatarDraft }"
							@click="avatarDraft = item"
						>
							<Avatar :avatar="item" :size="48" />
						</button>
					</div>
					<div class="dialog-actions">
						<button class="btn green" :disabled="savingProfile" @click="saveProfile">保存</button>
						<button class="btn ghost" @click="showProfile = false">取消</button>
					</div>
				</div>
			</div>
		</div>
	</template>

<style scoped>
.hall {
	background: var(--paper);
	display: flex;
	flex-direction: column;
	padding: 10px 16px 12px;
	gap: 8px;
}

.topbar {
	display: flex;
	align-items: center;
	height: 52px;
	flex: none;
}

.round {
	width: 48px;
	height: 48px;
	border-radius: 50%;
	background: var(--cream);
	border: 2px solid var(--brown-line);
	font-size: 20px;
	font-weight: 800;
	color: var(--brown-deep);
}

.page-title {
	flex: 1;
	text-align: center;
	font-size: var(--font-title);
	font-weight: 800;
	color: var(--brown-deep);
	letter-spacing: 4px;
}

.top-right {
	display: flex;
	align-items: center;
	gap: 10px;
}

.me {
	display: flex;
	align-items: center;
	gap: 8px;
	background: none;
	border: none;
	padding: 2px;
	border-radius: 12px;
	cursor: pointer;
}

.me:hover {
	background: rgba(253, 250, 242, 0.6);
}

.member.editable {
	cursor: pointer;
}

.me-name {
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown-deep);
}

.columns {
	flex: 1;
	display: flex;
	gap: 12px;
	min-height: 0;
}

.col-left {
	width: 290px;
	flex: none;
	background: rgba(168, 201, 140, 0.4);
	display: flex;
	flex-direction: column;
	padding: 10px;
	gap: 8px;
}

.col-head {
	display: flex;
	justify-content: space-between;
	align-items: center;
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown-deep);
	padding: 0 6px;
}

.list {
	flex: 1;
	display: flex;
	flex-direction: column;
	gap: 8px;
	min-height: 0;
}

.member {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 6px 10px;
	border-radius: 14px;
	background: rgba(253, 250, 242, 0.85);
	min-height: 56px;
}

.member.ready {
	background: rgba(168, 201, 140, 0.85);
}

.member.mine {
	background: var(--coral);
	color: #fff;
}

.member.mine .mini {
	color: rgba(255, 255, 255, 0.85);
}

.member-text {
	flex: 1;
	min-width: 0;
}

.member-name {
	font-size: var(--font-hint);
	font-weight: 700;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.host-tag {
	margin-left: 6px;
	padding: 1px 6px;
	border-radius: 999px;
	background: var(--yellow);
	color: #7a4a20;
	font-size: 12px;
}

.bot-tag {
	margin-left: 6px;
	padding: 1px 6px;
	border-radius: 999px;
	background: var(--sage-deep);
	color: #fff;
	font-size: 12px;
}

.bot-remove {
	width: 26px;
	height: 26px;
	flex: none;
	border-radius: 50%;
	border: 2px solid var(--coral-deep);
	background: var(--cream);
	color: var(--coral-deep);
	font-size: 16px;
	font-weight: 800;
	line-height: 1;
}

.state {
	font-size: 12px;
	padding: 3px 8px;
	border-radius: 999px;
	background: rgba(255, 255, 255, 0.8);
	color: var(--ink-soft);
}

.state.on {
	background: var(--sage-deep);
	color: #fff;
}

.kick-btn {
	flex: none;
	height: 26px;
	padding: 0 10px;
	border-radius: 999px;
	border: 2px solid var(--coral-deep);
	background: var(--cream);
	color: var(--coral-deep);
	font-size: 12px;
	font-weight: 800;
	cursor: pointer;
}

.empty {
	text-align: center;
	padding-top: 40px;
	line-height: 1.8;
}

.col-center {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 12px;
	gap: 4px;
	min-width: 0;
}

.center-title {
	padding: 4px 22px;
	border-radius: 999px;
	background: var(--sage-deep);
	color: #fff;
	font-size: var(--font-hint);
	font-weight: 700;
	letter-spacing: 2px;
}

.code-label {
	margin-top: 6px;
}

.code {
	font-size: 44px;
	font-weight: 900;
	letter-spacing: 6px;
	color: var(--brown-deep);
	line-height: 1.1;
}

.counter {
	margin-top: 6px;
	padding: 6px 24px;
	border-radius: 999px;
	background: var(--coral);
	color: #fff;
	font-weight: 700;
	font-size: var(--font-hint);
}

.chatbox {
	margin-top: 8px;
	width: 100%;
	flex: 1;
	min-height: 0;
	border-top: 1px dashed var(--brown-line);
	padding-top: 6px;
	font-size: 14px;
	color: var(--ink-soft);
	line-height: 1.7;
}

.chat-line b {
	color: var(--brown);
}

.chat-emoji {
	width: 26px;
	height: 26px;
	vertical-align: middle;
	object-fit: contain;
}

.no-room {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 10px;
}

.no-room .logo {
	width: 170px;
}

.col-right {
	width: 200px;
	flex: none;
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 8px;
	border-radius: var(--radius-card);
	background: rgba(169, 120, 78, 0.35);
}

.full {
	width: 100%;
	min-width: 0;
	height: 50px;
}

.full.small {
	height: 44px;
}

.chatbar {
	flex: none;
	height: 52px;
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 0 10px;
	border-radius: 999px;
	background: rgba(169, 120, 78, 0.28);
}

.quick {
	height: 36px;
	padding: 0 14px;
	border-radius: 999px;
	background: var(--yellow);
	color: #7a4a20;
	font-size: 14px;
	font-weight: 700;
	flex: none;
}

.quick[disabled] {
	opacity: 0.45;
	pointer-events: none;
}

.chat-input {
	flex: 1;
	height: 38px;
}

.dialog {
	width: 460px;
	padding: 22px;
	display: flex;
	flex-direction: column;
	gap: 14px;
	align-items: center;
}

.dialog-row {
	display: flex;
	align-items: center;
	gap: 10px;
	width: 100%;
}

.dialog-label {
	width: 48px;
	font-size: var(--font-hint);
	color: var(--brown);
	font-weight: 700;
}

.chip {
	height: 44px;
	padding: 0 18px;
	border-radius: 999px;
	border: 2px solid var(--brown-line);
	background: var(--cream);
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown-deep);
}

.chip.on {
	background: var(--sage-deep);
	border-color: var(--sage-deep);
	color: #fff;
}

.code-input {
	width: 100%;
	text-align: center;
	letter-spacing: 6px;
	font-size: 22px;
	height: 56px;
}

.dialog-actions {
	display: flex;
	gap: 14px;
}

.profile-dialog .input {
	width: 100%;
	height: 48px;
	text-align: center;
	font-size: 18px;
}

.avatar-grid {
	width: 100%;
	display: grid;
	grid-template-columns: repeat(5, 1fr);
	gap: 10px;
	max-height: 240px;
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

.stats-dialog {
	width: 460px;
	align-items: flex-start;
	gap: 12px;
}

.stats-head {
	display: flex;
	align-items: center;
	gap: 12px;
}

.stats-name {
	font-size: var(--font-title);
	font-weight: 800;
	color: var(--brown-deep);
}

.stats-grid {
	width: 100%;
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 12px;
}

.stats-grid.three {
	grid-template-columns: 1fr 1fr 1fr;
}

.stats-section-title {
	width: 100%;
	display: flex;
	align-items: center;
	justify-content: space-between;
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
}

.season-tag {
	font-size: 12px;
	font-weight: 700;
	color: var(--sage-deep);
}

.season-line {
	width: 100%;
	font-size: var(--font-hint);
	color: var(--ink-soft);
	font-weight: 600;
}

.season-line b {
	color: var(--brown-deep);
}

.history-list {
	width: 100%;
	display: flex;
	flex-direction: column;
	gap: 6px;
	max-height: 180px;
	overflow-y: auto;
	padding-right: 4px;
}

.history-row {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 10px;
	border-radius: 10px;
	background: rgba(253, 250, 242, 0.85);
	font-size: 13px;
	font-weight: 700;
	color: var(--brown-deep);
}

.history-season {
	flex: none;
	width: 62px;
	color: var(--sage-deep);
}

.history-cell {
	flex: 1;
	white-space: nowrap;
}

.history-cell i {
	margin-left: 2px;
	font-style: normal;
	font-weight: 600;
	color: var(--ink-soft);
}

.rank-season {
	margin-left: 8px;
	font-size: 13px;
	font-weight: 700;
	color: var(--sage-deep);
}

.badge-zoom {
	cursor: zoom-out;
}

.badge-zoom-img {
	max-width: 70%;
	max-height: 80%;
	object-fit: contain;
	filter: drop-shadow(0 10px 30px rgba(0, 0, 0, 0.4));
}

.stat-cell {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 6px;
	padding: 16px 10px;
	border-radius: 16px;
	background: rgba(253, 250, 242, 0.85);
	border: 2px solid var(--brown-line);
}

.stat-num {
	font-size: 34px;
	font-weight: 900;
	color: var(--brown-deep);
	line-height: 1;
}

.stat-num.shabo {
	color: var(--coral-deep);
}

.stat-label {
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--ink-soft);
}

.rank-dialog {
	width: 760px;
	flex-direction: row;
	align-items: stretch;
	gap: 14px;
	padding: 18px;
}

.rank-reward {
	flex: none;
	width: 244px;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 10px;
	padding: 12px 10px;
	border-radius: 16px;
	background: rgba(169, 120, 78, 0.18);
	border: 2px solid var(--brown-line);
}

.reward-title {
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
	letter-spacing: 2px;
}

.reward-note {
	font-size: 12px;
	line-height: 1.5;
	text-align: center;
	color: var(--ink-soft);
	font-weight: 600;
}

.reward-item {
	width: 100%;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 8px;
	margin-top: 6px;
	padding: 14px 6px;
	border-radius: 14px;
	background: rgba(253, 250, 242, 0.85);
	border: 2px solid var(--brown-line);
}

.reward-badge {
	width: 192px;
	height: 192px;
	object-fit: contain;
	cursor: zoom-in;
}

.reward-label {
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
}

.rank-main {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.rank-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.log-close {
	width: 34px;
	height: 34px;
	border-radius: 50%;
	border: 2px solid var(--brown-line);
	background: var(--cream);
	color: var(--brown-deep);
	font-size: 20px;
	font-weight: 800;
	line-height: 1;
	cursor: pointer;
}

.rank-tabs {
	display: flex;
	gap: 8px;
}

.rank-tab {
	flex: 1;
	height: 38px;
	border-radius: 999px;
	border: 2px solid var(--brown-line);
	background: var(--cream);
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown-deep);
	cursor: pointer;
}

.rank-tab.on {
	background: var(--sage-deep);
	border-color: var(--sage-deep);
	color: #fff;
}

.rank-list {
	display: flex;
	flex-direction: column;
	gap: 6px;
	max-height: 320px;
	overflow-y: auto;
	padding-right: 4px;
}

.rank-row {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 6px 10px;
	border-radius: 12px;
	background: rgba(253, 250, 242, 0.85);
}

.rank-row.mine {
	background: var(--coral);
	color: #fff;
}

.rank-row.top3 {
	background: rgba(245, 210, 122, 0.35);
}

.rank-row.mine.top3 {
	background: var(--coral);
}

.rank-no {
	width: 28px;
	text-align: center;
	font-size: 18px;
	font-weight: 900;
	color: var(--brown);
	flex: none;
}

.rank-no.r1 {
	color: #e8a417;
}

.rank-no.r2 {
	color: #9aa3ad;
}

.rank-no.r3 {
	color: #c07b3c;
}

.rank-row.mine .rank-no {
	color: #fff;
}

.rank-name {
	flex: 1;
	min-width: 0;
	font-size: var(--font-hint);
	font-weight: 700;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.rank-value {
	flex: none;
	font-size: 18px;
	font-weight: 900;
	color: var(--brown-deep);
}

.rank-row.mine .rank-value {
	color: #fff;
}

.rank-unit {
	margin-left: 2px;
	font-size: 12px;
	font-weight: 700;
	opacity: 0.75;
}

.me-fixed {
	margin-top: 4px;
	border: 2px dashed rgba(255, 255, 255, 0.7);
}

.me-note {
	text-align: center;
	padding: 8px 0 2px;
}
</style>
