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


def test_running_requests_countdown_once(assets, game):
    handler = RunningStateHandler(game)
    handler.update()
    handler.update()
    assert game.requested_states == [StateID.COUNTDOWN]


def test_countdown_resumes_running_after_three_seconds(game):
    game.dt = datetime.timedelta(seconds=0.75)
    handler = CountdownHandler(game)
    shown = []
    for _ in range(3):
        handler.update()
        shown.append(handler.wdg.img)
    assert shown == [handler.img_3, handler.img_2, handler.img_1]
    assert game.requested_states == []
    handler.update()
    assert game.requested_states == [StateID.RUNNING]
    assert not handler.wdg.enabled


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
    monkeypatch.setattr(pyxel, "play", lambda ch, snd, loop=None: calls.append((ch, list(snd), loop)))
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


def test_game_code_never_calls_playm():
    """pyxel.playm deadlocks with the audio thread in Pyxel 2.9.9 (reproduced with tools/audio_stress.py)."""
    package = Path(sound.__file__).parent
    offenders = [str(p.relative_to(package)) for p in package.rglob("*.py") if "pyxel.playm(" in p.read_text()]
    assert offenders == []
