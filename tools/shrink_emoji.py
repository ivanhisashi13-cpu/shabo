"""Downscale the animated emoji assets used by the game bubbles.

Run with ``python tools/shrink_emoji.py``. Reads every ``*.webp`` inside
``frontend/public/assets/emoji`` and rewrites it at ``TARGET_SIZE`` pixels so the
mobile client only downloads a few dozen kilobytes per emoji.
"""

import os
import sys

from PIL import Image
from PIL import ImageSequence

TARGET_SIZE = 144
QUALITY = 70
EMOJI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
	"frontend", "public", "assets", "emoji")


def shrink(path: str) -> None:
	"""Rewrite one animated webp at the target size.

	Args:
		path: Absolute path of the source file.
	"""
	with Image.open(path) as source:
		frames = []
		durations = []
		for frame in ImageSequence.Iterator(source):
			durations.append(frame.info.get("duration", 60))
			frames.append(frame.convert("RGBA").resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS))
		loop = source.info.get("loop", 0)

	head = frames[0]
	head.save(
		path,
		format="WEBP",
		save_all=True,
		append_images=frames[1:],
		duration=durations,
		loop=loop,
		quality=QUALITY,
		method=6,
	)


def main() -> int:
	"""Shrink every emoji asset.

	Returns:
		int: Process exit code.
	"""
	if not os.path.isdir(EMOJI_DIR):
		print(f"目录不存在: {EMOJI_DIR}")
		return 1
	for name in sorted(os.listdir(EMOJI_DIR)):
		if not name.endswith(".webp"):
			continue
		path = os.path.join(EMOJI_DIR, name)
		before = os.path.getsize(path)
		shrink(path)
		after = os.path.getsize(path)
		print(f"{name}: {before // 1024}KB -> {after // 1024}KB")
	return 0


if __name__ == "__main__":
	sys.exit(main())
