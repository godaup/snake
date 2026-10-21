import datetime

import pytest

from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import ENTITY_NAMES, Drone, GunPickup, SpreadPickup
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun, Spread

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def swarm(assets, game):
    game.level_counter = CAMPAIGN.resolve("swarm")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    return level_map


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def test_drone_is_a_registered_hostile_entity_bots_do_not_swerve_around():
    assert ENTITY_NAMES["drone"] is Drone and Drone.hostile and not Drone.avoid


def test_drone_flies_straight_for_the_head_walls_or_not(swarm):
    snake = snake_at(Vec2(240, 200))
    drone = Drone.at_pos(Vec2(236, 100))
    drone.heading = 90  # already facing it
    for _ in range(30):
        drone.update(snake, swarm)
    assert drone.pos.y == pytest.approx(100 + 30 * Drone.SPEED)
    assert drone.pos.x == pytest.approx(236)


def test_drone_overshoots_and_loops_back(swarm):
    snake = snake_at(Vec2(240, 200))
    drone = Drone.at_pos(Vec2(100, 196))
    drone.heading = 90  # flying across, too fast to turn on the spot
    for _ in range(10):
        drone.update(snake, swarm)
    assert drone.heading == pytest.approx(90 - 10 * Drone.TURN)


def test_drone_never_leaves_the_level(swarm):
    snake = snake_at(Vec2(10, swarm.header + 10))
    drone = Drone.at_pos(Vec2(4, swarm.header + 4))
    drone.heading = 225  # up and left, out of the level
    for _ in range(20):
        drone.update(snake, swarm)
        assert drone.pos.x >= 0 and swarm.header <= drone.pos.y


def test_a_sting_costs_segments_and_the_drone(swarm, game):
    snake = snake_at(Vec2(240, 200), length=20)
    drone = Drone.at_pos(Vec2(240 - 20 - 4, 200 - 4))  # on the body
    swarm.entities.append(drone)
    drone.update(snake, swarm)
    assert not drone.alive and not drone.killed  # gone, but not defeated
    assert len(snake) == 20 - Drone.STING
    assert game.sm.effects_played == ["hurt"]


def test_a_sting_the_snake_is_too_short_for_is_the_end(swarm):
    snake = snake_at(Vec2(240, 200), length=Drone.STING)
    Drone.at_pos(Vec2(236, 196)).on_intersect(snake, swarm)
    assert swarm.snake_killed


def test_spread_fires_a_fan_of_three_for_one_ammo(swarm):
    snake = snake_at(Vec2(240, 200))
    spread = Spread(ammo=2)
    spread.update(snake, swarm, fire=True, seconds=FRAME)
    assert spread.ammo == 1 and len(swarm.projectiles) == 3
    directions = sorted(round(proj.dir.y, 2) for proj in swarm.projectiles)
    assert directions[0] < 0 == directions[1] < directions[2]


def test_a_pickup_of_another_kind_replaces_the_weapon(swarm):
    snake = snake_at(Vec2(240, 200))
    GunPickup.at_pos(Vec2(0, 0)).on_intersect(snake, swarm)
    SpreadPickup.at_pos(Vec2(0, 0)).on_intersect(snake, swarm)
    assert type(snake.weapon) is Spread and snake.weapon.ammo == SpreadPickup.AMMO
    SpreadPickup.at_pos(Vec2(0, 0)).on_intersect(snake, swarm)
    assert snake.weapon.ammo == 2 * SpreadPickup.AMMO
    GunPickup.at_pos(Vec2(0, 0)).on_intersect(snake, swarm)
    assert type(snake.weapon) is Gun


def test_a_spawn_timer_can_send_a_wave(swarm):
    snake = snake_at(Vec2(60, 80))
    spawn = swarm.create_callback({"type": "spawn", "entity": "drone", "count": 4, "max": 6})
    spawn(swarm, snake)
    spawn(swarm, snake)
    drones = [ent for ent in swarm.entities if isinstance(ent, Drone)]
    assert len(drones) == 6  # a second wave of 4 is cut short by `max`
    assert len({(drone.pos.x, drone.pos.y) for drone in drones}) == 6


def test_bot_never_searches_outside_the_level(swarm):
    snake = snake_at(Vec2(240, 200))
    controller = PathController(lambda snake, map: Vec2(-50, -50))  # a target off the map
    controller.steer(snake, swarm)
    assert len(controller._distance) <= 1
