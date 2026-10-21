import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.caves import Crystal, Mushroom, Spider
from snake_quest.map import Map
from snake_quest.snake import NECK, Snake, SnakeSeg
from snake_quest.tiles import (
    EMPTY_TILE,
    FLOOR_TILES,
    TORN_WEB_TILE,
    WALL_TILE,
    WALL_TILES,
    WALL_VARIANT_ROW,
    WEB_HOLD,
    WEB_REGROW,
    WEB_SLOW,
    WEB_TILE,
    TileKind,
    tile_kind,
)
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def webs(assets, game):
    game.level_counter = CAMPAIGN.resolve("webs")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(0, 22):  # an open room, walled in, to play in
        for tx in range(0, 32):
            wall = tx in (0, 31) or ty in (0, 21)
            tilemap.pset(tx, ty, (15, WALL_VARIANT_ROW) if wall else EMPTY_TILE)
    return level_map


def snake_at(pos: Vec2, length=20, spacing=1.3) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * spacing, pos.y), 2, 0) for i in range(1, length)]
    return snake


def run(level_map, snake, frames):
    for _ in range(frames):
        snake.update(dt=level_map.game.dt, map=level_map)
        level_map.update(snake)


def test_webs_are_walkable_but_not_free_for_spawning():
    assert tile_kind(WEB_TILE) == TileKind.WEB
    assert WEB_TILE not in FLOOR_TILES and TORN_WEB_TILE not in FLOOR_TILES
    assert WEB_TILE not in WALL_TILES and TORN_WEB_TILE not in WALL_TILES


def test_a_web_holds_the_snake_and_tears(webs):
    snake = snake_at(Vec2(100, 80 + webs.header))
    tile = webs.tile_xy(Vec2(110, 80 + webs.header))
    webs.spin_web(tile)
    run(webs, snake, 12)
    assert snake.boost_left > 0 and snake.boost_factor == WEB_SLOW
    assert pyxel.tilemaps[webs.tm].pget(*tile) == TORN_WEB_TILE
    assert webs.game.sm.effects_played == ["hurt"]
    run(webs, snake, round(WEB_HOLD / FRAME) + 1)
    assert snake.effective_speed == snake.speed  # free again


def test_a_slowed_snake_does_not_bite_its_neck():
    snake = snake_at(Vec2(100, 100), length=30, spacing=1.3 * WEB_SLOW)  # bunched up behind a web
    assert not snake.self_intersect()
    assert snake.neck() * 1.3 * WEB_SLOW >= NECK


def test_a_torn_web_grows_back_once_the_snake_is_off_it(webs):
    snake = snake_at(Vec2(100, 80 + webs.header))
    tile = webs.tile_xy(Vec2(110, 80 + webs.header))
    webs.spin_web(tile)
    run(webs, snake, 12)
    assert tile in webs.torn
    snake.controller.steer = lambda snake, map: 0.0
    run(webs, snake, round(WEB_REGROW / FRAME) + 2)
    assert pyxel.tilemaps[webs.tm].pget(*tile) == WEB_TILE
    assert tile not in webs.torn


def test_webs_only_on_plain_floor(webs):
    assert not webs.spin_web((0, 0))  # rock
    assert webs.spin_web((5, 5))
    assert not webs.spin_web((5, 5))  # a web already
    webs.clear_web((5, 5))
    assert pyxel.tilemaps[webs.tm].pget(5, 5) == EMPTY_TILE


def test_spiders_crawl_along_the_walls(webs):
    spider = Spider.at_pos(Vec2(8, 8 + webs.header))  # in a corner
    webs.entities.append(spider)
    snake = snake_at(Vec2(130, 90 + webs.header))
    snake.controller.steer = lambda snake, map: 0.0
    tiles = set()
    for _ in range(24 * 10):
        spider.update(snake, webs)
        tiles.add(webs.tile_xy(spider.center))
    assert len(tiles) > 10  # it got about
    assert all(spider._ledge(webs, tile) for tile in tiles)


def test_spiders_spin_webs_and_keep_only_their_newest(webs, monkeypatch):
    spider = Spider.at_pos(Vec2(8, 8 + webs.header))
    webs.entities.append(spider)
    snake = snake_at(Vec2(130, 90 + webs.header))
    for _ in range(round(Spider.SPIN * (Spider.WEBS + 3) / FRAME)):
        spider.update(snake, webs)
    tilemap = pyxel.tilemaps[webs.tm]
    spun = [tile for tile in spider.webs if tilemap.pget(*tile) == WEB_TILE]
    assert len(spider.webs) == Spider.WEBS and len(spun) == Spider.WEBS
    assert webs.web


def test_a_spider_bites_the_body_once_then_scuttles_off(webs):
    snake = snake_at(Vec2(100, 80 + webs.header), length=20)
    spider = Spider.at_pos(Vec2(82, 76 + webs.header))  # on the body, behind the head
    spider.update(snake, webs)
    spider.update(snake, webs)
    assert len(snake) == 20 - Spider.BITE
    assert spider.state == "retreat"
    spider.on_intersect(snake, webs)  # harmless while scuttling off
    assert not webs.snake_killed


def test_running_into_a_spider_is_the_end(webs):
    snake = snake_at(Vec2(100, 80 + webs.header))
    Spider.at_pos(Vec2(98, 78 + webs.header)).on_intersect(snake, webs)
    assert webs.snake_killed


def test_crystals_glow_and_count(webs):
    snake = snake_at(Vec2(100, 80 + webs.header))
    crystal = Crystal.at_pos(Vec2(100, 80))
    assert crystal.light > 0 and Mushroom.light > 0
    crystal.on_intersect(snake, webs)
    assert not crystal.alive and snake.grow == Crystal.LENGTH and webs.game.score == Crystal.POINTS


def test_the_level_has_crystals_mushrooms_and_webs(assets, game):
    game.level_counter = CAMPAIGN.resolve("webs")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    assert sum(isinstance(ent, Crystal) for ent in level_map.entities) == 8
    assert sum(isinstance(ent, Mushroom) for ent in level_map.entities) >= 5
    assert level_map.web and level_map.darkness is not None
    tilemap = pyxel.tilemaps[level_map.tm]
    assert WALL_TILE not in {tilemap.pget(x, y) for x in range(96) for y in range(64)}  # autotiled
