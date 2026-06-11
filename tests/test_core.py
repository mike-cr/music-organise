from pathlib import Path
import xml.etree.ElementTree as ET

from music_organise.core import (
    DEFAULT_FORMAT,
    MovePlan,
    TrackTags,
    apply_moves,
    build_destination,
    cleanup_empty_dirs,
    discover_audio_files,
    format_playlist_location,
    parse_number,
    parse_playlist_location,
    parse_year,
    plan_moves,
    tags_from_mapping,
    update_xspf_playlists,
    update_xspf_playlist,
)


def test_parse_number_handles_track_totals():
    assert parse_number("03/12") == 3
    assert parse_number("7") == 7
    assert parse_number("") == 0


def test_parse_year_uses_leading_four_digit_year():
    assert parse_year("2006-09-04") == "2006"
    assert parse_year(" 1998") == "1998"
    assert parse_year("") == ""
    assert parse_year("Unknown") == "Unknown"


def test_tags_from_mapping_preserves_flac_extension(tmp_path: Path):
    source = tmp_path / "track.flac"

    tags = tags_from_mapping(
        source,
        {
            "artist": ["Artist"],
            "album": ["Album"],
            "title": ["Title"],
            "tracknumber": ["5"],
            "discnumber": ["2"],
            "date": ["2020-09-04"],
        },
    )

    assert tags == TrackTags(
        artist="Artist",
        albumartist="Artist",
        album="Album",
        title="Title",
        track=5,
        disc=2,
        year="2020",
        ext=".flac",
    )


def test_discover_audio_files_finds_mp3_and_flac(tmp_path: Path):
    mp3 = tmp_path / "one.mp3"
    flac = tmp_path / "two.flac"
    ignored = tmp_path / "notes.txt"
    mp3.write_bytes(b"")
    flac.write_bytes(b"")
    ignored.write_text("ignore", encoding="utf-8")

    assert discover_audio_files(tmp_path) == [mp3, flac]


def test_build_destination_formats_and_sanitizes_parts(tmp_path: Path):
    source_root = tmp_path / "source"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    source = source_root / "loose.mp3"
    source.write_bytes(b"")
    tags = TrackTags(
        artist='AC/DC: Live',
        album="Back < Black",
        title="Hells/Bells?",
        track=2,
        ext=".mp3",
    )

    destination = build_destination(
        destination_root,
        source,
        tags,
        "{artist}/{album}/{track:02d} - {title}{ext}",
    )

    assert destination == destination_root / "AC_DC_ Live" / "Back _ Black" / "02 - Hells_Bells_.mp3"


def test_build_destination_supports_optional_disc_suffix(tmp_path: Path):
    source = tmp_path / "source" / "track.mp3"
    destination_root = tmp_path / "library"
    source.parent.mkdir()
    source.write_bytes(b"")
    format_string = "{artist}/{year} - {album}{disc_suffix}/{track:02d} - {title}{ext}"

    with_disc = build_destination(
        destination_root,
        source,
        TrackTags(artist="Artist", year="1999", album="Album", disc=2, track=3, title="Title"),
        format_string,
    )
    without_disc = build_destination(
        destination_root,
        source,
        TrackTags(artist="Artist", year="1999", album="Album", disc=0, track=3, title="Title"),
        format_string,
    )

    assert with_disc == destination_root / "Artist" / "1999 - Album (Disc 2)" / "03 - Title.mp3"
    assert without_disc == destination_root / "Artist" / "1999 - Album" / "03 - Title.mp3"


def test_default_format_includes_year_album_and_optional_disc_suffix(tmp_path: Path):
    source = tmp_path / "source" / "track.mp3"
    destination_root = tmp_path / "library"
    source.parent.mkdir()
    source.write_bytes(b"")

    destination = build_destination(
        destination_root,
        source,
        TrackTags(artist="Artist", year="2001", album="Album", disc=1, track=4, title="Song"),
        DEFAULT_FORMAT,
    )

    assert destination == destination_root / "Artist" / "2001 - Album (Disc 1)" / "04 - Song.mp3"


def test_playlist_location_round_trip_relative(tmp_path: Path):
    playlist_dir = tmp_path / "playlists"
    playlist_dir.mkdir()
    target = tmp_path / "Music" / "Artist" / "Song Name.mp3"

    location = format_playlist_location(target, playlist_dir, "relative_path")
    parsed = parse_playlist_location(location, playlist_dir)

    assert location == "../Music/Artist/Song%20Name.mp3"
    assert parsed == (target, "relative_path")


def test_update_xspf_playlist_rewrites_matching_locations(tmp_path: Path):
    music = tmp_path / "music"
    playlists = tmp_path / "playlists"
    playlist_output = tmp_path / "copied-playlists"
    music.mkdir()
    playlists.mkdir()
    old_path = music / "old song.mp3"
    new_path = music / "Artist" / "Album" / "01 - New Song.mp3"
    old_path.write_bytes(b"")

    playlist = playlists / "mix.xspf"
    playlist.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <trackList>
    <track>
      <location>../music/old%20song.mp3</location>
    </track>
  </trackList>
</playlist>
""",
        encoding="utf-8",
    )

    copied_playlist = playlist_output / "mix.xspf"
    changes = update_xspf_playlist(
        playlist,
        copied_playlist,
        {old_path.resolve(): new_path.resolve()},
        apply=True,
    )

    assert changes == 1
    assert "../music/old%20song.mp3" in playlist.read_text(encoding="utf-8")
    tree = ET.parse(copied_playlist)
    location = tree.getroot().find(".//{http://xspf.org/ns/0/}location")
    assert location is not None
    assert location.text == "../music/Artist/Album/01%20-%20New%20Song.mp3"


def test_update_xspf_playlist_can_rewrite_in_place(tmp_path: Path):
    music = tmp_path / "music"
    playlists = tmp_path / "playlists"
    music.mkdir()
    playlists.mkdir()
    old_path = music / "old.mp3"
    new_path = music / "Artist" / "Album" / "01 - New.mp3"
    old_path.write_bytes(b"")

    playlist = playlists / "mix.xspf"
    playlist.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <trackList>
    <track>
      <location>../music/old.mp3</location>
    </track>
  </trackList>
</playlist>
""",
        encoding="utf-8",
    )

    changes = update_xspf_playlist(
        playlist,
        playlist,
        {old_path.resolve(): new_path.resolve()},
        apply=True,
    )

    assert changes == 1
    tree = ET.parse(playlist)
    location = tree.getroot().find(".//{http://xspf.org/ns/0/}location")
    assert location is not None
    assert location.text == "../music/Artist/Album/01%20-%20New.mp3"


def test_update_xspf_playlists_copies_nested_playlists_with_relative_paths(tmp_path: Path):
    music_source = tmp_path / "source-music"
    music_destination = tmp_path / "library"
    playlist_source = tmp_path / "source-playlists"
    playlist_destination = tmp_path / "copied-playlists"
    nested = playlist_source / "folders"
    music_source.mkdir()
    music_destination.mkdir()
    nested.mkdir(parents=True)
    old_path = music_source / "old.mp3"
    new_path = music_destination / "Artist" / "Album" / "01 - New.mp3"
    old_path.write_bytes(b"")

    playlist = nested / "mix.xspf"
    playlist.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <trackList>
    <track>
      <location>../../source-music/old.mp3</location>
    </track>
  </trackList>
</playlist>
""",
        encoding="utf-8",
    )

    updates = update_xspf_playlists(
        playlist_source,
        playlist_destination,
        {old_path.resolve(): new_path.resolve()},
        apply=True,
    )

    copied_playlist = playlist_destination / "folders" / "mix.xspf"
    assert updates[0].source == playlist
    assert updates[0].destination == copied_playlist
    assert updates[0].changes == 1
    tree = ET.parse(copied_playlist)
    location = tree.getroot().find(".//{http://xspf.org/ns/0/}location")
    assert location is not None
    assert location.text == "../../library/Artist/Album/01%20-%20New.mp3"


def test_update_xspf_playlists_copies_unchanged_playlists(tmp_path: Path):
    playlist_source = tmp_path / "source-playlists"
    playlist_destination = tmp_path / "copied-playlists"
    playlist_source.mkdir()
    playlist = playlist_source / "unchanged.xspf"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <trackList />
</playlist>
"""
    playlist.write_text(content, encoding="utf-8")

    updates = update_xspf_playlists(playlist_source, playlist_destination, {}, apply=True)

    copied_playlist = playlist_destination / "unchanged.xspf"
    assert updates[0].changes == 0
    assert copied_playlist.read_text(encoding="utf-8") == content


def test_update_xspf_playlists_allows_unchanged_in_place_playlists(tmp_path: Path):
    playlist_source = tmp_path / "playlists"
    playlist_source.mkdir()
    playlist = playlist_source / "unchanged.xspf"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <trackList />
</playlist>
"""
    playlist.write_text(content, encoding="utf-8")

    updates = update_xspf_playlists(playlist_source, playlist_source, {}, apply=True)

    assert updates[0].source == playlist
    assert updates[0].destination == playlist
    assert updates[0].changes == 0
    assert playlist.read_text(encoding="utf-8") == content



def test_plan_moves_moves_cover_art_with_tracks(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_dir = source_root / "album"
    source_dir.mkdir(parents=True)
    track = source_dir / "track.mp3"
    cover = source_dir / "cover.jpg"
    track.write_bytes(b"")
    cover.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        assert path == track
        return TrackTags(artist="Artist", album="Album", title="Title", track=1, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    moves = plan_moves(source_root, destination_root, "{artist}/{album}/{track:02d} - {title}{ext}")

    assert moves == [
        MovePlan(track, destination_root / "Artist" / "Album" / "01 - Title.mp3"),
        MovePlan(cover, destination_root / "Artist" / "Album" / "cover.jpg"),
    ]


def test_plan_moves_copies_cover_art_to_each_split_destination_folder(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_dir = source_root / "album"
    source_dir.mkdir(parents=True)
    track_one = source_dir / "one.mp3"
    track_two = source_dir / "two.mp3"
    cover = source_dir / "cover.jpg"
    track_one.write_bytes(b"")
    track_two.write_bytes(b"")
    cover.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        album = "One" if path == track_one else "Two"
        return TrackTags(artist="Artist", album=album, title=path.stem, track=1, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    moves = plan_moves(source_root, destination_root, "{artist}/{album}/{track:02d} - {title}{ext}")

    assert moves == [
        MovePlan(track_one, destination_root / "Artist" / "One" / "01 - one.mp3"),
        MovePlan(track_two, destination_root / "Artist" / "Two" / "01 - two.mp3"),
        MovePlan(cover, destination_root / "Artist" / "One" / "cover.jpg"),
        MovePlan(cover, destination_root / "Artist" / "Two" / "cover.jpg"),
    ]


def test_plan_moves_uses_unique_destinations_for_duplicate_formatted_tracks(
    tmp_path: Path, monkeypatch
):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track_one = source_root / "one.mp3"
    track_two = source_root / "two.mp3"
    track_one.write_bytes(b"")
    track_two.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        return TrackTags(artist="Artist", album="Album", title="Same", track=1, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    moves = plan_moves(source_root, destination_root, "{artist}/{album}/{track:02d} - {title}{ext}")

    assert moves == [
        MovePlan(track_one, destination_root / "Artist" / "Album" / "01 - Same.mp3"),
        MovePlan(track_two, destination_root / "Artist" / "Album" / "01 - Same (1).mp3"),
    ]


def test_plan_moves_handles_flac_files(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track = source_root / "track.flac"
    track.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        assert path == track
        return TrackTags(
            artist="Artist",
            year="2024",
            album="Album",
            title="Lossless",
            track=1,
            ext=".flac",
        )

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    moves = plan_moves(source_root, destination_root, DEFAULT_FORMAT)

    assert moves == [
        MovePlan(track, destination_root / "Artist" / "2024 - Album" / "01 - Lossless.flac")
    ]


def test_apply_moves_copies_files_and_keeps_sources(tmp_path: Path):
    source = tmp_path / "source" / "track.mp3"
    destination = tmp_path / "library" / "Artist" / "track.mp3"
    source.parent.mkdir()
    source.write_bytes(b"audio")

    path_map = apply_moves([MovePlan(source, destination)])

    assert source.read_bytes() == b"audio"
    assert destination.read_bytes() == b"audio"
    assert path_map == {source.resolve(): destination.resolve()}


def test_apply_moves_can_move_files_for_in_place_organisation(tmp_path: Path):
    source = tmp_path / "source" / "old" / "track.mp3"
    destination = tmp_path / "source" / "Artist" / "track.mp3"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"audio")

    path_map = apply_moves([MovePlan(source, destination)], move=True)

    assert not source.exists()
    assert destination.read_bytes() == b"audio"
    assert path_map == {source.resolve(): destination.resolve()}


def test_cleanup_empty_dirs_removes_only_empty_child_folders(tmp_path: Path):
    root = tmp_path / "music"
    empty_nested = root / "old" / "disc"
    non_empty = root / "Artist"
    empty_nested.mkdir(parents=True)
    non_empty.mkdir(parents=True)
    (non_empty / "track.mp3").write_bytes(b"audio")

    assert cleanup_empty_dirs(root) == 2
    assert root.exists()
    assert not (root / "old").exists()
    assert non_empty.exists()
