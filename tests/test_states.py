import datetime

import pytest
import pyxel

from snake_quest import sound
from snake_quest.states import StateID
from snake_quest.states.countdown import CountdownHandler
from snake_quest.states.death import DeathStateHandler
from snake_quest.states.menu import MenuStateHandler
from snake_quest.states.pause import PauseStateHandler
from snake_quest.states.running import RunningStateHandler


@pytest.mark.parametrize(
    "handler_cls", [MenuStateHandler, PauseStateHandler, RunningStateHandler, DeathStateHandler, CountdownHandler]
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


def test_sound_manager_respects_music_setting(monkeypatch):
    played = []
    monkeypatch.setattr(pyxel, "playm", lambda msc, loop=None: played.append(msc))
    sound.SoundManager(music=False).play(music=1)
    assert played == []
    sound.SoundManager(music=True).play(music=1)
    assert played == [1]


def test_sound_manager_plays_music_zero(monkeypatch):
    played = []
    monkeypatch.setattr(pyxel, "playm", lambda msc, loop=None: played.append(msc))
    sound.SoundManager(music=True).play(music=0)
    assert played == [0]
