import datetime

import omegaconf
import pytest
import pyxel

from snake_quest import difficulty
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import GoldenApple, HomingPickup, Hunter, Knight
from snake_quest.goals import TimeLimitGoal
from snake_quest.map import Map
from snake_quest.snake import Snake
from snake_quest.space import Planet
from snake_quest.tiles import BELT_TILES, EMPTY_TILE, HAZARD_TILE, ICE_TILE, MIRROR_TILE, WEB_TILE
from snake_quest.utils import Vec2
from snake_quest.weapons import Homing, Projectile

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def gauntlet(assets, game):
    game.level_counter = CAMPAIGN.resolve("gauntlet")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    game.dt = datetime.timedelta(seconds=FRAME)
    return level_map


def open_square(level_map):
    level_map.entities.clear()
    level_map.timers.clear()
    for ty in range(1, 21):
        for tx in range(1, 31):
            pyxel.tilemaps[level_map.tm].pset(tx, ty, EMPTY_TILE)


def test_the_gauntlet_has_every_stretch_and_a_golden_apple_in_each(gauntlet):
    """A stretch from each arc before it: ice, mirrors, thorns, webs, belts and a planet."""
    tiles = {pyxel.tilemaps[gauntlet.tm].pget(x, y) for x in range(240) for y in range(32)}
    assert {ICE_TILE, MIRROR_TILE, HAZARD_TILE, WEB_TILE} <= tiles and set(BELT_TILES) & tiles
    assert any(isinstance(ent, Planet) for ent in gauntlet.entities)
    goldens = sorted(ent.pos.x for ent in gauntlet.entities if isinstance(ent, GoldenApple))
    assert len(goldens) == 7 and goldens[0] < 400 and goldens[-1] > 1600


def test_the_clock_runs_out(gauntlet):
    goal = next(goal for goal in gauntlet.goals if isinstance(goal, TimeLimitGoal))
    snake = Snake(pos=gauntlet.start, orient=0, size=2)
    assert goal.done(gauntlet, snake) and goal.status(gauntlet, snake) == "TIME 1:50"
    goal.update(gauntlet, snake, datetime.timedelta(seconds=109.5))
    assert goal.status(gauntlet, snake) == "TIME 0:01" and not gauntlet.snake_killed
    assert goal.progress(gauntlet, snake) == pytest.approx(0.5 / 110)
    goal.update(gauntlet, snake, datetime.timedelta(seconds=1))
    assert not goal.done(gauntlet, snake) and gauntlet.snake_killed


@pytest.mark.parametrize(("name", "seconds"), [("easy", 125), ("medium", 75), ("nightmare", 75 / 1.4)])
def test_easier_means_more_time(game, name, seconds):
    cfg = omegaconf.OmegaConf.create({"goal": {"time_limit": 75}})
    scaled = difficulty.apply(cfg, difficulty.load(game.cfg, name))
    assert scaled.goal.time_limit == pytest.approx(seconds)


def test_homing_shots_turn_to_a_target(gauntlet):
    open_square(gauntlet)
    beetle = Hunter.at_pos(Vec2(100, 60 + gauntlet.header))
    gauntlet.entities.append(beetle)
    shot = Projectile(Vec2(40, 100 + gauntlet.header), 0, 3.5, 1, 11, lifetime=2, homing=Homing.TURN)
    for _ in range(40):
        shot.update(gauntlet, FRAME)
    assert not beetle.alive and beetle.killed


def test_homing_shots_ignore_armour_they_cannot_pierce(gauntlet):
    open_square(gauntlet)
    gauntlet.entities.append(Knight.at_pos(Vec2(100, 60 + gauntlet.header)))
    shot = Projectile(Vec2(40, 100 + gauntlet.header), 0, 3.5, 1, 11, homing=Homing.TURN)
    shot.update(gauntlet, FRAME)
    assert shot.dir.y == 0  # straight on


def test_a_homing_pickup_gives_the_weapon(gauntlet):
    snake = Snake(pos=gauntlet.start, orient=0, size=2)
    HomingPickup.at_pos(Vec2(0, 0)).on_intersect(snake, gauntlet)
    assert isinstance(snake.weapon, Homing) and snake.weapon.ammo == HomingPickup.AMMO


def test_the_bot_finds_its_way_around_thorns(gauntlet):
    open_square(gauntlet)
    pyxel.tilemaps[gauntlet.tm].pset(10, 10, HAZARD_TILE)
    bot = PathController(lambda snake, map: None)
    thorns = bot._cell(gauntlet.tile_center((10, 10)))
    assert bot._wall(gauntlet, thorns)
    assert not gauntlet.check_on_wall(gauntlet.tile_center((10, 10)))  # but no wall in the game
