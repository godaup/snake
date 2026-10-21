import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.caves import Bat, Burning, Crystal, FlarePickup
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import EMPTY_TILE, TORN_WEB_TILE, WALL_VARIANT_ROW
from snake_quest.utils import Vec2
from snake_quest.weapons import Flare, FlareShot

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def bats(assets, game):
    game.level_counter = CAMPAIGN.resolve("bats")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(0, 30):  # an open room, walled in
        for tx in range(0, 40):
            wall = tx in (0, 39) or ty in (0, 29)
            tilemap.pset(tx, ty, (15, WALL_VARIANT_ROW) if wall else EMPTY_TILE)
    return level_map


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def test_bats_sleep_in_the_dark_and_wake_in_any_light(bats):
    snake = snake_at(Vec2(40, 40 + bats.header))
    bat = Bat.at_pos(Vec2(200, 160 + bats.header))
    bat.update(snake, bats)
    assert bat.asleep
    crystal = Crystal.at_pos(Vec2(206, 160 + bats.header))  # glows right next to it
    bats.entities.append(crystal)
    bat.update(snake, bats)
    assert bat.state == "fly"


def test_the_snakes_light_wakes_them(bats):
    bat = Bat.at_pos(Vec2(100, 80 + bats.header))
    snake = snake_at(Vec2(100 + bats.darkness.light - 10, 80 + bats.header))
    bat.update(snake, bats)
    assert not bat.asleep


def test_a_bat_bites_the_body_and_flies_off(bats):
    snake = snake_at(Vec2(100, 80 + bats.header), length=20)
    bat = Bat.at_pos(Vec2(80, 76 + bats.header))
    bat.state = "fly"
    bat.update(snake, bats)
    assert len(snake) < 20 and bat.state == "retreat"
    length = len(snake)
    bat.update(snake, bats)
    assert len(snake) == length  # once


def test_bats_flee_from_a_burning_flare(bats):
    snake = snake_at(Vec2(40, 40 + bats.header))
    flare = Burning.at_pos(Vec2(150, 100 + bats.header))
    bats.entities.append(flare)
    bat = Bat.at_pos(Vec2(160, 100 + bats.header))
    bat.state = "fly"
    bat.heading = 0
    for _ in range(24):
        bat.update(snake, bats)
    assert (bat.center - flare.center).length() > (Vec2(164, 104 + bats.header) - flare.center).length()


def test_in_the_dark_for_long_a_bat_flies_home_to_sleep(bats):
    snake = snake_at(Vec2(40, 40 + bats.header))
    bat = Bat.at_pos(Vec2(250, 180 + bats.header))
    bat.state = "fly"
    for _ in range(round((Bat.ROOST + 6) / FRAME)):
        bat.update(snake, bats)
        snake.segs[0].pos = Vec2(40, 40 + bats.header)  # the snake stays away
    assert bat.asleep and bat.pos == bat.roost


def test_a_flare_comes_to_rest_and_burns(bats):
    snake = snake_at(Vec2(100, 80 + bats.header))
    snake.weapon = Flare(ammo=2)
    snake.weapon.update(snake, bats, fire=True, seconds=FRAME)
    (shot,) = bats.projectiles
    assert isinstance(shot, FlareShot)
    for _ in range(round(Flare.LIFETIME / FRAME) + 2):
        shot.update(bats, FRAME, snake)
    (burning,) = [ent for ent in bats.entities if isinstance(ent, Burning)]
    assert burning.light > 0 and (burning.center - snake.head.pos).length() > 40
    for _ in range(round(Burning.BURN / FRAME) + 1):
        burning.update(snake, bats)
    assert not burning.alive


def test_a_flare_burns_webs(bats):
    snake = snake_at(Vec2(40, 40 + bats.header))
    tile = (20, 10)
    bats.spin_web(tile)
    flare = Burning.at_pos(bats.tile_center(tile) - Vec2(4, 4))
    flare.update(snake, bats)
    assert pyxel.tilemaps[bats.tm].pget(*tile) == TORN_WEB_TILE


def test_a_flare_pickup_gives_flares():
    assert FlarePickup.WEAPON == "Flare" and Flare.name == "FLARE"


def test_the_level_is_dark_with_flares_to_find(assets, game):
    game.level_counter = CAMPAIGN.resolve("bats")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    assert level_map.darkness is not None
    assert any(timer for timer in level_map.cfg.timers.values() if timer.callback.entity == "flare")
