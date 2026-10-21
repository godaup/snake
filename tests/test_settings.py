import json

import pytest
import pyxel

from snake_quest.profile import SCREEN_MODES, Profile
from snake_quest.sound import EFFECT_CHANNEL, FULL_GAIN, MUSIC, VOLUME_STEPS, SoundManager
from snake_quest.states import StateID
from snake_quest.states.menu import MenuStateHandler
from snake_quest.states.menu_common import MENU_MUSIC
from snake_quest.states.settings import ITEMS, SettingsStateHandler


def test_the_menu_leads_to_the_settings(game):
    dict(MenuStateHandler(game).items)["SETTINGS"]()
    assert game.requested_states == [StateID.SETTINGS]


def test_settings_round_trip(tmp_path):
    path = tmp_path / "profile.json"
    profile = Profile.load(path)
    assert (profile.music_volume, profile.sound_volume, profile.fullscreen, profile.screen_mode) == (
        VOLUME_STEPS,
        VOLUME_STEPS,
        False,
        0,
    )
    profile.music_volume, profile.sound_volume, profile.fullscreen, profile.screen_mode = 3, 0, True, 2
    profile.save()
    loaded = Profile.load(path)
    assert (loaded.music_volume, loaded.sound_volume, loaded.fullscreen, loaded.screen_mode) == (3, 0, True, 2)


@pytest.mark.parametrize("odd", [-1, VOLUME_STEPS + 1, "5", 2.5, True, None])
def test_odd_saved_settings_fall_back_to_the_defaults(tmp_path, odd):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"music_volume": odd, "screen_mode": odd, "fullscreen": "yes"}))
    profile = Profile.load(path)
    assert (profile.music_volume, profile.screen_mode, profile.fullscreen) == (VOLUME_STEPS, 0, False)


def gains():
    return [round(channel.gain, 4) for channel in pyxel.channels]


def test_volumes_set_the_channel_gains(assets):
    sound = SoundManager()
    sound.set_volume(music=5, sound=2)
    sound.play(MUSIC["garden"])  # three channels: the effect channel keeps the effect volume
    assert gains() == [FULL_GAIN / 2] * 3 + [FULL_GAIN * 2 / VOLUME_STEPS]
    sound.play(MENU_MUSIC)  # the theme plays on all four
    assert gains() == [FULL_GAIN / 2] * 4
    sound.effect("eat")
    assert gains()[EFFECT_CHANNEL] == round(FULL_GAIN * 2 / VOLUME_STEPS, 4)
    sound.set_volume(music=VOLUME_STEPS, sound=VOLUME_STEPS)
    assert gains() == [FULL_GAIN] * 4
    pyxel.stop()


def test_silent_music_starts_again_when_turned_up(assets, monkeypatch):
    sound = SoundManager()
    sound.set_volume(music=0)
    played = []
    monkeypatch.setattr(pyxel, "play", lambda channel, *args, **kwargs: played.append(channel))
    sound.play(MENU_MUSIC)
    sound.effect("eat")
    assert played == [EFFECT_CHANNEL]  # no music at all, the effects still play
    sound.set_volume(music=1)
    assert played == [EFFECT_CHANNEL, 0, 1, 2, 3]


def test_no_effects_at_zero_volume(assets, monkeypatch):
    sound = SoundManager()
    sound.set_volume(sound=0)
    played = []
    monkeypatch.setattr(pyxel, "play", lambda *args, **kwargs: played.append(args))
    sound.effect("eat")
    assert not played


def test_changing_a_setting_applies_it_at_once(game):
    screen = SettingsStateHandler(game)
    screen.change("MUSIC", -1)
    screen.change("SOUND", -3)
    screen.change("FULLSCREEN", 1)
    screen.change("SCREEN", -1)
    profile = game.profile
    assert (profile.music_volume, profile.sound_volume) == (VOLUME_STEPS - 1, VOLUME_STEPS - 3)
    assert profile.fullscreen and profile.screen_mode == len(SCREEN_MODES) - 1
    assert game.settings_applied == 4
    assert game.sm.effects_played == ["eat"]  # the new sound volume is heard


def test_volumes_stop_at_their_ends(game):
    screen = SettingsStateHandler(game)
    screen.change("MUSIC", 1)
    assert game.profile.music_volume == VOLUME_STEPS
    for _ in range(VOLUME_STEPS + 2):
        screen.change("SOUND", -1)
    assert game.profile.sound_volume == 0


def test_settings_screen_draws_every_item(assets, game):
    screen = SettingsStateHandler(game)
    game.profile.music_volume = 0
    for selected in range(len(ITEMS)):
        screen.selected = selected
        screen.update()
        screen.draw()
    assert screen.get_music() == MENU_MUSIC and screen.is_visible()
