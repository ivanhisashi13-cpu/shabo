export const EMOTES = [
	{ key: 'lol', name: '大笑', file: '1f602' },
	{ key: 'wow', name: '惊讶', file: '1f62e' },
	{ key: 'angry', name: '愤怒', file: '1f621' },
	{ key: 'boom', name: '爆炸', file: '1f4a5' },
	{ key: 'smirk', name: '嘲讽', file: '1f60f' },
	{ key: 'cry', name: '哭泣', file: '1f62d' },
	{ key: 'thumb', name: '点赞', file: '1f44d' },
	{ key: 'clap', name: '鼓掌', file: '1f44f' }
]

export const QUICK_PHRASES = [
	'快点吧～',
	'这张我要了！',
	'别看我的牌',
	'我快 SHABO 了',
	'手气真差',
	'稳住，能赢'
]

const BY_KEY = EMOTES.reduce((map, item) => ({ ...map, [item.key]: item }), {})

export function emoteOf(key) {
	return BY_KEY[key] || null
}

export function emoteSrc(key) {
	const item = BY_KEY[key]
	return item ? `/art/emoji/${item.file}.webp` : ''
}
