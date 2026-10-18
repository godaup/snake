import datetime
from types import SimpleNamespace

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.entity import ENTITY_NAMES, Firefly, GoldenApple, SpeedApple
from snake_quest.hud import Hud
from snake_quest.map import WALL_TILES, Map
from snake_quest.snake import INIT_SPEED, MAX_SPEED, Snake
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
SECOND = datetime.timedelta(seconds=1)


def fresh_snake():
    snake = Snake(pos=Vec2(100, 100), orient=0, size=2)
    snake.grow = 0
    return snake


def fake_map():
    return SimpleNamespace(game=SimpleNamespace(score=0), entities=[])


def test_speed_apple_boosts_but_does_not_grow():
    snake, level_map = fresh_snake(), fake_map()
    SpeedApple.at_pos(Vec2(0, 0)).on_intersect(snake=snake, map=level_map)
    assert snake.grow == 0
    assert level_map.game.score == 1
    assert snake.effective_speed == pytest.approx(INIT_SPEED * SpeedApple.BOOST)
    before = snake.head.pos.x
    snake.update(dt=datetime.timedelta(seconds=1 / 24), map=None)
    assert snake.head.pos.x - before == pytest.approx(INIT_SPEED * SpeedApple.BOOST)


def test_boost_runs_out():
    snake = fresh_snake()
    snake.boost(1.5, seconds=2)
    snake.update(dt=SECOND, map=None)
    assert snake.effective_speed > INIT_SPEED
    snake.update(dt=SECOND, map=None)
    assert snake.effective_speed == INIT_SPEED
    assert snake.boost_left == 0


def test_second_boost_restarts_instead_of_stacking():
    snake = fresh_snake()
    snake.boost(1.5, seconds=5)
    snake.update(dt=3 * SECOND, map=None)
    snake.boost(1.5, seconds=5)
    assert snake.boost_left == 5
    assert snake.effective_speed == pytest.approx(INIT_SPEED * 1.5)


def test_boost_respects_max_speed():
    snake = fresh_snake()
    snake.speed = MAX_SPEED
    snake.boost(2.0, seconds=5)
    assert snake.effective_speed == MAX_SPEED


def test_hud_shows_active_boost(assets, game):
    level_map = Map(level=CAMPAIGN.level(1), game=game)
    snake = Snake(pos=level_map.start, orient=0, size=2)
    hud = Hud(game=game, level_map=level_map, snake=snake)
    assert hud.right_lines()[0].startswith("BEST")
    snake.boost(1.5, seconds=4)
    assert hud.right_lines()[0] == "SPEED +50% 4.0s"


def test_new_entities_have_level_file_names():
    assert ENTITY_NAMES["speed"] is SpeedApple
    assert ENTITY_NAMES["firefly"] is Firefly


def maze(game):
    return Map(level=CAMPAIGN.level(CAMPAIGN.resolve("maze")), game=game)


def test_firefly_lights_breadcrumbs_one_by_one_nearest_first(assets, game):
    level_map = maze(game)
    (firefly,) = [ent for ent in level_map.entities if isinstance(ent, Firefly)]
    snake = Snake(pos=firefly.pos + Vec2(4, 4), orient=0, size=2)
    firefly.on_intersect(snake=snake, map=level_map)
    assert level_map.path_revealed and level_map.crumbs_shown == 0
    distances = level_map.walking_distances(snake.head.pos)
    steps = [distances[level_map._tile_xy(pos)] for pos in level_map.path]
    assert steps == sorted(steps)  # nearest crumb first
    game.dt = SECOND
    level_map.update(snake=snake)
    assert 1 <= level_map.crumbs_shown < len(level_map.path)


def test_maze_firefly_is_on_the_way(assets, game):
    """The firefly's 8x8-tile maze cell lies on the only route to the golden apples (and it flies to a passing
    snake), so every player finds it."""
    level_map = maze(game)
    (firefly,) = [ent for ent in level_map.entities if isinstance(ent, Firefly)]
    distances = level_map.walking_distances(level_map.start)
    golden_tile = min(
        (level_map._tile_xy(ent.pos) for ent in level_map.entities if isinstance(ent, GoldenApple)),
        key=lambda tile: distances[tile],
    )
    # walk back from the golden apples along decreasing distance: the cells of the shortest route
    route_cells, (x, y) = set(), golden_tile
    while distances[x, y] > 0:
        route_cells.add((x // 8, y // 8))
        x, y = next(
            n for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if distances.get(n) == distances[x, y] - 1
        )
    fx, fy = level_map._tile_xy(firefly.pos)
    assert (fx // 8, fy // 8) in route_cells


def test_firefly_flies_to_a_snake_nearby_but_ignores_one_far_away():
    firefly = Firefly.at_pos(Vec2(100, 100))
    far = Snake(pos=Vec2(300, 300), orient=0, size=2)
    firefly.update(snake=far, map=None)
    assert firefly.pos == Vec2(100, 100)
    near = Snake(pos=Vec2(134, 104), orient=0, size=2)  # 30 px to the right of its centre
    for _ in range(40):
        firefly.update(snake=near, map=None)
    assert firefly.covers(near.head.pos)


@pytest.mark.parametrize("level", CAMPAIGN.levels, ids=lambda lv: lv.name)
def test_no_closed_floor_pockets(assets, game, level):
    """Everything not a wall is reachable from the start, so spawns can't land out of reach."""
    level_map = Map(level=level, game=game)
    reachable = level_map.walking_distances(level_map.start)
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    width, height = level_map.cfg.width // 8, level_map.cfg.height // 8
    pockets = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if tilemap.pget(x, y) not in WALL_TILES and (x, y) not in reachable
    ]
    assert pockets == []


def eat_firefly(level_map):
    firefly = next(ent for ent in level_map.entities if isinstance(ent, Firefly))
    snake = Snake(pos=firefly.pos + Vec2(4, 4), orient=0, size=2)
    firefly.on_intersect(snake=snake, map=level_map)
    return snake


def test_firefly_light_fades_after_about_twenty_seconds(assets, game):
    level_map = maze(game)
    snake = eat_firefly(level_map)
    game.dt = SECOND
    for _ in range(int(Firefly.LIGHT_SECONDS)):
        level_map.update(snake=snake)
    assert level_map.path_revealed
    assert level_map.crumbs_alpha() == 1  # still fully lit after ~20 s
    level_map.update(snake=snake)
    assert 0 < level_map.crumbs_alpha() < 1  # fading
    for _ in range(3):
        level_map.update(snake=snake)
    assert not level_map.path_revealed  # gone


def test_another_firefly_relights_the_path(assets, game):
    level_map = maze(game)
    snake = eat_firefly(level_map)
    game.dt = SECOND
    for _ in range(21):
        level_map.update(snake=snake)
    assert level_map.crumbs_alpha() < 1
    Firefly.at_pos(snake.head.pos).on_intersect(snake=snake, map=level_map)
    assert level_map.crumbs_alpha() == 1
    assert level_map.crumbs_shown == 0  # lights up again from the new spot


def test_untimed_reveal_stays(assets, game):
    level_map = maze(game)
    level_map.reveal_path()
    game.dt = 100 * SECOND
    level_map.update(snake=Snake(pos=level_map.start, orient=0, size=2))
    assert level_map.path_revealed and level_map.crumbs_alpha() == 1


def test_spawn_cap(assets, game):
    level_map = maze(game)
    level_map.entities = [e for e in level_map.entities if not isinstance(e, SpeedApple)]
    spawn = level_map.create_callback({"type": "spawn", "entity": "speed", "max": 2})
    snake = Snake(pos=level_map.start, orient=0, size=2)
    for _ in range(5):
        spawn(map=level_map, snake=snake)
    assert sum(isinstance(e, SpeedApple) for e in level_map.entities) == 2


def test_maze_is_full_of_fireflies_and_speed_apples(assets, game):
    level_map = maze(game)
    # a snake off the map, so no firefly flies to it and nothing gets eaten while counting
    snake = Snake(pos=Vec2(-500, -500), orient=0, size=2)
    game.dt = datetime.timedelta(seconds=1 / 24)
    for _ in range(48):  # the start-up timers fire within the first frames
        level_map.update(snake=snake)
    fireflies = sum(isinstance(e, Firefly) for e in level_map.entities)
    speed_apples = sum(isinstance(e, SpeedApple) for e in level_map.entities)
    assert fireflies == 7  # the one after the start plus six spread out
    assert speed_apples == 15


def test_fireflies_hover_without_moving():
    firefly = Firefly.at_pos(Vec2(40, 40))
    pyxel.cls(0)
    firefly.draw(Vec2(0, 0))
    assert firefly.pos == Vec2(40, 40)  # bobbing is drawing only
