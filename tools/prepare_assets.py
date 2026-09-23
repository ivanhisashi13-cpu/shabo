"""Crop transparent padding from SHABO art assets and copy them to the frontend.

Usage:
	python tools/prepare_assets.py <source_dir> <target_dir>
"""

import os
import sys

from PIL import Image

TRIM_FILES = (
	"card_back.png",
	"card_blank.png",
	"deck_pile.png",
	"button_shabo_call.png",
	"shabo_logo.png",
)
COPY_FILES = ("bg_game_table.png",)
ALPHA_THRESHOLD = 8


def trim(source_path: str, target_path: str) -> None:
	"""Remove fully transparent borders and save the result.

	Args:
		source_path: Original PNG path.
		target_path: Destination PNG path.
	"""
	image = Image.open(source_path).convert("RGBA")
	alpha = image.getchannel("A").point(lambda value: 255 if value > ALPHA_THRESHOLD else 0)
	box = alpha.getbbox()
	cropped = image.crop(box) if box else image
	cropped.save(target_path, optimize=True)
	print(f"{os.path.basename(source_path)} {image.size} -> {cropped.size}")


def main() -> None:
	"""Run the asset preparation pipeline."""
	source_dir, target_dir = sys.argv[1], sys.argv[2]
	os.makedirs(target_dir, exist_ok=True)
	for name in TRIM_FILES:
		trim(os.path.join(source_dir, name), os.path.join(target_dir, name))
	for name in COPY_FILES:
		image = Image.open(os.path.join(source_dir, name)).convert("RGBA")
		image.save(os.path.join(target_dir, name), optimize=True)
		print(f"{name} {image.size} copied")


if __name__ == "__main__":
	main()
