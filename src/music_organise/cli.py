from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .core import (
    DEFAULT_FORMAT,
    apply_moves,
    cleanup_empty_dirs,
    normalize_single_disc_tags,
    plan_moves,
    planned_path_map,
    update_xspf_playlists,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organise MP3 and FLAC files by tags and update XSPF playlists."
    )
    parser.add_argument("source_dir", nargs="?", type=Path, help="Folder containing audio files to organise.")
    parser.add_argument("destination_dir", nargs="?", type=Path, help="Folder to move organised files into.")
    parser.add_argument(
        "--format",
        default=DEFAULT_FORMAT,
        help=f"Destination format relative to destination_dir. Default: {DEFAULT_FORMAT}",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move files and update playlists. Without this, only a dry run is printed.",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Start the interactive terminal UI with path autocomplete.",
    )
    return parser.parse_args(argv)


def validate_paths(
    source_dir: Path,
    destination_dir: Path,
) -> str | None:
    playlist_dir = destination_dir / "playlists"
    if not source_dir.is_dir():
        return f"source directory does not exist: {source_dir}"
    if destination_dir.exists() and not destination_dir.is_dir():
        return f"destination path exists but is not a directory: {destination_dir}"
    if not playlist_dir.is_dir():
        return f"playlist directory does not exist: {playlist_dir}"
    return None


def run_organise(
    source_dir: Path,
    destination_dir: Path,
    format_string: str,
    apply: bool,
) -> int:
    source_dir = source_dir.expanduser().resolve()
    destination_dir = destination_dir.expanduser().resolve()
    playlist_dir = destination_dir / "playlists"

    validation_error = validate_paths(
        source_dir,
        destination_dir,
    )
    if validation_error:
        print(validation_error, file=sys.stderr)
        return 2

    try:
        moves = plan_moves(source_dir, destination_dir, format_string)
    except Exception as exc:
        print(f"failed to plan moves: {exc}", file=sys.stderr)
        return 1

    path_map = planned_path_map(moves)
    in_place_music = source_dir == destination_dir

    if moves:
        print("File moves:")
        for move in moves:
            print(f"  {move.source} -> {move.destination}")
    else:
        print("No audio files need moving.")

    if apply:
        try:
            normalized_tags = normalize_single_disc_tags(source_dir)
            if normalized_tags:
                print(f"Removed single-disc disc tags from {normalized_tags} file(s).")
            path_map = apply_moves(moves, move=True)
            if in_place_music:
                cleaned_dirs = cleanup_empty_dirs(source_dir)
                if cleaned_dirs:
                    print(f"Removed {cleaned_dirs} empty folder(s).")
        except Exception as exc:
            print(f"failed while moving files: {exc}", file=sys.stderr)
            return 1

    try:
        playlist_updates = update_xspf_playlists(
            playlist_dir,
            path_map,
            apply=apply,
        )
    except Exception as exc:
        print(f"failed while updating playlists: {exc}", file=sys.stderr)
        return 1

    if playlist_updates:
        print("Playlist copies:")
        for update in playlist_updates:
            print(f"  {update.source} -> {update.destination}: {update.changes} location update(s)")
    else:
        print("No XSPF playlists found.")

    if not apply:
        print("Dry run only. Re-run with --apply to move files and update playlists.")

    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = [
        args.source_dir,
        args.destination_dir,
    ]

    if args.tui or all(path is None for path in paths):
        from .tui import run_tui

        return run_tui()

    if any(path is None for path in paths):
        print(
            "source_dir and destination_dir are required",
            file=sys.stderr,
        )
        return 2

    return run_organise(
        args.source_dir,
        args.destination_dir,
        args.format,
        args.apply,
    )


if __name__ == "__main__":
    raise SystemExit(main())
