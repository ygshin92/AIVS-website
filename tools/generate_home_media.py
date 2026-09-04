#!/usr/bin/env python3
"""Generate assets/home_media.json from the most recently added activity images."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
ACTIVITY_DIR = Path("assets/img/activity")
DEFAULT_OUTPUT = Path("assets/home_media.json")
DEFAULT_LIMIT = 6


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


def added_timestamp(repo: Path, rel_path: str) -> int:
    """Return the commit timestamp where this path first appeared.

    A full git history is required for precise results; the accompanying
    GitHub Actions workflow checks out with fetch-depth: 0.
    """
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
        # `git log` is newest-first. For an add event there is normally one entry;
        # min() is safer if history contains an unusual delete/re-add sequence.
        return min(timestamps)

    # Fallback for unusual history: latest commit touching the file.
    output = git(repo, "log", "-1", "--format=%ct", "--", rel_path)
    return int(output) if output.isdigit() else 0


def list_activity_images(repo: Path) -> list[str]:
    tracked = git(repo, "ls-files", ACTIVITY_DIR.as_posix())
    paths = []
    for rel_path in tracked.splitlines():
        rel_path = rel_path.strip()
        if not rel_path:
            continue
        if Path(rel_path).suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(rel_path)
    return paths


def select_recent_images(repo: Path, limit: int) -> list[str]:
    images = list_activity_images(repo)
    if not images:
        return []

    ranked = [(added_timestamp(repo, path), path) for path in images]

    # Primary sort: newest Git addition first.
    # Tie-break: higher natural filename first (activity6 before activity5).
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

    repo = args.repo.resolve()
    output = args.output if args.output is not None else repo / DEFAULT_OUTPUT
    if not output.is_absolute():
        output = repo / output

    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    media = select_recent_images(repo, args.limit)
    write_json(output, media)

    print(f"Selected {len(media)} home image(s):")
    for path in media:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
