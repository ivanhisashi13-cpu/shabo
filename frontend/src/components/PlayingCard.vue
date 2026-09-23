<script setup>
import { computed } from 'vue'

const props = defineProps({
	card: { type: Object, default: null },
	faceDown: { type: Boolean, default: false },
	size: { type: String, default: 'own' },
	highlight: { type: Boolean, default: false },
	selected: { type: Boolean, default: false },
	dim: { type: Boolean, default: false },
	open: { type: Boolean, default: false },
	badge: { type: String, default: '' },
	hideSkill: { type: Boolean, default: false }
})

const SIZES = {
	own: [98, 138],
	mid: [80, 112],
	tight: [64, 90],
	foe: [48, 68],
	center: [86, 122],
	pile: [69, 98],
	big: [116, 164]
}

const SUIT_SYMBOL = { spade: '♠', heart: '♥', club: '♣', diamond: '♦', joker: '★' }

const box = computed(() => {
	const [w, h] = SIZES[props.size] || SIZES.own
	return { width: `${w}px`, height: `${h}px` }
})

const scale = computed(() => {
	const [, h] = SIZES[props.size] || SIZES.own
	return h / 138
})

const showFace = computed(() => Boolean(props.card) && !props.faceDown)
const symbol = computed(() => (props.card ? SUIT_SYMBOL[props.card.suit] || '' : ''))
const isRed = computed(() => Boolean(props.card) && (props.card.suit === 'heart' || props.card.suit === 'diamond'))
const specialText = computed(() => (props.card && !props.hideSkill ? props.card.skill_label || '' : ''))
</script>

<template>
	<div class="card" :class="{ highlight, dim, open, selected }" :style="box">
		<div class="flipper" :class="{ back: !showFace }">
			<div class="face front" :style="{ fontSize: `${scale * 46}px` }">
				<template v-if="card">
					<span class="rank" :class="{ red: isRed }">{{ card.label }}</span>
					<span v-if="specialText" class="special" :style="{ fontSize: `${scale * 13}px` }">{{ specialText }}</span>
				</template>
			</div>
			<div class="face rear"></div>
		</div>
		<span v-if="selected" class="check">✓</span>
		<span v-if="open" class="open-tag">明</span>
		<span v-if="badge" class="badge">{{ badge }}</span>
	</div>
</template>

<style scoped>
.card {
	position: relative;
	perspective: 700px;
	flex: none;
	transition: transform 0.18s ease, filter 0.18s ease;
}

.card.dim {
	filter: grayscale(0.4) brightness(0.92);
	opacity: 0.75;
}

.card.highlight {
	z-index: 2;
	animation: card-pop 0.9s ease-in-out infinite;
}

.card.highlight .face {
	animation: card-ring 0.9s ease-in-out infinite;
}

@keyframes card-pop {
	0%,
	100% {
		transform: translateY(-6px) scale(1);
	}
	50% {
		transform: translateY(-9px) scale(1.06);
	}
}

@keyframes card-ring {
	0%,
	100% {
		box-shadow: 0 0 0 2px var(--orange), 0 3px 8px rgba(109, 74, 44, 0.3);
	}
	50% {
		box-shadow: 0 0 0 4px var(--orange), 0 0 16px rgba(245, 172, 106, 0.95);
	}
}

.card.open .front {
	box-shadow: 0 0 0 3px var(--sage-deep), 0 3px 8px rgba(109, 74, 44, 0.3);
}

.card.selected {
	z-index: 4;
	transform: translateY(-10px) scale(1.05);
}

.card.selected .face {
	box-shadow: 0 0 0 3px #fff, 0 0 0 6px var(--coral-deep), 0 8px 16px rgba(109, 74, 44, 0.45);
	animation: selected-glow 1s ease-in-out infinite;
}

.card.selected .front::after {
	content: '';
	position: absolute;
	inset: 0;
	border-radius: 8px;
	background: rgba(226, 112, 92, 0.16);
	pointer-events: none;
}

@keyframes selected-glow {
	0%,
	100% {
		box-shadow: 0 0 0 3px #fff, 0 0 0 6px var(--coral-deep), 0 8px 16px rgba(109, 74, 44, 0.45);
	}
	50% {
		box-shadow: 0 0 0 3px #fff, 0 0 0 9px var(--coral-deep), 0 8px 20px rgba(226, 112, 92, 0.55);
	}
}

.check {
	position: absolute;
	right: -6px;
	top: -8px;
	width: 22px;
	height: 22px;
	border-radius: 50%;
	background: var(--coral-deep);
	color: #fff;
	font-size: 14px;
	font-weight: 900;
	line-height: 22px;
	text-align: center;
	box-shadow: 0 2px 5px rgba(109, 74, 44, 0.45);
	z-index: 5;
}

.open-tag {
	position: absolute;
	right: -4px;
	top: -6px;
	min-width: 18px;
	height: 18px;
	padding: 0 4px;
	border-radius: 999px;
	background: var(--sage-deep);
	color: #fff;
	font-size: 11px;
	font-weight: 800;
	line-height: 18px;
	text-align: center;
	z-index: 3;
}

.flipper {
	position: absolute;
	inset: 0;
	transform-style: preserve-3d;
	transition: transform 0.36s cubic-bezier(0.3, 0.8, 0.4, 1);
}

.flipper.back {
	transform: rotateY(180deg);
}

.face {
	position: absolute;
	inset: 0;
	backface-visibility: hidden;
	border-radius: 8px;
	background-size: 100% 100%;
	background-repeat: no-repeat;
	box-shadow: 0 3px 8px rgba(109, 74, 44, 0.3);
}

.front {
	background-image: url('/art/card_blank.png');
	display: flex;
	align-items: center;
	justify-content: center;
	color: var(--brown-deep);
	font-weight: 800;
}

.rear {
	background-image: url('/art/card_back.png');
	transform: rotateY(180deg);
}

.rank {
	line-height: 1;
}

.rank.red {
	color: var(--coral-deep);
}

.special {
	position: absolute;
	left: 50%;
	bottom: 13%;
	transform: translateX(-50%);
	max-width: 88%;
	padding: 2px 8px;
	border-radius: 999px;
	background: var(--sage);
	color: #3f5a2a;
	font-weight: 700;
	line-height: 1.2;
	text-align: center;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.badge {
	position: absolute;
	left: 50%;
	bottom: -10px;
	transform: translateX(-50%);
	padding: 2px 8px;
	border-radius: 999px;
	background: var(--orange);
	color: #7a4a20;
	font-size: 12px;
	font-weight: 700;
	white-space: nowrap;
	z-index: 3;
}
</style>
