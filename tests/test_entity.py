from types import SimpleNamespace

import pytest

from snake_quest.entity import ALL_ENTITIES, Apple, Enemy, Entity, GoldenApple
from snake_quest.map import FLOOR_TILES, PATH_TILE, WALL_TILES
from snake_quest.snake import Snake
from snake_quest.utils import Vec2


@pytest.fixture
def map():
    return SimpleNamespace(game=SimpleNamespace(score=0), entities=[], new_pos=lambda snake=None: Vec2(40, 40))


@pytest.fixture
def snake():
    return Snake(pos=Vec2(0, 0), orient=0, size=2)


def test_at_pos_uses_sprite_tile():
    apple = Apple.at_pos(Vec2(8, 16))
    assert (apple.img_x, apple.img_y) == (8 * Apple._img_x, 8 * Apple._img_y)
    assert apple.pos == Vec2(8, 16)


def test_covers_bounding_box():
    ent = Entity(pos=Vec2(10, 10), img_x=0, img_y=0)
    assert ent.covers(Vec2(10, 10))
    assert ent.covers(Vec2(18, 18))
    assert not ent.covers(Vec2(19, 10))


def test_hit_kills_when_health_depleted():
    enemy = Enemy.at_pos(Vec2(0, 0))
    enemy.hit(1)
    assert not enemy.alive
    apple = Apple.at_pos(Vec2(0, 0))
    apple.hit(100)
    assert apple.alive  # entities are indestructible by default


def test_apple_grows_snake_and_respawns(map, snake):
    apple = Apple.at_pos(Vec2(0, 0))
    grow = snake.grow
    apple.on_intersect(snake=snake, map=map)
    assert snake.grow == grow + 5
    assert map.game.score == 1
    assert not apple.alive
    assert len(map.entities) == 1
    assert isinstance(map.entities[0], Apple)
    assert map.entities[0].pos == Vec2(40, 40)


def test_golden_apple(map, snake):
    golden = GoldenApple.at_pos(Vec2(0, 0))
    grow = snake.grow
    golden.on_intersect(snake=snake, map=map)
    assert snake.grow == grow + 20
    assert map.game.score == 5
    assert not golden.alive
    assert map.entities == []


def test_enemy_speeds_up_snake_and_costs_score(map, snake):
    enemy = Enemy.at_pos(Vec2(0, 0))
    speed = snake.speed
    enemy.on_intersect(snake=snake, map=map)
    assert snake.speed == pytest.approx(speed * 1.15)
    assert map.game.score == -10
    assert not enemy.alive


def test_entity_sprites_are_unique():
    sprites = [(cls._img_x, cls._img_y) for cls in ALL_ENTITIES]
    assert len(sprites) == len(set(sprites))
    # entity sprites must not collide with tiles that have a fixed meaning, see Map
    assert not (FLOOR_TILES | WALL_TILES | {PATH_TILE}) & set(sprites)
