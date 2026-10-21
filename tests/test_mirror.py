import datetime
from collections import deque

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController, ScriptedController
from snake_quest.hud import Hud
from snake_quest.map import Map
from snake_quest.snake import Snake
from snake_quest.tiles import EMPTY_TILE, EXIT_TILE, MIRROR_TILE, WALL_TILES, TileKind, tile_kind
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def mirror(assets, game):
    game.level_counter = CAMPAIGN.resolve("mirror")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    return level_map


def paint(level_map, tile, x0, y0, w, h):
    for ty in range(y0, y0 + h):
        for tx in range(x0, x0 + w):
            pyxel.tilemaps[level_map.tm].pset(tx, ty, tile)
    return Vec2((x0 + w / 2) * 8, (y0 + h / 2) * 8 + level_map.header)


def test_mirrored_floor_is_walkable_terrain():
    assert tile_kind(MIRROR_TILE) == TileKind.MIRROR
    assert MIRROR_TILE not in WALL_TILES


def test_the_level_knows_it_has_mirrors(mirror):
    assert mirror.mirror


@pytest.mark.parametrize(("tile", "turned"), [(EMPTY_TILE, 1), (MIRROR_TILE, -1)])
def test_on_a_mirror_left_is_right(mirror, tile, turned):
    center = paint(mirror, tile, 2, 2, 12, 12)
    snake = Snake(pos=center, orient=0, size=2, controller=ScriptedController([1.0] * 4))
    for _ in range(4):
        mirror.update(snake)  # the map tells the snake what it is on
        snake.update(dt=mirror.game.dt, map=mirror)
    assert snake.mirrored == (tile == MIRROR_TILE)
    assert (snake.orient + 180) % 360 - 180 == turned * 4 * snake.turn_speed


def test_the_bot_steers_the_other_way_on_a_mirror(mirror):
    center = paint(mirror, MIRROR_TILE, 2, 2, 12, 12)
    bot = PathController(lambda snake, map: center + Vec2(0, 40))  # straight below: turn right
    snake = Snake(pos=center, orient=0, size=2, controller=bot)
    plain = bot._steer(snake, mirror)
    snake.mirrored = True
    assert plain > 0 and bot.steer(snake, mirror) == -plain


def test_the_hud_says_when_the_controls_are_mirrored(mirror, game):
    snake = Snake(pos=mirror.start, orient=0, size=2)
    hud = Hud(game=game, level_map=mirror, snake=snake)
    snake.mirrored = True
    assert hud.right_lines()[0] == "MIRRORED!"


def test_every_way_to_the_exit_crosses_a_mirror(mirror):
    """The mirrored bands run across the whole level: around them there is no way out."""
    tilemap = pyxel.tilemaps[mirror.tm]
    width, height = mirror.cfg.width // 8, mirror.cfg.height // 8
    start = mirror.tile_xy(mirror.start)
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nxt[0] < width and 0 <= nxt[1] < height) or nxt in seen:
                continue
            tile = tilemap.pget(*nxt)
            if tile in WALL_TILES or tile == MIRROR_TILE:
                continue
            seen.add(nxt)
            queue.append(nxt)
    assert not any(tilemap.pget(*tile) == EXIT_TILE for tile in seen)
