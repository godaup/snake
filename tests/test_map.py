import datetime

import pytest
import pyxel

from entity import ALL_ENTITIES, Apple, Enemy, GoldenApple
from map import Map
from snake import Snake
from timers import Timer
from utils import Vec2

from .conftest import ROOT

LEVELS = sorted(int(p.stem) for p in (ROOT / "levels").glob("*.yaml") if p.stem.isdigit())


@pytest.fixture
def level_map(assets, game):
    return Map(level=1, game=game)


@pytest.mark.parametrize("level", LEVELS)
def test_level_loads(assets, game, level):
    level_map = Map(level=level, game=game)
    assert not level_map.check_on_wall(level_map.start)


@pytest.mark.parametrize("level", LEVELS)
def test_entity_tiles_are_moved_out_of_tilemap(assets, game, level):
    level_map = Map(level=level, game=game)
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    sprites = {(cls._img_x, cls._img_y) for cls in ALL_ENTITIES}
    for tile_x in range(level_map.cfg.width // 8):
        for tile_y in range(level_map.cfg.height // 8):
            assert tilemap.pget(tile_x, tile_y) not in sprites


def test_new_pos_is_free(level_map, game):
    snake = Snake(pos=level_map.start, orient=0, size=2)
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    for _ in range(50):
        pos = level_map.new_pos(snake=snake)
        for corner in [pos, pos + Vec2(8, 0), pos + Vec2(0, 8), pos + Vec2(8, 8)]:
            assert tilemap.pget(corner.x // 8, (corner.y - game.cfg.header.h) // 8) == (0, 0)
            assert not snake.covers(corner)
            assert not any(ent.covers(corner) for ent in level_map.entities)


def test_check_on_wall(level_map, game):
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    wall = next(
        (x, y)
        for x in range(level_map.cfg.width // 8)
        for y in range(level_map.cfg.height // 8)
        if tilemap.pget(x, y) == (0, 3)
    )
    assert level_map.check_on_wall(Vec2(wall[0] * 8 + 4, wall[1] * 8 + 4 + game.cfg.header.h))


def test_timers_are_created_from_level_config(level_map):
    assert len(level_map.timers) == len(level_map.cfg.timers)
    assert all(isinstance(timer, Timer) for timer in level_map.timers)


def test_spawn_callback(level_map):
    level_map.entities.clear()
    spawn = level_map.create_callback({"type": "spawn", "entity": "enemy", "pos": [16, 32]})
    spawn(map=level_map, snake=None)
    assert len(level_map.entities) == 1
    assert isinstance(level_map.entities[0], Enemy)
    assert level_map.entities[0].pos == Vec2(16, 32)


def test_grow_callback(level_map):
    snake = Snake(pos=level_map.start, orient=0, size=2)
    grow = snake.grow
    level_map.create_callback({"type": "grow", "value": 7})(map=level_map, snake=snake)
    assert snake.grow == grow + 7


def test_timer_spawns_through_map_update(level_map, game):
    level_map.entities.clear()
    snake = Snake(pos=level_map.start, orient=0, size=2)
    game.dt = datetime.timedelta(seconds=1.5)
    level_map.update(snake=snake)
    assert any(isinstance(ent, GoldenApple) for ent in level_map.entities)


def test_dead_entities_are_removed_on_update(level_map):
    apple = Apple.at_pos(Vec2(0, 0))
    apple.alive = False
    level_map.entities.append(apple)
    level_map.update(snake=Snake(pos=level_map.start, orient=0, size=2))
    assert apple not in level_map.entities


def test_check_win_counts_score_from_level_start(assets, game):
    game.score = 50
    level_map = Map(level=1, game=game)
    snake = Snake(pos=level_map.start, orient=0, size=2)
    goal = level_map.cfg.goal.score
    game.score = 50 + goal - 1
    assert not level_map.check_win(snake=snake)
    game.score = 50 + goal
    assert level_map.check_win(snake=snake)


def test_check_win_length_goal(level_map):
    level_map.cfg.goal = {"length": 3}
    snake = Snake(pos=level_map.start, orient=0, size=2)
    assert not level_map.check_win(snake=snake)
    snake.segs *= 3
    assert level_map.check_win(snake=snake)
