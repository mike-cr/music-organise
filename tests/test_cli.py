from pathlib import Path

from music_organise.cli import main, parse_args
from music_organise.cli import validate_paths


def test_parse_args_allows_tui_without_paths():
    args = parse_args(["--tui"])

    assert args.tui is True
    assert args.source_dir is None


def test_main_rejects_partial_positional_args(capsys):
    result = main([str(Path("/tmp/music"))])

    assert result == 2
    assert "source_dir, destination_dir" in capsys.readouterr().err


def test_validate_paths_allows_playlist_destination_to_match_source(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    playlists = tmp_path / "playlists"
    source.mkdir()
    playlists.mkdir()

    assert validate_paths(source, destination, playlists, playlists) is None


def test_validate_paths_allows_music_destination_to_match_source(tmp_path):
    source = tmp_path / "source"
    playlists = tmp_path / "playlists"
    source.mkdir()
    playlists.mkdir()

    assert validate_paths(source, source, playlists, playlists) is None
