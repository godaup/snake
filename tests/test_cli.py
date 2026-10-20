import pytest

import snake_quest
from snake_quest import cli, game
from snake_quest.campaign import load_campaign
from snake_quest.profile import Profile


def test_defaults():
    args = cli.build_parser().parse_args([])
    assert args.level == 1
    assert cli.settings_overrides(args) == {}


def test_overrides():
    args = cli.build_parser().parse_args(["--scale", "2", "--mute", "--debug"])
    assert cli.settings_overrides(args) == {"scale": 2, "music": False, "effects": False, "debug": True}


def test_level_by_number_or_name():
    parser = cli.build_parser()
    assert parser.parse_args(["--level", "2"]).level == 2
    assert parser.parse_args(["--level", "maze"]).level == load_campaign().resolve("maze")


@pytest.mark.parametrize("value", ["99", "0", "nope"])
def test_level_must_exist(capsys, value):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--level", value])
    assert "choose from 1=classic" in capsys.readouterr().err


def make_game(monkeypatch, level_counter):
    """A Game that was never started, with change_state and the running handler stubbed out."""
    instance = game.Game.__new__(game.Game)
    instance.campaign = load_campaign()
    instance.level_counter = level_counter
    instance.start_level = 1
    instance.profile = Profile()  # never saved
    instance._state_handlers = {}
    instance.requested_states = []
    instance.change_state = instance.requested_states.append
    monkeypatch.setattr(game, "RunningStateHandler", lambda g: "fresh handler")
    return instance


def test_level_up_advances_to_next_level(monkeypatch):
    instance = make_game(monkeypatch, level_counter=1)
    instance.level_up()
    assert instance.level_counter == 2
    assert instance._state_handlers[game.StateID.RUNNING] == "fresh handler"
    assert instance.requested_states == [game.StateID.RUNNING]  # the new level opens with its mission


def test_level_up_after_last_level_wins(monkeypatch):
    last = len(load_campaign())
    instance = make_game(monkeypatch, level_counter=last)
    instance.level_up()
    assert instance.level_counter == last
    assert instance.requested_states == [game.StateID.VICTORY]


def test_finishing_an_arc_is_a_checkpoint(monkeypatch):
    campaign = load_campaign()
    first_arc, second_arc = campaign.arcs[:2]
    instance = make_game(monkeypatch, level_counter=first_arc.last)
    instance.level_up()
    assert instance.profile.arcs_done == [first_arc.name]
    assert instance.level_counter == second_arc.first
    assert instance.start_level == second_arc.first  # a game over in this arc restarts here


def test_play_opens_the_level_select_once_an_arc_is_done(monkeypatch):
    instance = make_game(monkeypatch, level_counter=1)
    restarts = []
    instance.restart = lambda: restarts.append(1)
    instance.play()
    assert restarts == [1] and instance.requested_states == []
    instance.profile.arcs_done.append(load_campaign().arcs[0].name)
    instance.play()
    assert instance.requested_states == [game.StateID.SELECT]


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
