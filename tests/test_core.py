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
    normalize_single_disc_tags,
    parse_disc_number,
    parse_number,
    parse_playlist_location,
    parse_year,
    plan_moves,
    raw_mp3_date_from_mapping,
    should_remove_disc_tag,
    tags_from_mapping,
    update_xspf_playlists,
    update_xspf_playlist,
)


def test_parse_number_handles_track_totals():
    assert parse_number("03/12") == 3
    assert parse_number("7") == 7
    assert parse_number("") == 0


def test_parse_disc_number_treats_one_of_one_as_absent():
    assert parse_disc_number("1/1") == 0
    assert parse_disc_number("01 / 01") == 0
    assert parse_disc_number("1/2") == 1
    assert parse_disc_number("2/2") == 2
    assert parse_disc_number("") == 0


def test_should_remove_disc_tag_only_matches_one_of_one():
    assert should_remove_disc_tag("1/1") is True
    assert should_remove_disc_tag(" 01 / 01 ") is True
    assert should_remove_disc_tag("1") is False
    assert should_remove_disc_tag("1/2") is False


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


def test_tags_from_mapping_reads_common_date_aliases(tmp_path: Path):
    source = tmp_path / "track.flac"

    tags = tags_from_mapping(
        source,
        {
            "artist": ["Artist"],
            "album": ["Album"],
            "title": ["Title"],
            "tracknumber": ["1"],
            "releasedate": ["2006-09-04"],
        },
    )

    assert tags.year == "2006"


def test_raw_mp3_date_from_mapping_reads_release_time_frame():
    assert raw_mp3_date_from_mapping({"TDRL": "2003"}) == "2003"


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
        return TrackTags(artist="Artist", year="2024", album="Album", title="Title", track=1, ext=".mp3")

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
        disc = 1 if path == track_one else 2
        return TrackTags(
            artist="Artist",
            year="2024",
            album="Album",
            disc=disc,
            title=path.stem,
            track=1,
            ext=".mp3",
        )

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    moves = plan_moves(source_root, destination_root, DEFAULT_FORMAT)

    assert moves == [
        MovePlan(track_one, destination_root / "Artist" / "2024 - Album (Disc 1)" / "01 - one.mp3"),
        MovePlan(track_two, destination_root / "Artist" / "2024 - Album (Disc 2)" / "01 - two.mp3"),
        MovePlan(cover, destination_root / "Artist" / "2024 - Album (Disc 1)" / "cover.jpg"),
        MovePlan(cover, destination_root / "Artist" / "2024 - Album (Disc 2)" / "cover.jpg"),
    ]


def test_plan_moves_refuses_folder_when_any_track_has_missing_date(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    missing_date = source_root / "missing.mp3"
    dated = source_root / "dated.mp3"
    missing_date.write_bytes(b"")
    dated.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        year = "" if path == missing_date else "2024"
        return TrackTags(artist="Artist", year=year, album="Album", title=path.stem, track=1, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    try:
        plan_moves(source_root, destination_root, DEFAULT_FORMAT)
    except ValueError as exc:
        message = str(exc)
        assert f"tracks in {source_root}" in message
        assert "missing date tags" in message
        assert "missing.mp3" in message
    else:
        raise AssertionError("expected missing date validation error")


def test_plan_moves_refuses_mixed_artists_in_same_source_folder(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track_one = source_root / "one.mp3"
    track_two = source_root / "two.mp3"
    track_one.write_bytes(b"")
    track_two.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        artist = "One" if path == track_one else "Two"
        return TrackTags(artist=artist, year="2024", album="Album", title=path.stem, track=1, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    try:
        plan_moves(source_root, destination_root, DEFAULT_FORMAT)
    except ValueError as exc:
        assert "different artists" in str(exc)
    else:
        raise AssertionError("expected mixed artist validation error")


def test_plan_moves_refuses_mixed_albums_in_same_source_folder(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track_one = source_root / "one.mp3"
    track_two = source_root / "two.mp3"
    track_one.write_bytes(b"")
    track_two.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        album = "One" if path == track_one else "Two"
        return TrackTags(artist="Artist", year="2024", album=album, title=path.stem, track=1, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    try:
        plan_moves(source_root, destination_root, DEFAULT_FORMAT)
    except ValueError as exc:
        assert "different albums" in str(exc)
    else:
        raise AssertionError("expected mixed album validation error")


def test_plan_moves_refuses_folder_when_any_track_has_missing_track_number(
    tmp_path: Path, monkeypatch
):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    missing_track = source_root / "missing.mp3"
    numbered = source_root / "numbered.mp3"
    missing_track.write_bytes(b"")
    numbered.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        track = 0 if path == missing_track else 1
        return TrackTags(artist="Artist", year="2024", album="Album", title=path.stem, track=track, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    try:
        plan_moves(source_root, destination_root, DEFAULT_FORMAT)
    except ValueError as exc:
        message = str(exc)
        assert f"tracks in {source_root}" in message
        assert "missing track numbers" in message
        assert "missing.mp3" in message
    else:
        raise AssertionError("expected missing track number validation error")


def test_plan_moves_refuses_non_sequential_track_numbers(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track_one = source_root / "one.mp3"
    track_three = source_root / "three.mp3"
    track_one.write_bytes(b"")
    track_three.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        track = 1 if path == track_one else 3
        return TrackTags(artist="Artist", year="2024", album="Album", title=path.stem, track=track, ext=".mp3")

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    try:
        plan_moves(source_root, destination_root, DEFAULT_FORMAT)
    except ValueError as exc:
        message = str(exc)
        assert "non-sequential track numbers" in message
        assert "expected [1, 2]" in message
        assert "found [1, 3]" in message
    else:
        raise AssertionError("expected non-sequential track number validation error")


def test_plan_moves_refuses_duplicate_track_numbers(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track_one = source_root / "one.mp3"
    track_two = source_root / "two.mp3"
    track_one.write_bytes(b"")
    track_two.write_bytes(b"")

    monkeypatch.setattr(
        "music_organise.core.read_audio_tags",
        lambda path: TrackTags(artist="Artist", year="2024", album="Album", title=path.stem, track=1, ext=".mp3"),
    )

    try:
        plan_moves(source_root, destination_root, DEFAULT_FORMAT)
    except ValueError as exc:
        message = str(exc)
        assert "non-sequential track numbers" in message
        assert "found [1, 1]" in message
    else:
        raise AssertionError("expected duplicate track number validation error")


def test_plan_moves_allows_disc_greater_than_one_folder_to_start_later(
    tmp_path: Path, monkeypatch
):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track_ten = source_root / "ten.mp3"
    track_eleven = source_root / "eleven.mp3"
    track_ten.write_bytes(b"")
    track_eleven.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        track = 10 if path == track_ten else 11
        return TrackTags(
            artist="Artist",
            year="2024",
            album="Album",
            disc=2,
            title=path.stem,
            track=track,
            ext=".mp3",
        )

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    moves = plan_moves(source_root, destination_root, DEFAULT_FORMAT)

    assert moves == [
        MovePlan(track_eleven, destination_root / "Artist" / "2024 - Album (Disc 2)" / "11 - eleven.mp3"),
        MovePlan(track_ten, destination_root / "Artist" / "2024 - Album (Disc 2)" / "10 - ten.mp3"),
    ]


def test_plan_moves_refuses_disc_greater_than_one_folder_with_track_gap(
    tmp_path: Path, monkeypatch
):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    track_ten = source_root / "ten.mp3"
    track_twelve = source_root / "twelve.mp3"
    track_ten.write_bytes(b"")
    track_twelve.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        track = 10 if path == track_ten else 12
        return TrackTags(
            artist="Artist",
            year="2024",
            album="Album",
            disc=2,
            title=path.stem,
            track=track,
            ext=".mp3",
        )

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    try:
        plan_moves(source_root, destination_root, DEFAULT_FORMAT)
    except ValueError as exc:
        message = str(exc)
        assert "non-sequential track numbers" in message
        assert "expected [10, 11]" in message
        assert "found [10, 12]" in message
    else:
        raise AssertionError("expected non-sequential track number validation error")


def test_plan_moves_allows_track_numbers_to_restart_on_each_disc(tmp_path: Path, monkeypatch):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    source_root.mkdir()
    disc_one = source_root / "disc-one.mp3"
    disc_two = source_root / "disc-two.mp3"
    disc_one.write_bytes(b"")
    disc_two.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        disc = 1 if path == disc_one else 2
        return TrackTags(
            artist="Artist",
            year="2024",
            album="Album",
            disc=disc,
            title=path.stem,
            track=1,
            ext=".mp3",
        )

    monkeypatch.setattr("music_organise.core.read_audio_tags", fake_read_tags)

    moves = plan_moves(source_root, destination_root, DEFAULT_FORMAT)

    assert moves == [
        MovePlan(disc_one, destination_root / "Artist" / "2024 - Album (Disc 1)" / "01 - disc-one.mp3"),
        MovePlan(disc_two, destination_root / "Artist" / "2024 - Album (Disc 2)" / "01 - disc-two.mp3"),
    ]


def test_plan_moves_uses_unique_destinations_for_duplicate_formatted_tracks(
    tmp_path: Path, monkeypatch
):
    source_root = tmp_path / "incoming"
    destination_root = tmp_path / "library"
    first_folder = source_root / "first"
    second_folder = source_root / "second"
    first_folder.mkdir(parents=True)
    second_folder.mkdir(parents=True)
    track_one = first_folder / "one.mp3"
    track_two = second_folder / "two.mp3"
    track_one.write_bytes(b"")
    track_two.write_bytes(b"")

    def fake_read_tags(path: Path) -> TrackTags:
        return TrackTags(artist="Artist", year="2024", album="Album", title="Same", track=1, ext=".mp3")

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


def test_apply_moves_copies_duplicate_source_then_removes_original_in_move_mode(tmp_path: Path):
    source = tmp_path / "source" / "cover.jpg"
    destination_one = tmp_path / "library" / "Disc 1" / "cover.jpg"
    destination_two = tmp_path / "library" / "Disc 2" / "cover.jpg"
    source.parent.mkdir()
    source.write_bytes(b"image")

    apply_moves(
        [
            MovePlan(source, destination_one),
            MovePlan(source, destination_two),
        ],
        move=True,
    )

    assert not source.exists()
    assert destination_one.read_bytes() == b"image"
    assert destination_two.read_bytes() == b"image"


def test_normalize_single_disc_tags_counts_changed_files(tmp_path: Path, monkeypatch):
    track = tmp_path / "track.mp3"
    track.write_bytes(b"")

    monkeypatch.setattr("music_organise.core.discover_audio_files", lambda root: [track])
    monkeypatch.setattr("music_organise.core.normalize_single_disc_tag", lambda path: path == track)

    assert normalize_single_disc_tags(tmp_path) == 1


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
