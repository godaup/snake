import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.caves import Mole
from snake_quest.controls import PathController
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import EMPTY_TILE, WALL_TILES, WALL_VARIANT_ROW
from snake_quest.utils import Vec2
from snake_quest.weapons import Projectile

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def moles(assets, game):
    game.level_counter = CAMPAIGN.resolve("moles")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(0, 22):  # rock with a room in its left half
        for tx in range(0, 32):
            tilemap.pset(tx, ty, EMPTY_TILE if 0 < tx < 15 and 0 < ty < 21 else (0, 3))
    level_map._autotile_walls()
    return level_map


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def test_digging_turns_rock_into_floor_and_retiles_around(moles):
    tilemap = pyxel.tilemaps[moles.tm]
    version = moles.walls_version
    assert moles.dig((20, 10))
    assert tilemap.pget(20, 10) == EMPTY_TILE and moles.walls_version == version + 1
    # the rock around it shows its new open side: west of (21, 10) is open now
    assert tilemap.pget(21, 10)[1] == WALL_VARIANT_ROW and not tilemap.pget(21, 10)[0] & 8
    assert not moles.dig((20, 10))  # floor already
    assert not moles.dig((0, 10))  # the border stays closed
    assert tilemap.pget(0, 10) in WALL_TILES


def test_digging_resets_the_bots_and_hunters_maps(moles):
    snake = snake_at(Vec2(60, 80 + moles.header))
    bot = PathController(lambda snake, map: None)
    cell = bot._cell(moles.tile_center((20, 10)))
    assert bot._wall(moles, cell)
    moles.chase(snake)
    moles.dig((20, 10))
    assert not moles._fields  # the walking distances are computed anew
    assert not bot._wall(moles, cell)


def test_a_mole_digs_a_wide_tunnel_underground(moles):
    mole = Mole.at_pos(Vec2(100, 80 + moles.header))
    mole.goal = moles.tile_center((25, 10))
    snake = snake_at(Vec2(40, 140 + moles.header))
    for _ in range(24 * 6):
        mole.left = 10  # stays down
        mole.goal = moles.tile_center((25, 10))
        mole.update(snake, moles)
    tilemap = pyxel.tilemaps[moles.tm]
    assert all(tilemap.pget(x, y) == EMPTY_TILE for x in range(16, 24) for y in (9, 10, 11))
    assert mole.dug > 0


def test_underground_moles_cannot_be_hit_or_touched(moles):
    mole = Mole.at_pos(Vec2(100, 80 + moles.header))
    moles.entities.append(mole)
    assert not mole.exposed and not mole.covers(mole.center) and not mole.avoid
    shot = Projectile(mole.center - Vec2(6, 0), 0, 3, 1, 10)
    moles.projectiles.append(shot)
    for _ in range(4):
        shot.update(moles, FRAME)
    assert mole.alive


def test_a_mole_comes_up_away_from_the_snake_and_dives_again(moles):
    mole = Mole.at_pos(Vec2(60, 80 + moles.header))
    snake = snake_at(Vec2(40, 140 + moles.header))
    mole.left = 0
    mole.goal = mole.center
    mole.update(snake, moles)
    assert mole.state == "up" and mole.exposed
    for _ in range(round(Mole.UP / FRAME) + 1):
        mole.update(snake, moles)
    assert mole.state == "under"


def test_a_surfaced_mole_is_shot_or_bites(moles):
    mole = Mole.at_pos(Vec2(60, 80 + moles.header))
    mole.state, mole.left = "up", Mole.UP
    moles.entities.append(mole)
    shot = Projectile(mole.center - Vec2(6, 0), 0, 3, 1, 10)
    for _ in range(3):
        shot.update(moles, FRAME)
    assert not mole.alive and mole.killed
    biter = Mole.at_pos(Vec2(60, 80 + moles.header))
    biter.state = "up"
    snake = snake_at(Vec2(64, 84 + moles.header))
    biter.on_intersect(snake, moles)
    assert len(snake) == 20 - Mole.BITE and biter.state == "under"


def test_no_mole_comes_up_next_to_the_snake(moles):
    mole = Mole.at_pos(Vec2(60, 80 + moles.header))
    snake = snake_at(Vec2(66, 84 + moles.header))
    mole.left = 0
    mole.goal = mole.center
    mole.update(snake, moles)
    assert mole.state == "under"
