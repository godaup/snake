import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.entity import Apple, Enemy, GoldenApple
from snake_quest.goals import load_goals
from snake_quest.map import DECOR_TILES, FLOOR_TILES, WALL_TILE, WALL_TILES, WALL_VARIANT_ROW, Map
from snake_quest.snake import Snake
from snake_quest.timers import Timer
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
LEVELS = CAMPAIGN.levels


@pytest.fixture
def level_map(assets, game):
    return Map(level=CAMPAIGN.level(1), game=game)


@pytest.mark.parametrize("level", LEVELS, ids=lambda lv: lv.name)
def test_level_loads(assets, game, level):
    level_map = Map(level=level, game=game)
    assert not level_map.check_on_wall(level_map.start)


@pytest.mark.parametrize("level", LEVELS, ids=lambda lv: lv.name)
def test_only_floor_and_walls_remain_after_loading(assets, game, level):
    """Entity and path tiles are lifted out of the tilemap and walls become hedge variants; anything else left over
    is a stray tile."""
    level_map = Map(level=level, game=game)
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    leftovers = {
        (tile_x, tile_y): tilemap.pget(tile_x, tile_y)
        for tile_x in range(level_map.cfg.width // 8)
        for tile_y in range(level_map.cfg.height // 8)
        if tilemap.pget(tile_x, tile_y) not in FLOOR_TILES | WALL_TILES - {WALL_TILE}
    }
    assert leftovers == {}


def maze_map(game):
    return Map(level=CAMPAIGN.level(CAMPAIGN.resolve("maze")), game=game)


def test_maze_path_is_collected_and_hidden(assets, game):
    level_map = maze_map(game)
    assert len(level_map.path) == 72
    assert not level_map.path_revealed


def breadcrumb_drawn(level_map, game) -> bool:
    """Draw the map with the first path tile at screen position (100, 100) and look for any non-floor pixel."""
    crumb = level_map.path[0]
    offset = Vec2(100 - crumb.x, 100 - crumb.y)
    pyxel.cls(0)
    level_map.draw(offset)
    return any(pyxel.pget(100 + x, 100 + y) != game.cfg.area.bg for y in range(8) for x in range(8))


def test_path_is_drawn_only_when_revealed(assets, game):
    level_map = maze_map(game)
    assert not breadcrumb_drawn(level_map, game)
    level_map.reveal_path()
    assert breadcrumb_drawn(level_map, game)


def test_maze_is_won_by_eating_all_golden_apples(assets, game):
    level_map = maze_map(game)
    snake = Snake(pos=level_map.start, orient=0, size=2)
    golden = [ent for ent in level_map.entities if isinstance(ent, GoldenApple)]
    assert golden
    for ent in golden[:-1]:
        ent.on_intersect(snake=snake, map=level_map)
    level_map.update(snake=snake)
    assert not level_map.check_win(snake=snake)
    golden[-1].on_intersect(snake=snake, map=level_map)
    level_map.update(snake=snake)
    assert level_map.check_win(snake=snake)


def reachable_tiles(level_map, game) -> set[tuple[int, int]]:
    """Floor tiles connected to the start tile (8px corridors are wide enough for the snake)."""
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    width, height = level_map.cfg.width // 8, level_map.cfg.height // 8
    start = (int(level_map.start.x) // 8, (int(level_map.start.y) - game.cfg.header.h) // 8)
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (
                0 <= nxt[0] < width
                and 0 <= nxt[1] < height
                and nxt not in seen
                and tilemap.pget(*nxt) not in WALL_TILES
            ):
                seen.add(nxt)
                todo.append(nxt)
    return seen


def test_maze_golden_apples_and_path_are_reachable(assets, game):
    level_map = maze_map(game)
    reachable = reachable_tiles(level_map, game)
    golden = [ent for ent in level_map.entities if isinstance(ent, GoldenApple)]
    for pos in [ent.pos for ent in golden] + level_map.path:
        assert (int(pos.x) // 8, (int(pos.y) - game.cfg.header.h) // 8) in reachable


def test_maze_shortest_way_follows_the_whole_path(assets, game):
    """No shortcuts: the shortest walk from the start to the golden apples passes every cell holding a path tile."""
    level_map = maze_map(game)
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    width, height = level_map.cfg.width // 8, level_map.cfg.height // 8

    def tile(pos):
        return int(pos.x) // 8, (int(pos.y) - game.cfg.header.h) // 8

    goals = {tile(ent.pos) for ent in level_map.entities if isinstance(ent, GoldenApple)}
    start = tile(level_map.start)
    previous = {start: None}
    queue = [start]
    while queue:  # breadth first, so the first golden apple reached is reached the shortest way
        here = queue.pop(0)
        if here in goals:
            break
        x, y = here
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            inside = 0 <= nxt[0] < width and 0 <= nxt[1] < height
            if inside and nxt not in previous and tilemap.pget(*nxt) not in WALL_TILES:
                previous[nxt] = here
                queue.append(nxt)
    walk = [here]
    while previous[walk[-1]] is not None:
        walk.append(previous[walk[-1]])
    cells_walked = {(x // 8, y // 8) for x, y in walk}
    path_cells = {(tx // 8, ty // 8) for tx, ty in map(tile, level_map.path)}
    assert path_cells - cells_walked == set()


def test_debug_shows_path(assets, game):
    game.cfg.debug = True
    assert breadcrumb_drawn(maze_map(game), game)


def test_new_pos_is_free(level_map, game):
    snake = Snake(pos=level_map.start, orient=0, size=2)
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    for _ in range(50):
        pos = level_map.new_pos(snake=snake)
        for corner in [pos, pos + Vec2(8, 0), pos + Vec2(0, 8), pos + Vec2(8, 8)]:
            assert tilemap.pget(corner.x // 8, (corner.y - game.cfg.header.h) // 8) in FLOOR_TILES
            assert not snake.covers(corner)
            assert not any(ent.covers(corner) for ent in level_map.entities)


def test_check_on_wall(level_map, game):
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    wall = next(
        (x, y)
        for x in range(level_map.cfg.width // 8)
        for y in range(level_map.cfg.height // 8)
        if tilemap.pget(x, y) in WALL_TILES
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
    level_map = Map(level=CAMPAIGN.level(1), game=game)
    snake = Snake(pos=level_map.start, orient=0, size=2)
    goal = level_map.cfg.goal.score
    game.score = 50 + goal - 1
    assert not level_map.check_win(snake=snake)
    game.score = 50 + goal
    assert level_map.check_win(snake=snake)


def test_check_win_length_goal(level_map):
    level_map.goals = load_goals({"length": 3}, map=level_map)
    snake = Snake(pos=level_map.start, orient=0, size=2)
    assert not level_map.check_win(snake=snake)
    snake.segs *= 3
    assert level_map.check_win(snake=snake)


def test_each_map_gets_fresh_tilemaps(assets, game):
    level = CAMPAIGN.level(1)
    tm = Map(level=level, game=game).cfg.tm
    original = pyxel.tilemaps[tm].pget(0, 0)
    pyxel.tilemaps[tm].pset(0, 0, (5, 5))  # e.g. left over from a previous run of the level
    Map(level=level, game=game)
    # look the tilemap up again: pyxel.load replaces the Tilemap objects
    assert pyxel.tilemaps[tm].pget(0, 0) == original


def test_killed_entities_count_as_defeated(level_map):
    snake = Snake(pos=level_map.start, orient=0, size=2)
    shot, eaten = Enemy.at_pos(Vec2(0, 0)), Apple.at_pos(Vec2(8, 8))
    shot.hit(1)
    eaten.alive = False
    level_map.entities += [shot, eaten]
    level_map.update(snake=snake)
    assert level_map.defeated == 1


def test_goals_are_updated_with_frame_time(level_map, game):
    level_map.goals = load_goals({"survive": 1}, map=level_map)
    snake = Snake(pos=level_map.start, orient=0, size=2)
    game.dt = datetime.timedelta(seconds=0.6)
    level_map.update(snake=snake)
    assert not level_map.check_win(snake=snake)
    level_map.update(snake=snake)
    assert level_map.check_win(snake=snake)


def variant_mask(tile):
    assert tile[1] == WALL_VARIANT_ROW
    return tile[0]


def test_walls_become_hedge_variants_matching_their_neighbours(level_map):
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    # an isolated vertical wall of three tiles in open floor
    x, y = 10, 10
    assert all(tilemap.pget(x + dx, y + dy) in FLOOR_TILES for dx in (-1, 0, 1) for dy in range(-1, 4))
    for dy in range(3):
        tilemap.pset(x, y + dy, WALL_TILE)
    level_map._autotile_walls()
    north, south = 1, 4
    assert variant_mask(tilemap.pget(x, y)) == south
    assert variant_mask(tilemap.pget(x, y + 1)) == north | south
    assert variant_mask(tilemap.pget(x, y + 2)) == north
    assert level_map.check_on_wall(Vec2(x * 8 + 4, (y + 1) * 8 + 4 + level_map.game.cfg.header.h))


def test_map_border_counts_as_wall(level_map):
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    assert variant_mask(tilemap.pget(0, 0)) == 15  # corner: outside the map is wall on two sides
    assert variant_mask(tilemap.pget(10, 0)) == 1 | 2 | 8  # top border: open only to the south


def test_decorations_are_walkable_and_free_for_spawning(level_map):
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    decor = sorted(DECOR_TILES)[0]
    for x in range(1, level_map.cfg.width // 8 - 1):
        for y in range(1, level_map.cfg.height // 8 - 1):
            if tilemap.pget(x, y) in FLOOR_TILES:
                tilemap.pset(x, y, decor)
    pos = Vec2(12 * 8 + 4, 12 * 8 + 4 + level_map.game.cfg.header.h)
    assert level_map.tile_at(pos) == decor
    assert not level_map.check_on_wall(pos)
    # with every floor tile decorated, spawning must still find a place
    level_map.new_pos()
