import datetime

import pytest
import pyxel

from snake_quest import bot
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController, nearest
from snake_quest.entity import ENTITY_NAMES, Apple, RicochetPickup, Turret
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import EMPTY_TILE, EXIT_TILE, ICE_GRIP, ICE_TILE, TileKind, tile_kind
from snake_quest.utils import Vec2, drift
from snake_quest.weapons import Projectile, Ricochet

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def ice(assets, game):
    game.level_counter = CAMPAIGN.resolve("ice")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    return level_map


def paint(level_map, tile, x0, y0, w, h):
    """Paint a w x h block of tiles (tile coordinates) and return the world position of its centre."""
    for ty in range(y0, y0 + h):
        for tx in range(x0, x0 + w):
            pyxel.tilemaps[level_map.tm].pset(tx, ty, tile)
    return Vec2((x0 + w / 2) * 8, (y0 + h / 2) * 8 + level_map.header)


def snake_at(pos: Vec2, length=10) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def test_ice_is_walkable_terrain():
    assert tile_kind(ICE_TILE) == TileKind.ICE


def test_drift_follows_only_part_of_a_turn():
    assert drift(0, 90, 1.0) == 90
    assert drift(0, 90, 0.5) == pytest.approx(45)
    assert drift(350, 10, 0.5) == pytest.approx(0)  # the short way round


def test_the_level_knows_it_has_ice(ice):
    assert ice.ice


def test_on_ice_the_snake_slides_on_before_it_turns(ice):
    center = paint(ice, EMPTY_TILE, 1, 1, 20, 20)
    snake = snake_at(center)
    ice.update(snake)
    assert snake.grip == 1.0
    turned = snake.head.pos
    snake.orient = 90
    snake.update(datetime.timedelta(seconds=FRAME), ice)
    assert snake.heading == 90 and snake.head.pos.y > turned.y  # on floor: straight away
    paint(ice, ICE_TILE, 1, 1, 20, 20)
    snake = snake_at(center)
    ice.update(snake)
    assert snake.grip == ICE_GRIP
    snake.orient = 90
    snake.update(datetime.timedelta(seconds=FRAME), ice)
    assert snake.heading == pytest.approx(90 * ICE_GRIP)  # on ice: mostly on as before
    assert snake.head.pos.x > center.x + 1


def test_bot_arcs_slide_on_ice_too(ice):
    center = paint(ice, EMPTY_TILE, 1, 1, 20, 20)
    snake = snake_at(center)
    controller = PathController(lambda snake, map: None)
    on_floor = controller._arc(snake, ice, center, 0, 1.0, 10)
    paint(ice, ICE_TILE, 1, 1, 20, 20)
    on_ice = controller._arc(snake, ice, center, 0, 1.0, 10)
    assert on_ice[1].x > on_floor[1].x + 3  # sliding on instead of curling round
    assert on_ice[4] < on_ice[2]  # heading lags behind where it points


def test_ricochet_bounces_off_walls(ice):
    paint(ice, EMPTY_TILE, 1, 1, 20, 20)
    wall = paint(ice, (0, 3), 15, 1, 2, 20)  # a wall across the way
    shot = Projectile(Vec2(wall.x - 30, wall.y), 0, 5.0, size=1, col=12, lifetime=2.0, bounces=1)
    ice.projectiles.append(shot)
    for _ in range(12):
        shot.update(ice, FRAME)
    assert shot.alive and shot.dir.x < 0 and shot.bounces == 0  # back the way it came
    for _ in range(12):
        shot.update(ice, FRAME)
    assert shot.alive  # flying on until the next wall or its lifetime


def test_a_shot_without_bounces_stops_at_a_wall(ice):
    paint(ice, EMPTY_TILE, 1, 1, 20, 20)
    wall = paint(ice, (0, 3), 15, 1, 2, 20)
    shot = Projectile(Vec2(wall.x - 30, wall.y), 0, 5.0, size=1, col=12)
    for _ in range(12):
        shot.update(ice, FRAME)
    assert not shot.alive


def test_ricochet_pickup_gives_the_ricochet(ice):
    assert ENTITY_NAMES["ricochet"] is RicochetPickup
    snake = snake_at(Vec2(100, 100))
    RicochetPickup.at_pos(Vec2(0, 0)).on_intersect(snake, ice)
    assert type(snake.weapon) is Ricochet
    (shot,) = snake.weapon.shots(snake)
    assert shot.bounces == Ricochet.BOUNCES and shot.lifetime == Ricochet.LIFETIME


def test_bot_heads_for_the_exit_once_all_else_is_done(ice):
    snake = snake_at(Vec2(60, 80))
    ice.entities.append(Turret.at_pos(Vec2(300, 200)))
    assert bot.target(snake, ice) != ice.tile_center((96, 46))  # the turrets first (destroy_all)
    ice.entities.clear()
    assert pyxel.tilemaps[ice.tm].pget(96, 46) == EXIT_TILE
    assert bot.target(snake, ice) == ice.tile_center((96, 46))


def test_pickups_next_to_a_turret_are_left_for_last(ice):
    paint(ice, EMPTY_TILE, 1, 1, 30, 20)
    snake = snake_at(Vec2(40, 100))
    near_turret, far = Apple.at_pos(Vec2(80, 100)), Apple.at_pos(Vec2(200, 100))
    ice.entities += [near_turret, far, Turret.at_pos(Vec2(80, 115))]
    assert nearest(Apple, wary=32)(snake, ice) == far.pos + Vec2(4, 4)
    far.alive = False
    assert nearest(Apple, wary=32)(snake, ice) == near_turret.pos + Vec2(4, 4)


def test_bot_gives_up_aiming_for_a_while(ice):
    center = paint(ice, EMPTY_TILE, 1, 1, 30, 30)
    snake = snake_at(center)
    snake.weapon = Ricochet(ammo=10)
    ice.entities.append(Turret.at_pos(center + Vec2(-40, 0)))  # behind: aiming means turning round
    controller = PathController(lambda snake, map: center + Vec2(100, 0))
    modes = []
    for _ in range(3 * PathController.AIM_PATIENCE):
        controller.steer(snake, ice)
        modes.append(controller.mode)
    assert "aim" in modes[: PathController.AIM_PATIENCE]
    assert "aim" not in modes[PathController.AIM_PATIENCE : 2 * PathController.AIM_PATIENCE]


def test_spawns_keep_out_of_clear_zones(ice):
    paint(ice, EMPTY_TILE, 1, 1, 30, 20)
    for _ in range(50):
        pos = ice.new_pos(clear=[[120, 100, 2000]])  # the whole level is to be kept clear: no spot is
        assert pos is not None
    spawn = ice.create_callback({"type": "spawn", "entity": "apple", "clear": [[772, 392, 72]], "count": 20})
    spawn(ice, snake_at(Vec2(60, 80)))
    assert all((ent.pos - Vec2(768, 388)).length() >= 72 for ent in ice.entities)
