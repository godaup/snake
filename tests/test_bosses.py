import datetime

import omegaconf
import pytest
import pyxel

from snake_quest.bosses import BOSSES, AlphaBoss, CoreBoss, Hunger, OuroborosBoss, load_boss
from snake_quest.campaign import load_campaign
from snake_quest.entity import Apple
from snake_quest.hud import BOSS_BAR_W, COL_BOSS
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.states.running import RunningStateHandler
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
SECOND = datetime.timedelta(seconds=1)


def cfg(**values):
    base = {"type": "hunger", "rise": 0.1, "meal": 0.5, "starve": 4, "light": [40, 20]}
    return omegaconf.OmegaConf.create({**base, **values})


@pytest.fixture
def hunger_map(assets, game):
    game.level_counter = CAMPAIGN.resolve("hunger")
    return Map(level=CAMPAIGN.level(game.level_counter), game=game)


def long_snake(n=30):
    snake = Snake(pos=Vec2(100, 100), orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(100 - i, 100), 2, 0) for i in range(1, n)]
    return snake


def test_registry_and_unknown_type(hunger_map):
    assert {"hunger": Hunger, "alpha": AlphaBoss, "core": CoreBoss, "ouroboros": OuroborosBoss} == BOSSES
    with pytest.raises(ValueError, match="unknown boss"):
        load_boss(omegaconf.OmegaConf.create({"type": "dragon"}), hunger_map)


def test_hunger_level_has_its_boss_and_darkness(hunger_map):
    assert isinstance(hunger_map.boss, Hunger)
    assert hunger_map.darkness is not None


def test_phases_start_by_time_and_settings_fall_back_to_the_boss(hunger_map):
    boss = Hunger(cfg(phases=[{"after": 0}, {"after": 2, "rise": 0.3}]), hunger_map)
    snake = long_snake()
    assert boss.setting("rise") == 0.1
    assert boss.label() == "THE HUNGER I"
    boss.update(hunger_map, snake, SECOND)
    assert boss.phase == 0
    boss.update(hunger_map, snake, SECOND)
    assert boss.phase == 1
    assert boss.setting("rise") == 0.3
    assert boss.setting("meal") == 0.5
    assert boss.since_phase == 0
    assert boss.label() == "THE HUNGER II"


def test_one_phase_has_no_number(hunger_map):
    assert Hunger(cfg(), hunger_map).label() == "THE HUNGER"


def test_hunger_rises_and_meals_ease_it(hunger_map):
    boss = Hunger(cfg(), hunger_map)
    snake = long_snake()
    for _ in range(5):
        boss.update(hunger_map, snake, SECOND)
    assert boss.bar(hunger_map, snake) == pytest.approx(0.5)
    hunger_map.eaten += 1
    boss.update(hunger_map, snake, SECOND)
    assert boss.hunger == pytest.approx(0.1)


def test_the_hungrier_the_faster_it_shrinks_and_the_smaller_the_light(hunger_map):
    boss = Hunger(cfg(rise=1.0), hunger_map)
    snake = long_snake(30)
    boss.update(hunger_map, snake, SECOND)  # hunger 1 at once: 4 segments per second
    assert len(snake) == 26
    assert hunger_map.darkness.light == pytest.approx(20)
    boss.hunger, boss.cfg.rise = 0.0, 0.0
    boss.update(hunger_map, snake, SECOND)
    assert len(snake) == 26
    assert hunger_map.darkness.light == pytest.approx(40)


def test_starving_kills(hunger_map):
    boss = Hunger(cfg(rise=1.0, starve=10), hunger_map)
    snake = long_snake(5)
    boss.update(hunger_map, snake, SECOND)
    assert hunger_map.snake_killed


def test_map_counts_meals_but_not_kills(hunger_map):
    eaten, killed = Apple.at_pos(Vec2(40, 40)), Apple.at_pos(Vec2(60, 60))
    hunger_map.entities += [eaten, killed]
    eaten.alive = False
    killed.health = 1
    killed.hit(1)
    hunger_map.update(long_snake())
    assert (hunger_map.eaten, hunger_map.defeated) == (1, 1)


def test_hud_draws_the_boss_bar(assets, game):
    game.level_counter = CAMPAIGN.resolve("hunger")
    running = RunningStateHandler(game)
    running.map.boss.hunger = 1.0
    running.cam.update()
    running.draw()
    y = game.cfg.header.h + 2 + pyxel.FONT_HEIGHT // 2
    row = [pyxel.pget(x, y) for x in range(game.cfg.width)]
    assert row.count(COL_BOSS) >= BOSS_BAR_W  # the full bar, plus the label's red pixels


@pytest.mark.parametrize(("phase", "shown"), [(0, False), (1, True)])
def test_phase_banner_shows_after_a_phase_change(assets, game, monkeypatch, phase, shown):
    monkeypatch.setattr(pyxel, "frame_count", 0, raising=False)  # the banner blinks
    game.level_counter = CAMPAIGN.resolve("hunger")
    running = RunningStateHandler(game)
    running.map.boss.phase, running.map.boss.since_phase = phase, 0.0
    running.draw()
    assert (running.hud.banner_text.text == "THE HUNGER GROWS") is shown
