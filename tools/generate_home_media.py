#!/usr/bin/env python3
"""Generate Home carousel media from recent landscape activity photos.

Rules
-----
- Scan tracked images in assets/img/activity/.
- Keep only landscape images whose aspect ratio is between 1.25 and 1.90.
  This includes common 4:3, 3:2, and 16:9 photos while excluding portrait
  images and very wide panoramas.
- Select at most 6 eligible images.
- For the current activityN.jpg naming convention, larger N is newer.
- For arbitrary future filenames, fall back to Git add time.
- Write the result to assets/home_media.json.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, UnidentifiedImageError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
ACTIVITY_DIR = Path("assets/img/activity")
DEFAULT_OUTPUT = Path("assets/home_media.json")
DEFAULT_LIMIT = 6
MIN_ASPECT_RATIO = 1.25
MAX_ASPECT_RATIO = 1.90


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def natural_key(path: str):
    name = Path(path).name.lower()
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def activity_number(path: str) -> int | None:
    """Return N for names like activityN.jpg, otherwise None."""
    match = re.fullmatch(r"activity(\d+)", Path(path).stem, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def is_home_eligible(width: int, height: int) -> bool:
    """Return True for landscape photos suitable for the Home carousel."""
    if width <= 0 or height <= 0 or width <= height:
        return False
    ratio = width / height
    return MIN_ASPECT_RATIO <= ratio <= MAX_ASPECT_RATIO


def image_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as image:
            return image.size
    except (OSError, UnidentifiedImageError):
        return None


def added_timestamp(repo: Path, rel_path: str) -> int:
    """Return timestamp for the commit in which the file was first added."""
    output = git(
        repo,
        "log",
        "--follow",
        "--diff-filter=A",
        "--format=%ct",
        "--",
        rel_path,
    )
    timestamps = [int(line) for line in output.splitlines() if line.strip().isdigit()]
    if timestamps:
        return min(timestamps)

    output = git(repo, "log", "-1", "--format=%ct", "--", rel_path)
    return int(output) if output.isdigit() else 0


def list_activity_images(repo: Path) -> list[str]:
    tracked = git(repo, "ls-files", ACTIVITY_DIR.as_posix())
    images: list[str] = []
    for rel_path in tracked.splitlines():
        rel_path = rel_path.strip()
        if not rel_path:
            continue
        if Path(rel_path).suffix.lower() in IMAGE_EXTENSIONS:
            images.append(rel_path)
    return images


def filter_eligible_images(repo: Path, images: list[str]) -> list[str]:
    eligible: list[str] = []
    for rel_path in images:
        dimensions = image_dimensions(repo / rel_path)
        if dimensions is None:
            print(f"[skip] unreadable image: {rel_path}")
            continue

        width, height = dimensions
        ratio = width / height if height else 0
        if not is_home_eligible(width, height):
            print(f"[skip] unsuitable ratio {width}x{height} ({ratio:.3f}): {rel_path}")
            continue

        print(f"[keep] {width}x{height} ({ratio:.3f}): {rel_path}")
        eligible.append(rel_path)

    return eligible


def select_recent_images(repo: Path, limit: int) -> list[str]:
    images = list_activity_images(repo)
    eligible = filter_eligible_images(repo, images)
    if not eligible:
        return []

    numbered = [(activity_number(path), path) for path in eligible]
    if all(number is not None for number, _ in numbered):
        numbered.sort(key=lambda item: item[0], reverse=True)
        return [path for _, path in numbered[:limit]]

    ranked = [(added_timestamp(repo, path), path) for path in eligible]
    ranked.sort(key=lambda item: natural_key(item[1]), reverse=True)
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in ranked[:limit]]


def write_json(output: Path, media: list[str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"media": media}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    repo = args.repo.resolve()
    output = args.output if args.output is not None else repo / DEFAULT_OUTPUT
    if not output.is_absolute():
        output = repo / output

    media = select_recent_images(repo, args.limit)
    write_json(output, media)

    print(f"Selected {len(media)} Home carousel image(s):")
    for path in media:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
