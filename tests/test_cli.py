import pytest

import snake_quest
from snake_quest import cli, game


def test_defaults():
    args = cli.build_parser().parse_args([])
    assert args.level == 1
    assert cli.settings_overrides(args) == {}


def test_overrides():
    args = cli.build_parser().parse_args(["--scale", "2", "--mute", "--debug"])
    assert cli.settings_overrides(args) == {"scale": 2, "music": False, "effects": False, "debug": True}


def test_level_must_exist(capsys):
    assert 4 not in cli.available_levels()
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--level", "4"])
    assert "invalid choice" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"snake-quest {snake_quest.__version__}"


def test_main_starts_game_with_options(monkeypatch):
    calls = []
    monkeypatch.setattr(game, "Game", lambda **kwargs: calls.append(kwargs))
    cli.main(["--level", "2", "--mute"])
    assert calls == [{"overrides": {"music": False, "effects": False}, "start_level": 2}]


def test_game_merges_overrides_over_settings():
    instance = game.Game.__new__(game.Game)
    instance.overrides = {"music": False, "scale": 1}
    instance.reload_settings()
    assert instance.cfg.music is False
    assert instance.cfg.scale == 1
    assert instance.cfg.width == 320  # untouched values come from settings.yaml
