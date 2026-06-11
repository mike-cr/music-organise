from __future__ import annotations

from pathlib import Path
import sys

from .core import DEFAULT_FORMAT


class TuiCancelled(Exception):
    pass


def run_tui() -> int:
    try:
        from prompt_toolkit import prompt
        from prompt_toolkit.completion import PathCompleter
    except ImportError:
        print(
            "prompt-toolkit is required for the TUI. Install dependencies with: python3 -m pip install -e .",
            file=sys.stderr,
        )
        return 1

    from .cli import run_organise, validate_paths

    path_completer = PathCompleter(only_directories=True, expanduser=True)

    print("music-organise TUI")
    print("Use Tab to autocomplete paths. Leave the format blank to use the default.")
    print("Playlists are read from the destination music folder's playlists subfolder.")
    print()

    try:
        source_dir = prompt_path("Source music folder: ", path_completer, prompt)
        destination_dir = prompt_path("Destination music folder: ", path_completer, prompt)
        format_string = prompt_text(
            "Organisation format: ",
            prompt,
            default=DEFAULT_FORMAT,
            complete_while_typing=False,
        ).strip() or DEFAULT_FORMAT
        apply_changes = prompt_apply_mode(prompt)
    except TuiCancelled:
        print()
        print("Cancelled.")
        return 130

    source_dir = source_dir.expanduser().resolve()
    destination_dir = destination_dir.expanduser().resolve()

    validation_error = validate_paths(
        source_dir,
        destination_dir,
    )
    if validation_error:
        print(validation_error, file=sys.stderr)
        return 2

    print()
    print("Applying changes" if apply_changes else "Dry run preview")
    return run_organise(
        source_dir,
        destination_dir,
        format_string,
        apply=apply_changes,
    )


def prompt_path(message: str, path_completer: object, prompt_func: object) -> Path:
    while True:
        value = prompt_text(
            message,
            prompt_func,
            completer=path_completer,
            complete_while_typing=True,
        ).strip()
        if value:
            return Path(value)
        print("Path is required.")


def prompt_apply_mode(prompt_func: object) -> bool:
    while True:
        value = prompt_text("Mode [dry-run/apply]: ", prompt_func, default="dry-run").strip().lower()
        if value in {"dry-run", "dry", "d", "preview", "p"}:
            return False
        if value in {"apply", "a", "yes", "y"}:
            return True
        print("Enter 'dry-run' or 'apply'.")


def prompt_text(message: str, prompt_func: object, **kwargs: object) -> str:
    try:
        return prompt_func(message, **kwargs)
    except (KeyboardInterrupt, EOFError) as exc:
        raise TuiCancelled from exc
