<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const STAGE_W = 960
const STAGE_H = 540

const transform = ref('')
const rotated = ref(false)

function resize() {
	const vw = window.innerWidth
	const vh = window.innerHeight
	const landscape = vw >= vh
	rotated.value = !landscape
	const scale = landscape
		? Math.min(vw / STAGE_W, vh / STAGE_H)
		: Math.min(vh / STAGE_W, vw / STAGE_H)
	transform.value = landscape ? `scale(${scale})` : `rotate(90deg) scale(${scale})`
}

onMounted(() => {
	resize()
	window.addEventListener('resize', resize)
	window.addEventListener('orientationchange', resize)
})

onBeforeUnmount(() => {
	window.removeEventListener('resize', resize)
	window.removeEventListener('orientationchange', resize)
})
</script>

<template>
	<div class="stage-root">
		<div class="stage" :style="{ transform }">
			<slot />
		</div>
		<div v-if="rotated" class="rotate-tip">请横屏使用，体验更佳</div>
	</div>
</template>

<style scoped>
.rotate-tip {
	position: absolute;
	right: 10px;
	bottom: 10px;
	padding: 6px 14px;
	border-radius: 999px;
	background: rgba(253, 250, 242, 0.85);
	color: #6d4a2c;
	font-size: 13px;
	pointer-events: none;
}
</style>
