<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import Avatar from '../components/Avatar.vue'
import { getServerSetting, serverLabel, setServerSetting } from '../api/server'
import { useAuthStore } from '../store/auth'
import { useGameStore } from '../store/game'

const auth = useAuthStore()
const game = useGameStore()
const router = useRouter()

const tab = ref('login')
const userId = ref('')
const password = ref('')
const nickname = ref('')
const avatar = ref('fox')
const server = ref(getServerSetting())
const busy = ref(false)

onMounted(async () => {
	try {
		await auth.loadAvatars()
	} catch (error) {
		game.showToast(error.message)
	}
})

function saveServer() {
	setServerSetting(server.value)
	server.value = getServerSetting()
	game.showToast(`服务器已设为 ${serverLabel()}`, 'ok')
}

async function submit() {
	if (busy.value) return
	busy.value = true
	try {
		if (tab.value === 'login') {
			await auth.login({ user_id: userId.value.trim(), password: password.value })
		} else {
			await auth.register({
				user_id: userId.value.trim(),
				password: password.value,
				nickname: nickname.value.trim(),
				avatar: avatar.value
			})
		}
		router.push({ name: 'hall' })
	} catch (error) {
		game.showToast(error.message)
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<div class="screen login">
		<div class="brand">
			<div class="tag-shadow"></div>
			<div class="tag">
				<div class="hole"></div>
				<img class="logo" src="/art/shabo_logo.png" alt="SHABO" />
				<div class="sub">记忆卡牌对战</div>
			</div>
		</div>

		<div class="right">
			<div class="panel form">
				<div class="tabs">
					<button class="tab" :class="{ on: tab === 'login' }" @click="tab = 'login'">登录</button>
					<button class="tab red" :class="{ on: tab === 'register' }" @click="tab = 'register'">注册</button>
				</div>

				<div class="body">
					<div class="row">
						<span class="label">用户ID</span>
						<input v-model="userId" class="input" placeholder="3-20 位字母数字" maxlength="20" />
					</div>
					<div class="row">
						<span class="label">密码</span>
						<input v-model="password" class="input" type="password" placeholder="6-20 位" maxlength="20" />
					</div>
					<template v-if="tab === 'register'">
						<div class="row">
							<span class="label">昵称</span>
							<input v-model="nickname" class="input" placeholder="2-12 个字" maxlength="12" />
						</div>
						<div class="row">
							<span class="label">头像</span>
							<div class="avatars scroll">
								<button
									v-for="item in auth.avatars"
									:key="item"
									class="avatar-pick"
									:class="{ on: avatar === item }"
									@click="avatar = item"
								>
									<Avatar :avatar="item" :size="40" />
								</button>
							</div>
						</div>
					</template>

					<button class="btn wide" :disabled="busy" @click="submit">
						{{ tab === 'login' ? '进入游戏' : '注册并登录' }}
					</button>
				</div>
			</div>

			<div class="panel server">
				<input v-model="server" class="input flex" placeholder="服务器地址（留空使用当前站点）" />
				<button class="btn small" @click="saveServer">保存</button>
			</div>
		</div>

		<button class="rules-link" @click="router.push({ name: 'rules' })">规则说明</button>
	</div>
</template>

<style scoped>
.login {
	background: var(--paper);
	display: flex;
	align-items: center;
	padding: 0 56px;
	gap: 40px;
}

.brand {
	position: relative;
	width: 330px;
	height: 420px;
	flex: none;
}

.tag-shadow {
	position: absolute;
	left: 8px;
	top: 34px;
	width: 274px;
	height: 366px;
	border-radius: 26px;
	background: var(--sage);
	transform: rotate(-3deg);
}

.tag {
	position: absolute;
	left: 40px;
	top: 14px;
	width: 262px;
	height: 372px;
	border-radius: 24px;
	background: var(--cream);
	border: 2px solid var(--brown-line);
	box-shadow: var(--shadow-float);
	transform: rotate(2deg);
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 10px;
}

.hole {
	position: absolute;
	top: 26px;
	width: 20px;
	height: 20px;
	border-radius: 50%;
	background: var(--brown-deep);
}

.logo {
	width: 190px;
	object-fit: contain;
}

.sub {
	font-size: 20px;
	font-weight: 800;
	color: var(--brown-deep);
	letter-spacing: 4px;
}

.right {
	flex: 1;
	display: flex;
	flex-direction: column;
	gap: 14px;
	max-width: 470px;
}

.form {
	overflow: hidden;
	padding: 0;
}

.tabs {
	display: flex;
	height: 52px;
}

.tab {
	flex: 1;
	font-size: 20px;
	font-weight: 800;
	letter-spacing: 3px;
	color: #fff;
	background: rgba(168, 201, 140, 0.55);
}

.tab.on {
	background: var(--sage-deep);
}

.tab.red {
	background: rgba(226, 112, 92, 0.5);
}

.tab.red.on {
	background: var(--coral);
}

.body {
	padding: 16px 22px 20px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.row {
	display: flex;
	align-items: center;
	gap: 12px;
}

.label {
	width: 62px;
	flex: none;
	font-size: var(--font-hint);
	font-weight: 700;
	color: var(--brown);
}

.input {
	flex: 1;
	width: 100%;
}

.avatars {
	flex: 1;
	display: flex;
	gap: 8px;
	overflow-x: auto;
	overflow-y: hidden;
	padding: 2px;
}

.avatar-pick {
	padding: 2px;
	border-radius: 14px;
	border: 2px solid transparent;
	flex: none;
}

.avatar-pick.on {
	border-color: var(--coral);
}

.btn.wide {
	width: 100%;
	margin-top: 4px;
}

.server {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 12px;
}

.server .flex {
	flex: 1;
}

.rules-link {
	position: absolute;
	right: 18px;
	top: 14px;
	font-size: var(--font-hint);
	color: var(--brown);
	text-decoration: underline;
	padding: 8px;
}
</style>
