import datetime
from pathlib import Path

import pytest
import pyxel

from snake_quest import sound
from snake_quest.states import StateID
from snake_quest.states.countdown import CountdownHandler
from snake_quest.states.death import DeathStateHandler
from snake_quest.states.menu import MenuStateHandler
from snake_quest.states.pause import PauseStateHandler
from snake_quest.states.running import RunningStateHandler
from snake_quest.states.victory import VictoryStateHandler


@pytest.mark.parametrize(
    "handler_cls",
    [
        MenuStateHandler,
        PauseStateHandler,
        RunningStateHandler,
        DeathStateHandler,
        CountdownHandler,
        VictoryStateHandler,
    ],
)
def test_handlers_construct_update_and_draw(assets, game, handler_cls):
    handler = handler_cls(game)
    handler.update()
    handler.draw()


def test_running_shows_mission_once(assets, game):
    handler = RunningStateHandler(game)
    handler.update()
    handler.update()
    assert game.requested_states == [StateID.MISSION]


def test_countdown_counts_down_then_go_then_running(game):
    game.dt = datetime.timedelta(seconds=0.5)
    handler = CountdownHandler(game)
    handler.on_enter()
    shown = [handler.label()]
    for _ in range(7):
        handler.update()
        shown.append(handler.label())
    assert shown == ["3", "3", "2", "2", "1", "1", "GO!", "GO!"]
    assert game.requested_states == []
    handler.update()
    assert game.requested_states == [StateID.RUNNING]


def test_countdown_pulses_from_big_to_normal(game):
    handler = CountdownHandler(game)
    handler.on_enter()
    big = handler.scale()
    game.dt = datetime.timedelta(seconds=0.9)
    handler.update()
    assert handler.label() == "3"
    assert handler.scale() < big


def test_center_text(game):
    handler = PauseStateHandler(game)
    text = "abcd"
    assert handler.center_text(text) * 2 + len(text) * pyxel.FONT_WIDTH == game.cfg.width


@pytest.mark.parametrize(("handler_cls", "visible"), [(MenuStateHandler, True), (RunningStateHandler, False)])
def test_mouse_visibility(handler_cls, visible):
    assert handler_cls.is_visible() is visible


@pytest.fixture
def played(monkeypatch):
    """Record pyxel.play calls; pyxel.playm must never be used (it can deadlock, see SoundManager.play)."""
    calls = []
    monkeypatch.setattr(
        pyxel, "play", lambda ch, snd, loop=None: calls.append((ch, snd if isinstance(snd, int) else list(snd), loop))
    )
    monkeypatch.setattr(pyxel, "playm", lambda *a, **kw: pytest.fail("pyxel.playm can deadlock in Pyxel 2.9.9"))
    return calls


def test_sound_manager_starts_every_channel_of_a_music(assets, played):
    sound.SoundManager(music=True).play(music=1)
    assert [(ch, loop) for ch, _, loop in played] == [(0, True), (1, True), (2, True), (3, True)]
    assert [snd for _, snd, _ in played] == [list(seq) for seq in pyxel.musics[1].seqs]


def test_sound_manager_respects_music_setting(assets, played):
    sound.SoundManager(music=False).play(music=1)
    assert played == []


def test_sound_manager_plays_music_zero(assets, played):
    pyxel.musics[0].set([8], [], [], [])  # music 0 is a real music, not "no music"
    sound.SoundManager(music=True).play(music=0)
    assert played == [(0, [8], True)]


def test_empty_music_makes_no_audio_calls(assets, played):
    pyxel.musics[0].set([], [], [], [])
    sound.SoundManager(music=True).play(music=0)
    assert played == []


def test_effects_play_on_their_own_channel(played):
    sound.SoundManager(effects=True).effect("eat")
    assert played == [(sound.EFFECT_CHANNEL, sound.EFFECTS["eat"], None)]


def test_effects_respect_the_setting(played):
    sound.SoundManager(effects=False).effect("eat")
    assert played == []


def test_effects_have_sounds_apart_from_the_music(assets):
    theme = {snd for seq in pyxel.musics[1].seqs for snd in seq}
    for name, slot in sound.EFFECTS.items():
        assert len(pyxel.sounds[slot].notes) > 0, name
        assert slot not in theme, name


def test_death_and_level_complete_play_their_jingles(assets, game):
    from snake_quest.states.death import DeathStateHandler
    from snake_quest.states.level_complete import LevelCompleteStateHandler

    DeathStateHandler(game).on_enter()
    LevelCompleteStateHandler(game).on_enter()
    assert game.sm.effects_played == ["death", "win"]


def test_game_code_never_calls_playm():
    """pyxel.playm deadlocks with the audio thread in Pyxel 2.9.9 (reproduced with tools/audio_stress.py)."""
    package = Path(sound.__file__).parent
    offenders = [str(p.relative_to(package)) for p in package.rglob("*.py") if "pyxel.playm(" in p.read_text()]
    assert offenders == []
