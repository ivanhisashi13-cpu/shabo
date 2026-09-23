<script setup>
import { computed } from 'vue'

const props = defineProps({
	avatar: { type: String, default: 'fox' },
	size: { type: Number, default: 56 },
	active: { type: Boolean, default: false },
	offline: { type: Boolean, default: false },
	tone: { type: String, default: 'cream' }
})

const EMOJI = {
	fox: '🦊',
	panda: '🐼',
	owl: '🦉',
	cat: '🐱',
	wolf: '🐺',
	bear: '🐻',
	rabbit: '🐰',
	tiger: '🐯',
	penguin: '🐧',
	koala: '🐨',
	deer: '🦌',
	dragon: '🐲',
	whale: '🐳'
}

const emoji = computed(() => EMOJI[props.avatar] || '🦊')
const box = computed(() => ({
	width: `${props.size}px`,
	height: `${props.size}px`,
	fontSize: `${Math.round(props.size * 0.56)}px`
}))
</script>

<template>
	<div class="avatar" :class="[tone, { active, offline }]" :style="box">
		<span>{{ emoji }}</span>
	</div>
</template>

<style scoped>
.avatar {
	display: flex;
	align-items: center;
	justify-content: center;
	flex: none;
	border-radius: 16px;
	border: 3px solid var(--brown-line);
	background: var(--cream);
	box-shadow: 0 3px 8px rgba(109, 74, 44, 0.22);
	transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

.avatar.green {
	background: var(--sage);
}

.avatar.coral {
	background: var(--coral);
}

.avatar.active {
	border-color: var(--orange);
	transform: scale(1.06);
	box-shadow: 0 0 0 4px rgba(245, 172, 106, 0.55), 0 0 22px rgba(245, 172, 106, 0.85);
	animation: pulse 1.4s ease-in-out infinite;
}

.avatar.offline {
	filter: grayscale(1);
	opacity: 0.6;
}

@keyframes pulse {
	0%,
	100% {
		box-shadow: 0 0 0 4px rgba(245, 172, 106, 0.45), 0 0 18px rgba(245, 172, 106, 0.6);
	}
	50% {
		box-shadow: 0 0 0 6px rgba(245, 172, 106, 0.7), 0 0 28px rgba(245, 172, 106, 0.95);
	}
}
</style>
