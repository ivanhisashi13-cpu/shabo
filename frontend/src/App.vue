<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import Stage from './components/Stage.vue'
import { preloadAssets } from './data/assets'
import { useAuthStore } from './store/auth'
import { useGameStore } from './store/game'

const auth = useAuthStore()
const game = useGameStore()
const route = useRoute()
const router = useRouter()

const assetsReady = ref(false)
const loaded = ref(0)
const total = ref(1)

const percent = computed(() => Math.round((loaded.value / Math.max(1, total.value)) * 100))

onMounted(async () => {
	const startedAt = Date.now()
	await preloadAssets((done, count) => {
		loaded.value = done
		total.value = count
	})
	const rest = 600 - (Date.now() - startedAt)
	if (rest > 0) await new Promise((resolve) => setTimeout(resolve, rest))
	assetsReady.value = true
})

watch(
	() => auth.token,
	(token) => {
		if (token) {
			game.start(token)
		} else {
			game.stop()
		}
	},
	{ immediate: true }
)

watch(
	() => Boolean(game.game),
	(playing) => {
		if (playing && route.name !== 'game') router.push({ name: 'game' })
		if (!playing && route.name === 'game') router.push({ name: 'hall' })
	}
)

const statusText = computed(() => {
	if (game.status === 'online') return ''
	return game.status === 'connecting' ? '连接中…' : '已断线，正在重连…'
})

// 短暂（<1 秒）的重连不弹提示，避免频繁闪现「已断线」
const netVisible = ref(false)
let netTimer = null

watch(
	() => game.status,
	(status) => {
		if (status === 'online') {
			if (netTimer) {
				clearTimeout(netTimer)
				netTimer = null
			}
			netVisible.value = false
			return
		}
		if (netTimer) return
		netTimer = setTimeout(() => {
			netVisible.value = true
			netTimer = null
		}, 900)
	}
)
</script>

<template>
	<Stage>
		<router-view v-slot="{ Component }">
			<component :is="Component" />
		</router-view>

		<Transition name="fade">
			<div v-if="game.toast" class="toast" :class="game.toastTone">{{ game.toast }}</div>
		</Transition>

		<div v-if="netVisible && statusText && auth.isLoggedIn" class="net">{{ statusText }}</div>

		<div v-if="game.invite" class="mask">
			<div class="panel invite">
				<div class="title">房间邀请</div>
				<p class="invite-text">
					<b>{{ game.invite.from_nickname }}</b> 邀请你加入房间
					<b>{{ game.invite.code }}</b>
				</p>
				<div class="invite-actions">
					<button class="btn green" @click="game.respondInvite(true)">接受</button>
					<button class="btn ghost" @click="game.respondInvite(false)">拒绝</button>
				</div>
			</div>
		</div>

		<Transition name="fade">
			<div v-if="!assetsReady" class="loading">
				<div class="load-title">SHABO 傻波儿</div>
				<div class="load-hint">正在加载牌桌素材，稍等一下～</div>
				<div class="load-bar">
					<div class="load-fill" :style="{ width: `${percent}%` }"></div>
				</div>
				<div class="load-num">{{ loaded }} / {{ total }} · {{ percent }}%</div>
			</div>
		</Transition>
	</Stage>
</template>

<style scoped>
.net {
	position: absolute;
	right: 14px;
	bottom: 10px;
	padding: 5px 14px;
	border-radius: 999px;
	background: rgba(226, 112, 92, 0.92);
	color: #fff;
	font-size: 13px;
	z-index: 95;
}

.invite {
	width: 420px;
	padding: 24px;
	text-align: center;
}

.invite-text {
	font-size: var(--font-body);
	margin: 18px 0 22px;
}

.invite-actions {
	display: flex;
	gap: 16px;
	justify-content: center;
}

.loading {
	position: absolute;
	inset: 0;
	z-index: 200;
	background: var(--paper);
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 14px;
}

.load-title {
	font-size: 44px;
	font-weight: 900;
	letter-spacing: 8px;
	color: var(--brown-deep);
}

.load-hint {
	font-size: var(--font-hint);
	color: var(--ink-soft);
}

.load-bar {
	width: 420px;
	height: 18px;
	border-radius: 999px;
	border: 2px solid var(--brown-line);
	background: var(--cream);
	overflow: hidden;
}

.load-fill {
	height: 100%;
	background: var(--sage-deep);
	transition: width 0.2s ease;
}

.load-num {
	font-size: var(--font-mini);
	color: var(--ink-soft);
}
</style>
