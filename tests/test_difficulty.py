import datetime
import json

import omegaconf
import pytest
import pyxel

from snake_quest import difficulty
from snake_quest.campaign import load_campaign
from snake_quest.cli import build_parser, settings_overrides
from snake_quest.map import Map
from snake_quest.profile import Profile
from snake_quest.snake import INIT_SPEED
from snake_quest.states.highscores import HighscoresStateHandler
from snake_quest.states.menu import DIFFICULTY_ITEM, MenuStateHandler
from snake_quest.states.running import RunningStateHandler

CAMPAIGN = load_campaign()
DAY = datetime.date(2026, 10, 19)
LEVEL = {
    "goal": {"score": 20, "hold_length": {"length": 50, "seconds": 25}, "collect_all": "golden"},
    "timers": {
        "apples": {"duration": 10, "frequency": 4, "fire_n": 0, "callback": {"type": "spawn", "entity": "apple"}},
        "enemies": {"duration": 8, "frequency": 20, "fire_n": 0, "callback": {"type": "spawn", "entity": "enemy"}},
        "grow": {"duration": 1, "frequency": 2, "fire_n": 0, "callback": {"type": "grow", "value": 3}},
    },
    "darkness": {"light": 40},
    "boss": {
        "type": "hunger",
        "rise": 0.04,
        "meal": 0.5,
        "starve": 2,
        "light": [40, 20],
        "phases": [{"after": 0}, {"after": 30, "rise": 0.06}],
    },
}


@pytest.fixture
def settings(game):
    return game.cfg


def scaled(settings, name, level=None):
    return difficulty.apply(omegaconf.OmegaConf.create(level or LEVEL), difficulty.load(settings, name))


def test_four_difficulties_with_medium_as_reference(settings):
    assert difficulty.NAMES == ("easy", "medium", "hard", "nightmare")
    assert difficulty.load(settings, "medium") == difficulty.Difficulty("medium")
    assert difficulty.load(settings, "bogus").name == "medium"
    hard = difficulty.load(settings, "hard")
    assert hard.goals > 1 and hard.helpful > 1 and hard.hostile < 1 and hard.light < 1
    assert hard.label == "HARD"


def test_harder_means_harder_for_every_factor(settings):
    levels = [difficulty.load(settings, name) for name in difficulty.NAMES]
    for easier, harder in zip(levels, levels[1:], strict=False):
        assert easier.speed < harder.speed
        assert easier.goals < harder.goals
        assert easier.helpful < harder.helpful
        assert easier.hostile > harder.hostile
        assert easier.boss < harder.boss
        assert easier.light > harder.light


def test_next_name_wraps():
    assert difficulty.next_name("nightmare") == "easy"
    assert difficulty.next_name("easy", -1) == "nightmare"


def test_medium_leaves_a_level_as_it_is(settings):
    assert omegaconf.OmegaConf.to_container(scaled(settings, "medium")) == LEVEL


def test_harder_levels_scale_goals_timers_light_and_boss(settings):
    hard = difficulty.load(settings, "hard")
    cfg = scaled(settings, "hard")
    assert cfg.goal.score == round(20 * hard.goals)
    assert cfg.goal.hold_length == {"length": round(50 * hard.goals), "seconds": round(25 * hard.goals)}
    assert cfg.goal.collect_all == "golden"
    assert cfg.timers.apples.frequency == pytest.approx(4 * hard.helpful)  # apples come more rarely
    assert cfg.timers.apples.duration == pytest.approx(10 * hard.helpful)
    assert cfg.timers.enemies.frequency == pytest.approx(20 * hard.hostile)  # enemies more often
    assert cfg.timers.grow.frequency == 2  # not a spawn
    assert cfg.darkness.light == pytest.approx(40 * hard.light)
    assert cfg.boss.rise == pytest.approx(0.04 * hard.boss)
    assert cfg.boss.starve == pytest.approx(2 * hard.boss)
    assert cfg.boss.meal == pytest.approx(0.5 / hard.boss)
    assert cfg.boss.phases[1].rise == pytest.approx(0.06 * hard.boss)
    assert list(cfg.boss.light) == pytest.approx([40 * hard.light, 20 * hard.light])


def test_whole_numbers_stay_whole_and_at_least_one(settings):
    cfg = scaled(settings, "easy", {"goal": {"score": 1}})
    assert cfg.goal.score == 1 and isinstance(cfg.goal.score, int)


def test_level_overrides_win_over_scaling(settings):
    level = {**LEVEL, "difficulty": {"hard": {"goal": {"score": 70}}}}
    assert scaled(settings, "hard", level).goal.score == 70
    assert scaled(settings, "easy", level).goal.score == round(20 * difficulty.load(settings, "easy").goals)


def test_map_and_snake_follow_the_profile_difficulty(assets, game):
    game.profile.difficulty = "nightmare"
    nightmare = game.difficulty
    level_map = Map(level=CAMPAIGN.level(1), game=game)
    medium = omegaconf.OmegaConf.load(CAMPAIGN.level(1).path)
    assert level_map.cfg.goal.score == round(medium.goal.score * nightmare.goals)
    running = RunningStateHandler(game)
    assert running.snake.speed == pytest.approx(INIT_SPEED * nightmare.speed)


def test_command_line_difficulty_wins_over_the_profile(game):
    args = build_parser().parse_args(["--difficulty", "easy"])
    assert settings_overrides(args) == {"start_difficulty": "easy"}
    game.cfg.start_difficulty = "easy"
    game.profile.difficulty = "hard"
    assert game.difficulty.name == "easy"


def test_separate_highscore_tables(tmp_path):
    profile = Profile(path=tmp_path / "profile.json")
    assert profile.add_highscore(100, 2, "hard", date=DAY) == 1
    assert profile.add_highscore(50, 1, "easy", date=DAY) == 1
    assert profile.add_highscore(70, 1, "easy", date=DAY) == 1
    profile.difficulty = "hard"
    profile.save()
    loaded = Profile.load(tmp_path / "profile.json")
    assert [h.score for h in loaded.table("easy")] == [70, 50]
    assert [h.score for h in loaded.table("hard")] == [100]
    assert loaded.table("medium") == []
    assert loaded.difficulty == "hard"


def test_old_single_table_becomes_medium(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"palette": "garden", "highscores": [{"score": 9, "level": 1, "date": "2026-10-18"}]}))
    profile = Profile.load(path)
    assert [h.score for h in profile.table("medium")] == [9]
    assert profile.difficulty == "medium"


def test_unknown_difficulty_in_the_file_falls_back(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps({"difficulty": "godlike", "highscores": {"godlike": [{"score": 1, "level": 1, "date": "x"}]}})
    )
    profile = Profile.load(path)
    assert profile.difficulty == "medium"
    assert profile.highscores == {}


def test_menu_switches_difficulty(game, monkeypatch):
    menu = MenuStateHandler(game)
    assert menu.label(DIFFICULTY_ITEM) == "DIFFICULTY  MEDIUM"
    dict(menu.items)["DIFFICULTY"]()  # enter: the next one
    assert game.profile.difficulty == "hard"
    menu.selected = DIFFICULTY_ITEM
    pressed = {pyxel.KEY_LEFT}
    monkeypatch.setattr(pyxel, "btnp", lambda key, hold=0, repeat=0: key in pressed)
    menu.update()
    assert game.profile.difficulty == "medium"


def test_highscores_screen_pages_through_the_tables(assets, game, monkeypatch):
    game.profile.add_highscore(77, 3, "nightmare", "The Garden", date=DAY)
    game.profile.difficulty = "hard"
    screen = HighscoresStateHandler(game)
    screen.on_enter()
    assert screen.shown == "hard" and screen.rows() == []
    pressed = {pyxel.KEY_RIGHT}
    monkeypatch.setattr(pyxel, "btnp", lambda key, hold=0, repeat=0: key in pressed)
    screen.update()
    assert screen.shown == "nightmare"
    assert "77" in screen.rows()[0]
