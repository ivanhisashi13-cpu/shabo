"""WebSocket protocol smoke test, executed inside the backend container."""

import asyncio
import json
import urllib.error
import urllib.request

import websockets

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws"


def http_post(path: str, payload: dict) -> dict:
	"""Send a JSON POST request.

	Args:
		path: API path.
		payload: JSON body.

	Returns:
		dict: Decoded response body.
	"""
	request = urllib.request.Request(
		BASE_URL + path,
		data=json.dumps(payload).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	with urllib.request.urlopen(request, timeout=10) as response:
		return json.loads(response.read().decode("utf-8"))


def ensure_account(user_id: str, nickname: str) -> str:
	"""Register or log in a test account.

	Args:
		user_id: Account identifier.
		nickname: Display name.

	Returns:
		str: Access token.
	"""
	payload = {"user_id": user_id, "password": "test1234", "nickname": nickname, "avatar": "fox"}
	try:
		return http_post("/api/auth/register", payload)["access_token"]
	except urllib.error.HTTPError:
		return http_post("/api/auth/login", {"user_id": user_id, "password": "test1234"})["access_token"]


class Client:
	"""A thin websocket test client."""

	def __init__(self, user_id: str, token: str) -> None:
		"""Create the client.

		Args:
			user_id: Account identifier.
			token: JWT access token.
		"""
		self.user_id = user_id
		self.token = token
		self.socket = None
		self.room = None
		self.game = None
		self.errors = []

	async def connect(self) -> None:
		"""Open the socket and authenticate."""
		self.socket = await websockets.connect(WS_URL)
		await self.send("auth", token=self.token)
		await self.pump(0.6)

	async def send(self, action: str, **payload) -> None:
		"""Send one command.

		Args:
			action: Message type.
			payload: Extra fields.
		"""
		await self.socket.send(json.dumps({"type": action, **payload}))

	async def pump(self, seconds: float = 0.5) -> None:
		"""Drain incoming messages for a while.

		Args:
			seconds: Listening window.
		"""
		loop = asyncio.get_event_loop()
		end = loop.time() + seconds
		while loop.time() < end:
			try:
				raw = await asyncio.wait_for(self.socket.recv(), timeout=max(0.05, end - loop.time()))
			except asyncio.TimeoutError:
				return
			message = json.loads(raw)
			if message["type"] == "room_state":
				self.room = message["room"]
				self.game = message["game"]
			elif message["type"] == "error":
				self.errors.append(message["message"])


def own_hand(client: "Client") -> list:
	"""Return the occupied hand slots of a client from its own snapshot.

	Args:
		client: Connected test client.

	Returns:
		list: Slot views that still hold a card.
	"""
	row = [item for item in client.game["players"] if item["user_id"] == client.user_id][0]
	return [slot for slot in row["hand"] if slot["has_card"]]


async def main() -> None:
	"""Run the smoke test."""
	host = Client("smokehost", ensure_account("smokehost", "房主"))
	guest = Client("smokeguest", ensure_account("smokeguest", "客人"))
	await host.connect()
	await guest.connect()

	await host.send("create_room", max_players=2, mode="SINGLE")
	await host.pump()
	code = host.room["code"]
	print("room", code)

	await guest.send("join_room", code=code)
	await guest.pump()
	await host.pump(0.3)

	await guest.send("ready", ready=True)
	await guest.pump(0.3)
	await host.pump(0.3)

	await host.send("start_game")
	await host.pump(0.6)
	await guest.pump(0.3)
	assert host.game is not None, "game not started"
	print("phase", host.game["phase"], "peeker", host.game["peek_user_id"])

	for _ in range(2):
		for client in (host, guest):
			if client.game and client.game["peek_user_id"] == client.user_id:
				await client.send("peek_select", slots=[0, 1])
				await client.pump(0.4)
				await (guest if client is host else host).pump(0.2)
		await asyncio.sleep(3.2)
		await host.pump(0.4)
		await guest.pump(0.4)

	print("phase", host.game["phase"], "turn", host.game["turn_user_id"])

	taker = host if host.game["turn_user_id"] == host.user_id else guest
	peer = guest if taker is host else host
	await taker.send("take_discard", slot=3)
	await taker.pump(0.5)
	await peer.pump(0.3)
	taker_view = [row for row in taker.game["players"] if row["user_id"] == taker.user_id][0]
	peer_view = [row for row in peer.game["players"] if row["user_id"] == taker.user_id][0]
	print("take_discard slot3", taker_view["hand"][3]["card"], "peer sees", peer_view["hand"][3]["card"])
	assert peer_view["hand"][3]["card"] is not None, "taken card must be public"

	actor = host if host.game["turn_user_id"] == host.user_id else guest
	other = guest if actor is host else host

	await actor.send("draw")
	await actor.pump(0.4)
	print("drawn", actor.game["drawn_card"], "peer sees", other.game["drawn_card"] if other.game else None)
	assert actor.game["drawn_card"] is not None, "actor should see the drawn card"

	if actor.game["drawn_card"]["is_special"]:
		await actor.send("use_special")
		await actor.pump(0.4)
		print("special", actor.game["special"])
		await actor.send("cancel_special")
		await actor.pump(0.3)

	await actor.send("replace", slot=2)
	await actor.pump(0.5)
	await other.pump(0.3)
	print("after replace turn", actor.game["turn_user_id"], "discard", actor.game["discard_count"])

	multi = host if host.game["turn_user_id"] == host.user_id else guest
	watcher = guest if multi is host else host
	before = len(own_hand(multi))
	await multi.send("draw")
	await multi.pump(0.4)
	await multi.send("replace", slots=[0, 1])
	await multi.pump(0.6)
	await watcher.pump(0.3)
	after = len(own_hand(multi))
	seen = [row for row in watcher.game["players"] if row["user_id"] == multi.user_id][0]
	print("multi replace", before, "->", after,
		[slot["card"]["value"] if slot["card"] else None for slot in seen["hand"]])
	assert after != before, "多张换牌必须改变手牌数量"

	await host.send("chat", text="lol", kind="emoji")
	await host.pump(0.3)
	await guest.pump(0.3)
	last_chat = guest.room["chat"][-1]
	print("chat", last_chat)
	assert last_chat["kind"] == "emoji" and last_chat["text"] == "lol", "emoji chat broken"
	await host.send("chat", text="not_an_emoji", kind="emoji")
	await host.pump(0.3)
	assert host.errors, "unknown emoji must be rejected"
	host.errors.clear()

	current = host if host.game["turn_user_id"] == host.user_id else guest
	await current.send("draw")
	await current.pump(0.4)
	await current.send("discard")
	await current.pump(0.5)

	await host.pump(0.3)
	next_actor = host if host.game["turn_user_id"] == host.user_id else guest
	await next_actor.send("call_cabo")
	await next_actor.pump(0.5)
	print("cabo caller", next_actor.game["cabo_caller"], "phase", next_actor.game["phase"])

	loops = 0
	while host.game and host.game["round_result"] is None and loops < 12:
		current = host if host.game["turn_user_id"] == host.user_id else guest
		await current.send("draw")
		await current.pump(0.35)
		await current.send("discard")
		await current.pump(0.45)
		await host.pump(0.2)
		loops += 1

	print("result", json.dumps(host.game["round_result"], ensure_ascii=False)[:400])

	await host.send("create_room", max_players=5, mode="MULTI")
	await host.pump(0.5)
	print("five seat room", host.room["code"], host.room["max_players"])
	assert host.room["max_players"] == 5, "房间应支持 5 人"
	await host.send("leave_room")
	await host.pump(0.3)
	await guest.pump(0.3)
	guest.errors.clear()

	print("errors host", host.errors)
	print("errors guest", guest.errors)
	assert not host.errors and not guest.errors, "unexpected protocol errors"
	print("SMOKE OK")


asyncio.run(main())
