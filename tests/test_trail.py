import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.map import TRAIL_GAP, Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import (
    EMPTY_TILE,
    EXIT_TILE,
    TRAIL_CRUMBLE,
    TRAIL_CRUMBLE_TILE,
    TRAIL_TILE,
    TileKind,
    tile_kind,
)
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def trail(assets, game):
    game.level_counter = CAMPAIGN.resolve("trail")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    for ty in range(1, 21):  # an open square to play in
        for tx in range(1, 31):
            pyxel.tilemaps[level_map.tm].pset(tx, ty, EMPTY_TILE)
    return level_map


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def run(level_map, snake, frames):
    for _ in range(frames):
        snake.update(dt=level_map.game.dt, map=level_map)
        level_map.update(snake)


def test_the_trail_is_a_wall():
    assert tile_kind(TRAIL_TILE) == TileKind.WALL
    assert tile_kind(TRAIL_CRUMBLE_TILE) == TileKind.WALL


def test_the_tail_leaves_a_wall_behind(trail):
    snake = snake_at(Vec2(100, 80 + trail.header))
    start_tile = trail.tile_xy(snake.segs[-1].pos)
    run(trail, snake, 30)
    assert trail.tile_at(Vec2(start_tile[0] * 8, start_tile[1] * 8 + trail.header)) == TRAIL_TILE
    assert trail.check_on_wall(trail.tile_center(start_tile))
    # but never right at the head
    assert all((trail.tile_center(tile) - snake.head.pos).length() >= TRAIL_GAP - 8 for tile in trail.trail)


def test_a_short_snake_lays_no_trail_under_its_head(trail):
    snake = Snake(pos=Vec2(100, 80 + trail.header), orient=0, size=2)  # length 1, growing
    run(trail, snake, 3)
    assert trail.trail == {}
    assert not trail.check_on_wall(snake.head.pos)


def test_the_trail_crumbles_and_is_gone(trail):
    snake = snake_at(Vec2(100, 80 + trail.header))
    run(trail, snake, 1)
    (tile,) = trail.trail
    frames = round((trail.trail_seconds - TRAIL_CRUMBLE) / FRAME) + 2
    run(trail, snake, frames)
    assert pyxel.tilemaps[trail.tm].pget(*tile) == TRAIL_CRUMBLE_TILE
    run(trail, snake, round(TRAIL_CRUMBLE / FRAME) + 2)
    assert tile not in trail.trail
    assert pyxel.tilemaps[trail.tm].pget(*tile) == EMPTY_TILE


def test_special_tiles_stay(trail):
    snake = snake_at(Vec2(100, 80 + trail.header))
    tile = trail.tile_xy(snake.segs[-1].pos)
    pyxel.tilemaps[trail.tm].pset(*tile, EXIT_TILE)
    run(trail, snake, 1)
    assert tile not in trail.trail
    assert pyxel.tilemaps[trail.tm].pget(*tile) == EXIT_TILE


def test_hunters_cannot_walk_through_the_trail(trail):
    snake = snake_at(Vec2(100, 80 + trail.header))
    run(trail, snake, 1)
    (tile,) = trail.trail
    assert tile not in trail.walking_distances(trail.tile_center((tile[0] - 2, tile[1])))


def test_the_bot_sees_the_trail_come_and_go(trail):
    bot = PathController(lambda snake, map: None)
    snake = snake_at(Vec2(100, 80 + trail.header))
    run(trail, snake, 1)
    (tile,) = trail.trail
    cell = bot._cell(trail.tile_center(tile))
    assert bot._wall(trail, cell)
    run(trail, snake, round(trail.trail_seconds / FRAME) + 2)
    assert tile not in trail.trail
    assert not bot._wall(trail, cell)  # not cached as a wall


def test_the_bot_knows_its_body_leaves_walls(trail):
    bot = PathController(lambda snake, map: None)
    snake = snake_at(Vec2(100, 80 + trail.header))
    plain = bot._vacate(snake)
    lingering = bot._vacate(snake, trail)
    cell = bot._cell(snake.segs[-1].pos)
    assert lingering[cell] == plain[cell] + trail.trail_seconds * trail.game.cfg.fps


def test_levels_without_a_trail_lay_none(assets, game):
    game.level_counter = CAMPAIGN.resolve("classic")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    assert level_map.trail_seconds == 0
