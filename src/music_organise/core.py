from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping
from urllib.parse import quote, unquote, urlparse
import os
import re
import shutil
import xml.etree.ElementTree as ET

XSPF_NS = "http://xspf.org/ns/0/"
DEFAULT_FORMAT = "{artist}/{year} - {album}{disc_suffix}/{track:02d} - {title}{ext}"
AUDIO_EXTENSIONS = {".mp3", ".flac"}
COVER_ART_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}

_BAD_FILENAME_CHARS = re.compile(r'[<>:"\\|?*\x00-\x1f]')
_MULTI_SPACE = re.compile(r"\s+")
DATE_TAG_KEYS = ("date", "originaldate", "year", "originalyear", "releasedate", "releaseyear")
RAW_MP3_DATE_FRAME_KEYS = ("TDRC", "TDRL", "TYER", "TDOR")


@dataclass(frozen=True)
class TrackTags:
    artist: str = "Unknown Artist"
    albumartist: str = "Unknown Artist"
    album: str = "Unknown Album"
    title: str = "Unknown Title"
    track: int = 0
    disc: int = 0
    year: str = ""
    genre: str = ""
    ext: str = ".mp3"


@dataclass(frozen=True)
class MovePlan:
    source: Path
    destination: Path


@dataclass(frozen=True)
class TrackInfo:
    source: Path
    tags: TrackTags


@dataclass(frozen=True)
class PlaylistUpdate:
    source: Path
    destination: Path
    changes: int


class TagFormatDict(dict):
    def __missing__(self, key: str) -> str:
        raise KeyError(f"unknown format field: {key}")


def read_audio_tags(path: Path) -> TrackTags:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return read_mp3_tags(path)
    if suffix == ".flac":
        return read_flac_tags(path)
    raise RuntimeError(f"unsupported audio file type: {path}")


def read_mp3_tags(path: Path) -> TrackTags:
    try:
        from mutagen.easyid3 import EasyID3
    except ImportError as exc:
        raise RuntimeError(
            "mutagen is required to read MP3 tags. Install with: python3 -m pip install -e ."
        ) from exc

    try:
        audio = EasyID3(path)
    except Exception as exc:
        raise RuntimeError(f"could not read MP3 tags from {path}: {exc}") from exc

    tags = tags_from_mapping(path, audio)
    if tags.year:
        return tags

    raw_date = read_mp3_raw_date(path)
    if raw_date:
        return replace(tags, year=parse_year(raw_date))
    return tags


def read_flac_tags(path: Path) -> TrackTags:
    try:
        from mutagen.flac import FLAC
    except ImportError as exc:
        raise RuntimeError(
            "mutagen is required to read FLAC tags. Install with: python3 -m pip install -e ."
        ) from exc

    try:
        audio = FLAC(path)
    except Exception as exc:
        raise RuntimeError(f"could not read FLAC tags from {path}: {exc}") from exc

    return tags_from_mapping(path, audio)


def tags_from_mapping(path: Path, audio: Mapping[str, list[str]]) -> TrackTags:
    def first(*keys: str, default: str = "") -> str:
        for key in keys:
            values = audio.get(key)
            if values and values[0].strip():
                return values[0].strip()
        return default

    artist = first("artist", default="Unknown Artist")
    albumartist = first("albumartist", "performer", default=artist)
    title = first("title", default=path.stem)

    return TrackTags(
        artist=artist,
        albumartist=albumartist,
        album=first("album", default="Unknown Album"),
        title=title,
        track=parse_number(first("tracknumber")),
        disc=parse_disc_number(first("discnumber")),
        year=parse_year(first(*DATE_TAG_KEYS)),
        genre=first("genre"),
        ext=path.suffix.lower() or ".mp3",
    )


def parse_number(value: str) -> int:
    if not value:
        return 0
    match = re.match(r"\s*(\d+)", value)
    return int(match.group(1)) if match else 0


def parse_disc_number(value: str) -> int:
    if not value:
        return 0
    match = re.match(r"\s*(\d+)(?:\s*/\s*(\d+))?", value)
    if not match:
        return 0
    disc = int(match.group(1))
    total = int(match.group(2)) if match.group(2) else 0
    if disc == 1 and total == 1:
        return 0
    return disc


def parse_year(value: str) -> str:
    if not value:
        return ""
    match = re.match(r"\s*(\d{4})", value)
    return match.group(1) if match else value.strip()


def read_mp3_raw_date(path: Path) -> str:
    try:
        from mutagen import File
    except ImportError as exc:
        raise RuntimeError(
            "mutagen is required to read MP3 tags. Install with: python3 -m pip install -e ."
        ) from exc

    audio = File(path)
    if audio is None:
        return ""
    return raw_mp3_date_from_mapping(audio)


def raw_mp3_date_from_mapping(audio: Mapping[str, object]) -> str:
    for key in RAW_MP3_DATE_FRAME_KEYS:
        value = audio.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def build_destination(destination_root: Path, source: Path, tags: TrackTags, format_string: str) -> Path:
    values = TagFormatDict(format_values(tags))
    rendered_parts: list[str] = []

    for raw_part in format_string.split("/"):
        if raw_part in {"", ".", ".."}:
            continue
        rendered = raw_part.format_map(values)
        rendered_parts.append(sanitize_path_part(rendered))

    if not rendered_parts:
        raise ValueError("format produced an empty destination path")

    destination = destination_root.joinpath(*rendered_parts)
    resolved_root = destination_root.resolve()
    resolved_destination_parent = destination.parent.resolve()
    if not resolved_destination_parent.is_relative_to(resolved_root):
        raise ValueError(f"destination would leave destination directory: {destination}")
    return unique_destination(destination, source)


def format_values(tags: TrackTags) -> dict[str, object]:
    values = dict(tags.__dict__)
    values["disc_suffix"] = f" (Disc {tags.disc})" if tags.disc > 0 else ""
    return values


def sanitize_path_part(value: object) -> str:
    text = str(value).strip()
    text = _BAD_FILENAME_CHARS.sub("_", text)
    text = text.replace("/", "_")
    text = _MULTI_SPACE.sub(" ", text)
    text = text.strip(" .")
    return text or "Unknown"


def unique_destination(destination: Path, source: Path, reserved: set[Path] | None = None) -> Path:
    reserved = reserved or set()
    if destination == source or (not destination.exists() and destination.resolve() not in reserved):
        return destination

    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if candidate == source or (not candidate.exists() and candidate.resolve() not in reserved):
            return candidate
        counter += 1


def discover_audio_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def discover_cover_art(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in COVER_ART_EXTENSIONS
    )


def plan_moves(source_root: Path, destination_root: Path, format_string: str) -> list[MovePlan]:
    track_plans: list[MovePlan] = []
    destination_dirs_by_source_dir: dict[Path, set[Path]] = {}
    reserved_destinations: set[Path] = set()
    tracks = [TrackInfo(source=source, tags=read_audio_tags(source)) for source in discover_audio_files(source_root)]
    validate_tracks(tracks)

    for track in tracks:
        source = track.source
        tags = track.tags
        destination = build_destination(destination_root, source, tags, format_string)
        destination = unique_destination(destination, source, reserved_destinations)
        reserved_destinations.add(destination.resolve())
        destination_dirs_by_source_dir.setdefault(source.parent, set()).add(destination.parent)
        if source.resolve() != destination.resolve():
            track_plans.append(MovePlan(source=source, destination=destination))

    cover_plans = plan_cover_art_moves(destination_dirs_by_source_dir, reserved_destinations)
    return track_plans + cover_plans


def validate_tracks(tracks: list[TrackInfo]) -> None:
    tags_by_source_dir: dict[Path, list[TrackInfo]] = {}
    for track in tracks:
        tags_by_source_dir.setdefault(track.source.parent, []).append(track)

    for source_dir, folder_tracks in tags_by_source_dir.items():
        missing_date_tracks = [track.source.name for track in folder_tracks if not track.tags.year]
        if missing_date_tracks:
            raise ValueError(
                f"tracks in {source_dir} have missing date tags: {', '.join(sorted(missing_date_tracks))}"
            )
        artists = {track.tags.artist for track in folder_tracks}
        albums = {track.tags.album for track in folder_tracks}
        if len(artists) > 1:
            raise ValueError(f"tracks in {source_dir} have different artists: {', '.join(sorted(artists))}")
        if len(albums) > 1:
            raise ValueError(f"tracks in {source_dir} have different albums: {', '.join(sorted(albums))}")
        validate_folder_track_numbers(source_dir, folder_tracks)


def validate_folder_track_numbers(source_dir: Path, tracks: list[TrackInfo]) -> None:
    missing_track_numbers = [track.source.name for track in tracks if track.tags.track <= 0]
    if missing_track_numbers:
        raise ValueError(
            f"tracks in {source_dir} have missing track numbers: {', '.join(sorted(missing_track_numbers))}"
        )

    tracks_by_disc: dict[int, list[TrackInfo]] = {}
    for track in tracks:
        tracks_by_disc.setdefault(track.tags.disc, []).append(track)

    allow_later_start = all(track.tags.disc > 1 for track in tracks)
    for disc, disc_tracks in sorted(tracks_by_disc.items()):
        actual = sorted(track.tags.track for track in disc_tracks)
        start = actual[0] if allow_later_start else 1
        expected = list(range(start, start + len(disc_tracks)))
        if actual != expected:
            disc_label = f"disc {disc}" if disc > 0 else "tracks"
            raise ValueError(
                f"tracks in {source_dir} have non-sequential track numbers for {disc_label}: "
                f"expected {expected}, found {actual}"
            )


def plan_cover_art_moves(
    destination_dirs_by_source_dir: Mapping[Path, set[Path]],
    reserved_destinations: set[Path],
) -> list[MovePlan]:
    plans: list[MovePlan] = []

    for source_dir, destination_dirs in sorted(destination_dirs_by_source_dir.items()):
        for image in discover_cover_art(source_dir):
            for destination_dir in sorted(destination_dirs):
                if source_dir.resolve() == destination_dir.resolve():
                    continue
                destination = unique_destination(destination_dir / image.name, image, reserved_destinations)
                reserved_destinations.add(destination.resolve())
                if image.resolve() != destination.resolve():
                    plans.append(MovePlan(source=image, destination=destination))

    return plans


def apply_moves(plans: list[MovePlan], move: bool = False) -> dict[Path, Path]:
    path_map: dict[Path, Path] = {}
    plans_by_source: dict[Path, list[MovePlan]] = {}
    for plan in plans:
        plans_by_source.setdefault(plan.source.resolve(), []).append(plan)

    for source, source_plans in plans_by_source.items():
        if move and len(source_plans) == 1:
            plan = source_plans[0]
            plan.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(plan.source), str(plan.destination))
            path_map[source] = plan.destination.resolve()
            continue

        for plan in source_plans:
            plan.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plan.source, plan.destination)
            path_map[source] = plan.destination.resolve()
        if move:
            source_path = Path(source)
            if source_path.exists():
                source_path.unlink()
    return path_map


def normalize_single_disc_tags(root: Path) -> int:
    changed = 0
    for path in discover_audio_files(root):
        if normalize_single_disc_tag(path):
            changed += 1
    return changed


def normalize_single_disc_tag(path: Path) -> bool:
    if path.suffix.lower() not in AUDIO_EXTENSIONS:
        return False
    if path.suffix.lower() == ".mp3":
        return normalize_mp3_single_disc_tag(path)
    elif path.suffix.lower() == ".flac":
        return normalize_flac_single_disc_tag(path)
    return False


def should_remove_disc_tag(value: str) -> bool:
    return bool(re.match(r"\s*0*1\s*/\s*0*1\s*$", value))


def normalize_mp3_single_disc_tag(path: Path) -> bool:
    try:
        from mutagen.easyid3 import EasyID3
    except ImportError as exc:
        raise RuntimeError(
            "mutagen is required to update MP3 tags. Install with: python3 -m pip install -e ."
        ) from exc

    audio = EasyID3(path)
    values = audio.get("discnumber")
    if values and should_remove_disc_tag(values[0]):
        del audio["discnumber"]
        audio.save()
        return True
    return False


def normalize_flac_single_disc_tag(path: Path) -> bool:
    try:
        from mutagen.flac import FLAC
    except ImportError as exc:
        raise RuntimeError(
            "mutagen is required to update FLAC tags. Install with: python3 -m pip install -e ."
        ) from exc

    audio = FLAC(path)
    changed = False
    for key in ("discnumber", "disc"):
        values = audio.get(key)
        if values and should_remove_disc_tag(values[0]):
            del audio[key]
            changed = True
    if changed:
        audio.save()
    return changed


def cleanup_empty_dirs(root: Path) -> int:
    removed = 0
    for path in sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            continue
        removed += 1
    return removed


def planned_path_map(plans: list[MovePlan]) -> dict[Path, Path]:
    return {plan.source.resolve(): plan.destination.resolve() for plan in plans}


def update_xspf_playlists(
    playlist_root: Path,
    path_map: Mapping[Path, Path],
    apply: bool,
) -> list[PlaylistUpdate]:
    updates: list[PlaylistUpdate] = []
    for playlist in sorted(playlist_root.rglob("*.xspf")):
        changes = update_xspf_playlist(playlist, playlist, path_map, apply)
        updates.append(PlaylistUpdate(source=playlist, destination=playlist, changes=changes))
    return updates


def update_xspf_playlist(
    source_playlist: Path,
    destination_playlist: Path,
    path_map: Mapping[Path, Path],
    apply: bool,
) -> int:
    ET.register_namespace("", XSPF_NS)
    tree = ET.parse(source_playlist)
    root = tree.getroot()
    changes = 0

    for location in root.findall(f".//{{{XSPF_NS}}}location") + root.findall(".//location"):
        if not location.text:
            continue
        parsed = parse_playlist_location(location.text, source_playlist.parent)
        if parsed is None:
            continue
        original_path, _style = parsed
        replacement = path_map.get(original_path.resolve())
        if replacement is None:
            continue
        location.text = format_playlist_location(replacement, destination_playlist.parent, "relative_path")
        changes += 1

    if apply:
        destination_playlist.parent.mkdir(parents=True, exist_ok=True)
        if changes:
            tree.write(destination_playlist, encoding="utf-8", xml_declaration=True)
        elif source_playlist.resolve() != destination_playlist.resolve():
            shutil.copy2(source_playlist, destination_playlist)

    return changes


def parse_playlist_location(value: str, base_dir: Path) -> tuple[Path, str] | None:
    text = value.strip()
    parsed = urlparse(text)

    if parsed.scheme and parsed.scheme != "file":
        return None

    if parsed.scheme == "file":
        return Path(unquote(parsed.path)), "file_uri"

    unquoted = unquote(text)
    path = Path(unquoted)
    if path.is_absolute():
        return path.resolve(), "absolute_path"
    return base_dir.joinpath(path).resolve(), "relative_path"


def format_playlist_location(path: Path, base_dir: Path, style: str) -> str:
    if style == "file_uri":
        return path.as_uri()
    if style == "absolute_path":
        return str(path)

    relative = os.path.relpath(path, base_dir)
    return quote(Path(relative).as_posix(), safe="/()[]!$&'*,;=:@")
