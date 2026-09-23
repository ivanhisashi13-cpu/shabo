import { EMOTES } from './emotes'

export const PRELOAD_ASSETS = [
	'/art/bg_game_table.png',
	'/art/card_back.png',
	'/art/card_blank.png',
	'/art/deck_pile.png',
	'/art/button_shabo_call.png',
	'/art/shabo_logo.png',
	...EMOTES.map((item) => `/art/emoji/${item.file}.webp`)
]

function loadOne(url) {
	return new Promise((resolve) => {
		const image = new Image()
		image.onload = () => resolve(url)
		image.onerror = () => resolve(url)
		image.src = url
	})
}

export function preloadAssets(onProgress) {
	let done = 0
	const total = PRELOAD_ASSETS.length
	onProgress(0, total)
	return Promise.all(
		PRELOAD_ASSETS.map((url) =>
			loadOne(url).then((value) => {
				done += 1
				onProgress(done, total)
				return value
			})
		)
	)
}
