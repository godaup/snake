import omegaconf
import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.sound import EFFECT_CHANNEL, EFFECTS, MUSIC, MUSIC_CHANNELS
from snake_quest.states.countdown import CountdownHandler
from snake_quest.states.level_complete import LevelCompleteStateHandler
from snake_quest.states.menu_common import MENU_MUSIC
from snake_quest.states.mission import MissionStateHandler
from snake_quest.states.pause import PauseStateHandler
from snake_quest.states.running import RunningStateHandler

CAMPAIGN = load_campaign()
COMPOSED = ("garden",)  # tracks written so far by tools/compose_music.py


def level_music(level) -> str:
    return omegaconf.OmegaConf.load(level.path).get("music", level.music)


def test_every_level_plays_a_known_music():
    for level in CAMPAIGN.levels:
        assert level_music(level) in MUSIC, level.name


def test_boss_levels_play_the_boss_music():
    bosses = [level.name for level in CAMPAIGN.levels if "boss" in omegaconf.OmegaConf.load(level.path)]
    assert bosses and all(level_music(CAMPAIGN.level(CAMPAIGN.resolve(name))) == "boss" for name in bosses)


def test_the_menu_theme_has_its_own_slot():
    assert MENU_MUSIC not in MUSIC.values()


@pytest.mark.parametrize("name", COMPOSED)
def test_level_music_leaves_the_effect_channel_free(assets, name):
    seqs = [list(seq) for seq in pyxel.musics[MUSIC[name]].seqs]
    assert any(seqs[:MUSIC_CHANNELS]), "not composed"
    assert all(not seq for seq in seqs[MUSIC_CHANNELS:]) and EFFECT_CHANNEL >= MUSIC_CHANNELS
    sounds = {snd for seq in seqs for snd in seq}
    theme = {snd for seq in pyxel.musics[MENU_MUSIC].seqs for snd in seq}
    assert not sounds & (set(EFFECTS.values()) | theme)


def test_tracks_of_a_music_are_equally_long(assets):
    for name in COMPOSED:
        lengths = {round(pyxel.sounds[seq[0]].total_sec(), 2) for seq in pyxel.musics[MUSIC[name]].seqs if seq}
        assert len(lengths) == 1, name  # the voices loop together


@pytest.mark.parametrize(("level", "music"), [("classic", "garden"), ("hunger", "boss"), ("trail", "ouroboros")])
def test_a_level_plays_its_music(assets, game, level, music):
    game.level_counter = CAMPAIGN.resolve(level)
    assert RunningStateHandler(game).get_music() == MUSIC[music]


@pytest.mark.parametrize("handler_cls", [MissionStateHandler, CountdownHandler, PauseStateHandler])
def test_the_music_plays_on_over_the_level(assets, game, handler_cls):
    assert handler_cls(game).get_music() == game.running_handler.get_music()


def test_level_complete_is_quiet_for_its_jingle(assets, game):
    assert LevelCompleteStateHandler(game).get_music() is None
