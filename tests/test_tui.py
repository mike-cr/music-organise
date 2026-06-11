from pathlib import Path

from music_organise.tui import TuiCancelled, prompt_apply_mode, prompt_path, prompt_text, run_tui


def test_prompt_path_uses_supplied_prompt_function():
    calls = []

    def fake_prompt(*args, **kwargs):
        calls.append((args, kwargs))
        return "/tmp/music"

    assert prompt_path("Path: ", object(), fake_prompt) == Path("/tmp/music")
    assert calls[0][0] == ("Path: ",)
    assert calls[0][1]["complete_while_typing"] is True


def test_prompt_apply_mode_defaults_to_dry_run():
    calls = []

    def fake_prompt(*args, **kwargs):
        calls.append((args, kwargs))
        return "dry-run"

    assert prompt_apply_mode(fake_prompt) is False
    assert calls == [(("Mode [dry-run/apply]: ",), {"default": "dry-run"})]


def test_prompt_apply_mode_accepts_apply():
    assert prompt_apply_mode(lambda *args, **kwargs: "apply") is True


def test_prompt_text_converts_keyboard_interrupt_to_cancelled():
    def fake_prompt(*args, **kwargs):
        raise KeyboardInterrupt

    try:
        prompt_text("Path: ", fake_prompt)
    except TuiCancelled:
        pass
    else:
        raise AssertionError("expected TuiCancelled")


def test_run_tui_returns_cleanly_on_cancel(monkeypatch, capsys):
    class FakeCompleter:
        def __init__(self, *args, **kwargs):
            pass

    def fake_prompt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("prompt_toolkit.prompt", fake_prompt)
    monkeypatch.setattr("prompt_toolkit.completion.PathCompleter", FakeCompleter)

    assert run_tui() == 130
    assert "Cancelled." in capsys.readouterr().out
