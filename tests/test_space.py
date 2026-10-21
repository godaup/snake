"""Arc 6, Space: airlock doors and oxygen (Airlock), grip and the Tractor (Zero-G), planets (Gravity Wells) and
asteroids (Asteroids). The Mothership has its own file."""

import datetime

import omegaconf
import pytest
import pyxel

from snake_quest import bot, difficulty
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import Apple, Drone
from snake_quest.goals import CollectAllGoal, OxygenGoal
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.space import AirTank, Asteroid, Planet, Star
from snake_quest.tiles import DOOR_OPEN_TILE, DOOR_TILE, EMPTY_TILE, WALL_TILES, WALL_VARIANT_ROW
from snake_quest.utils import Vec2
from snake_quest.weapons import Projectile, Tractor, TractorBeam

CAMPAIGN = load_campaign()
FRAME = 1 / 24
DT = datetime.timedelta(seconds=FRAME)


def level(game, name) -> Map:
    game.level_counter = CAMPAIGN.resolve(name)
    game.dt = DT
    return Map(level=CAMPAIGN.level(game.level_counter), game=game)


def room(level_map, w=40, h=30):
    """An open room, walled in, at the level's top left; no entities or timers."""
    level_map.entities.clear()
    level_map.timers.clear()
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(h):
        for tx in range(w):
            wall = tx in (0, w - 1) or ty in (0, h - 1)
            tilemap.pset(tx, ty, (15, WALL_VARIANT_ROW) if wall else EMPTY_TILE)
    return level_map


def snake_at(pos: Vec2, length=20, orient=0) -> Snake:
    snake = Snake(pos=pos, orient=orient, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


# ---- Airlock --------------------------------------------------------------------------------------------------------


@pytest.fixture
def airlock(assets, game):
    return level(game, "airlock")


def oxygen(level_map) -> OxygenGoal:
    return next(goal for goal in level_map.goals if isinstance(goal, OxygenGoal))


def test_doors_survive_loading_and_shut_ones_are_walls(airlock):
    tilemap = pyxel.tilemaps[airlock.tm]
    kinds = {tilemap.pget(*tile) for tile in airlock.doors}
    assert airlock.doors and kinds == {DOOR_TILE, DOOR_OPEN_TILE}  # not autotiled into hull
    assert DOOR_TILE in WALL_TILES and DOOR_OPEN_TILE not in WALL_TILES


def test_doors_take_turns_and_blink_before_shutting(airlock):
    tilemap = pyxel.tilemaps[airlock.tm]
    snake = snake_at(Vec2(60, 60))
    opened = {tile for tile in airlock.doors if tilemap.pget(*tile) == DOOR_OPEN_TILE}
    version = airlock.walls_version
    airlock._cycle_doors(snake, airlock.door_cycle - airlock.door_warn + 0.01)
    assert airlock.closing == opened
    airlock._cycle_doors(snake, airlock.door_warn)
    assert all(tilemap.pget(*tile) == DOOR_TILE for tile in opened)
    assert all(tilemap.pget(*tile) == DOOR_OPEN_TILE for tile in set(airlock.doors) - opened)
    assert not airlock.closing and airlock.walls_version > version


def test_a_shutting_door_cuts_the_body_and_ends_a_head(airlock):
    tilemap = pyxel.tilemaps[airlock.tm]
    door = next(tile for tile in airlock.doors if tilemap.pget(*tile) == DOOR_OPEN_TILE)
    snake = snake_at(airlock.tile_center(door) + Vec2(13, 0), length=30)  # the 10th segment lies in the door
    airlock.door_left = 0
    airlock._cycle_doors(snake, 0.01)
    assert 0 < len(snake) < 30 and not airlock.snake_killed
    door = next(tile for tile in airlock.doors if tilemap.pget(*tile) == DOOR_OPEN_TILE)
    head = snake_at(airlock.tile_center(door), length=5)
    airlock.door_left = 0
    airlock._cycle_doors(head, 0.01)
    assert airlock.snake_killed


def test_oxygen_drains_tanks_refill_and_empty_is_the_end(airlock):
    goal, snake = oxygen(airlock), snake_at(Vec2(60, 60))
    goal.update(airlock, snake, datetime.timedelta(seconds=goal.drain / 2))
    assert goal.left == pytest.approx(0.5) and goal.done(airlock, snake)
    assert goal.status(airlock, snake) == "O2 50%"
    AirTank.at_pos(Vec2(0, 0)).on_intersect(snake, airlock)
    assert goal.left == pytest.approx(min(1.0, 0.5 + goal.tank))
    goal.update(airlock, snake, datetime.timedelta(seconds=goal.drain))
    assert airlock.snake_killed and not goal.done(airlock, snake)


def test_the_lamp_dims_as_the_air_runs_low(airlock):
    goal, snake = oxygen(airlock), snake_at(Vec2(60, 60))
    goal.update(airlock, snake, DT)
    full = airlock.darkness.light
    goal.update(airlock, snake, datetime.timedelta(seconds=goal.drain * 0.75))
    assert airlock.darkness.light < full
    assert airlock.darkness.light == pytest.approx(goal.light[1] + (goal.light[0] - goal.light[1]) * goal.left)


def test_harder_difficulties_drain_the_air_faster(game):
    cfg = omegaconf.OmegaConf.create({"goal": {"oxygen": {"drain": 90, "tank": 0.5}}})
    easy = difficulty.apply(cfg, difficulty.load(game.cfg, "easy")).goal.oxygen.drain
    hard = difficulty.apply(cfg, difficulty.load(game.cfg, "hard")).goal.oxygen.drain
    assert easy > 90 > hard


def test_bots_short_of_air_fetch_a_tank(airlock):
    room(airlock)
    snake = snake_at(Vec2(100, 100))
    tank = AirTank.at_pos(Vec2(200, 150))
    airlock.entities += [tank, Apple.at_pos(Vec2(120, 104))]
    oxygen(airlock).left = 0.2
    assert bot.target(snake, airlock) == tank.pos + Vec2(4, 4)


# ---- Zero-G ---------------------------------------------------------------------------------------------------------


@pytest.fixture
def zerog(assets, game):
    return room(level(game, "zerog"))


def test_low_grip_everywhere(zerog):
    assert zerog.grip_at(Vec2(100, 100)) == zerog.grip < 1
    snake = snake_at(Vec2(100, 100))
    zerog._step_on_tiles(snake)
    assert snake.grip == zerog.grip


def test_the_tractor_pulls_pickups_ahead_only(zerog):
    snake = snake_at(Vec2(100, 100))
    snake.weapon = Tractor(ammo=3)
    apple, drone = Apple.at_pos(Vec2(150, 96)), Drone.at_pos(Vec2(150, 106))
    behind = Apple.at_pos(Vec2(40, 96))
    zerog.entities += [apple, drone, behind]
    snake.weapon.update(snake, zerog, fire=True, seconds=FRAME)
    (beam,) = zerog.projectiles
    assert isinstance(beam, TractorBeam) and snake.weapon.ammo == 2
    start, drone_at, behind_at = apple.pos, drone.pos, behind.pos
    for _ in range(6):
        beam.update(zerog, FRAME, snake)
    assert apple.pos.x < start.x and drone.pos == drone_at and behind.pos == behind_at
    for _ in range(round(TractorBeam.PULSE / FRAME)):
        beam.update(zerog, FRAME, snake)
    assert not beam.alive


def test_bots_fire_the_tractor_at_pickups_in_its_cone(zerog):
    snake = snake_at(Vec2(100, 100))
    snake.weapon = Tractor(ammo=3)
    controller = PathController(lambda snake, map: None)
    assert not controller.fire(snake, zerog)
    zerog.entities.append(Star.at_pos(Vec2(150, 96)))
    assert controller.fire(snake, zerog)
    apple = Apple.at_pos(Vec2(200, 200))
    zerog.entities += [apple, Drone.at_pos(Vec2(120, 120))]
    assert bot.target(snake, zerog) == apple.pos + Vec2(4, 4)  # with a tractor it eats, it doesn't hunt


# ---- Gravity Wells ---------------------------------------------------------------------------------------------------


@pytest.fixture
def gravity(assets, game):
    return room(level(game, "gravity"))


def planet_at(level_map, centre: Vec2, mass=1600.0) -> Planet:
    planet = Planet.at_pos(centre - Vec2(8, 8))
    planet.mass = mass
    level_map.entities.append(planet)
    return planet


def test_a_planet_pulls_the_heading_towards_it_harder_when_close(gravity):
    planet = planet_at(gravity, Vec2(160, 140))
    above = Vec2(100, 100)  # going right, the planet below on the right: turn right (positive)
    near, far = planet.pull(above, 0, 1.0), planet.pull(Vec2(70, 80), 0, 1.0)
    assert near > far > 0
    # capped; going down, a planet to the west lies on the right of the way
    assert planet.pull(planet.center + Vec2(10, 0), 90, 1.0) == Planet.MAX_PULL
    assert planet.pull(planet.center + Vec2(Planet.REACH + 1, 0), 90, 1.0) == 0


def test_the_snake_is_pulled_and_its_arcs_agree(gravity):
    planet_at(gravity, Vec2(160, 160))
    gravity.update(snake_at(Vec2(20, 20)))  # refreshes the wells
    snake = snake_at(Vec2(100, 120))
    controller = PathController(lambda snake, map: None)
    controller._threats, controller._solids, controller._shots = [], [], []
    _, pos, orient, _, heading = controller._arc(snake, gravity, snake.head.pos, snake.orient, 0.0, 10)
    for _ in range(10):
        snake.update(DT, gravity)
    assert snake.orient > 0  # pulled off its straight line
    assert (snake.head.pos - pos).length() < 0.5 and orient == pytest.approx(snake.orient)


def test_flying_into_a_planet_burns_and_bots_keep_clear(gravity):
    planet = planet_at(gravity, Vec2(160, 160))
    snake = snake_at(Vec2(100, 100))
    assert planet.covers(planet.center) and not planet.covers(planet.center + Vec2(9, 0))
    planet.on_intersect(snake, gravity)
    assert gravity.snake_killed
    controller = PathController(lambda snake, map: None)
    controller._steer(snake, gravity)
    assert controller._solids == [(planet.center, Planet.RADIUS + controller.SOLID)]
    assert not planet.avoid and not planet.exposed


def test_harder_difficulties_bring_heavier_planets(assets, game):
    game.profile.difficulty = "nightmare"
    assert level(game, "gravity").gravity > 1
    game.profile.difficulty = "easy"
    assert level(game, "gravity").gravity < 1


# ---- Asteroids -------------------------------------------------------------------------------------------------------


@pytest.fixture
def asteroids(assets, game):
    return room(level(game, "asteroids"), w=60, h=40)


def test_asteroids_split_into_smaller_pieces(asteroids):
    rock = Asteroid.at_pos(Vec2(200, 150))
    assert rock.size == 3 and rock.w == 32
    rock.hit(rock.health)
    assert not rock.alive and [piece.size for piece in rock.pieces] == [2, 2]
    asteroids.entities.append(rock)
    asteroids.update(snake_at(Vec2(40, 40)))
    assert sum(isinstance(ent, Asteroid) for ent in asteroids.entities) == 2  # the map adds the pieces
    small = Asteroid.at_pos(Vec2(0, 0))
    small.resize(1)
    small.hit(1)
    assert not small.pieces


def test_every_piece_counts_for_destroy_all(asteroids):
    goal = CollectAllGoal("asteroid", asteroids)
    rock = Asteroid.at_pos(Vec2(200, 150))
    asteroids.entities.append(rock)
    assert goal.counts(asteroids) == (0, 1)
    rock.hit(rock.health)
    asteroids.update(snake_at(Vec2(40, 40)))
    assert goal.counts(asteroids) == (1, 3)


def test_asteroids_bounce_off_walls(asteroids):
    rock = Asteroid.at_pos(Vec2(10, 100))
    rock.resize(2)
    rock.heading = 180  # into the left wall
    snake = snake_at(Vec2(300, 200))
    for _ in range(40):
        rock.update(snake, asteroids)
    assert not asteroids.check_on_wall(rock.center)
    assert pyxel.cos(rock.heading) > 0  # going right now


def test_a_rock_on_the_head_is_the_end_a_pebble_only_stings(asteroids):
    snake = snake_at(Vec2(100, 100), length=20)
    pebble = Asteroid.at_pos(Vec2(96, 96))
    pebble.resize(1)
    pebble.strike(snake, asteroids, 0)
    assert len(snake) == 20 - Asteroid.STING and not asteroids.snake_killed
    rock = Asteroid.at_pos(Vec2(80, 80))
    rock.strike(snake, asteroids, 10)
    assert len(snake) < 18 and not asteroids.snake_killed
    rock.cool = 0
    rock.strike(snake, asteroids, 0)
    assert asteroids.snake_killed


def test_shots_break_rocks(asteroids):
    rock = Asteroid.at_pos(Vec2(200, 150))
    asteroids.entities.append(rock)
    for _ in range(rock.HEALTH[3]):
        shot = Projectile(rock.center - Vec2(10, 0), 0, 3, 1, 10)
        for _ in range(5):
            shot.update(asteroids, FRAME)
    assert not rock.alive and rock.killed
