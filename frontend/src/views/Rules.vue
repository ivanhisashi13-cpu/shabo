<script setup>
import { useRouter } from 'vue-router'

import { RULE_SECTIONS as SECTIONS } from '../data/rules'

const router = useRouter()
</script>

<template>
	<div class="screen rules">
		<div class="head">
			<button class="round" @click="router.back()">←</button>
			<div class="title">SHABO 规则</div>
			<div class="spacer"></div>
		</div>
		<div class="body scroll">
			<div v-for="section in SECTIONS" :key="section.title" class="panel card">
				<div class="card-title">{{ section.title }}</div>
				<p v-for="(line, index) in section.lines" :key="index" class="line">· {{ line }}</p>
			</div>
		</div>
	</div>
</template>

<style scoped>
.rules {
	background: var(--paper);
	display: flex;
	flex-direction: column;
	padding: 10px 16px 14px;
	gap: 10px;
}

.head {
	display: flex;
	align-items: center;
	height: 48px;
	flex: none;
}

.round {
	width: 44px;
	height: 44px;
	border-radius: 50%;
	background: var(--cream);
	border: 2px solid var(--brown-line);
	font-size: 18px;
	font-weight: 800;
	color: var(--brown-deep);
}

.title {
	flex: 1;
	text-align: center;
}

.spacer {
	width: 44px;
}

.body {
	flex: 1;
	min-height: 0;
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	gap: 10px;
	align-content: start;
	padding-right: 6px;
}

.card {
	padding: 10px 14px;
}

.card-title {
	font-size: var(--font-hint);
	font-weight: 800;
	color: var(--brown-deep);
	margin-bottom: 4px;
}

.line {
	margin: 2px 0;
	font-size: 14px;
	line-height: 1.6;
	color: var(--ink-soft);
}
</style>
