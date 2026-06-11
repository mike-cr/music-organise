from pathlib import Path

from music_organise.cli import main, parse_args, run_organise
from music_organise.cli import validate_paths
from music_organise.core import MovePlan


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


def test_run_organise_moves_music_when_destination_differs(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    playlists = tmp_path / "playlists"
    source.mkdir()
    playlists.mkdir()
    track = source / "track.mp3"
    target = destination / "track.mp3"
    plan = MovePlan(track, target)
    move_args = []

    monkeypatch.setattr("music_organise.cli.plan_moves", lambda *args: [plan])
    monkeypatch.setattr("music_organise.cli.planned_path_map", lambda plans: {track.resolve(): target.resolve()})
    monkeypatch.setattr("music_organise.cli.normalize_single_disc_tags", lambda root: 0)

    def fake_apply_moves(plans, move=False):
        move_args.append(move)
        return {track.resolve(): target.resolve()}

    monkeypatch.setattr("music_organise.cli.apply_moves", fake_apply_moves)
    monkeypatch.setattr("music_organise.cli.update_xspf_playlists", lambda *args, **kwargs: [])

    assert run_organise(source, destination, playlists, playlists, "{title}{ext}", apply=True) == 0
    assert move_args == [True]
