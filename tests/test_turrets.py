import datetime

import pytest
import pyxel

from snake_quest import bot
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import ENTITY_NAMES, GunPickup, Hunter, Turret
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import EMPTY_TILE, FLOOR_TILES
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun, Projectile

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def turrets(assets, game):
    game.level_counter = CAMPAIGN.resolve("turrets")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    return level_map


def snake_at(pos: Vec2, length=20, orient=0) -> Snake:
    """A snake heading along `orient` with its body straight out behind it."""
    snake = Snake(pos=pos, orient=orient, size=2)
    snake.grow = 0
    back = Vec2(-pyxel.cos(orient), -pyxel.sin(orient)) * 1.3
    snake.segs += [SnakeSeg(pos + back * i, 2, 0) for i in range(1, length)]
    return snake


def open_spot(level_map, tiles=20) -> Vec2:
    """Clear a square of `tiles` x `tiles` floor tiles in the top left (every Map loads fresh tilemaps) and return the
    world position of its middle."""
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(1, tiles + 1):
        for tx in range(1, tiles + 1):
            tilemap.pset(tx, ty, EMPTY_TILE)
    return Vec2((tiles // 2 + 1) * 8, (tiles // 2 + 1) * 8 + level_map.header)


def tick(level_map, snake, seconds=FRAME):
    level_map.game.dt = datetime.timedelta(seconds=seconds)
    for ent in list(level_map.entities):
        ent.update(snake, level_map)
    for proj in level_map.projectiles:
        if proj.alive:
            proj.update(level_map, seconds, snake)


def test_turret_is_a_registered_hostile_entity():
    assert ENTITY_NAMES["turret"] is Turret and Turret.hostile


def test_the_fortress_tints_its_walls(turrets):
    assert turrets.tint == {3: 13, 11: 6}


def test_a_hit_on_the_body_cuts_the_snake_there():
    snake = snake_at(Vec2(100, 100), length=30)
    assert snake.wound(20)
    assert len(snake) == 20


def test_a_hit_never_cuts_off_more_than_half():
    snake = snake_at(Vec2(100, 100), length=30)
    assert snake.wound(3)  # right behind the head
    assert len(snake) == 15


def test_a_hit_on_the_head_costs_half_the_body():
    snake = snake_at(Vec2(100, 100), length=30)
    assert snake.wound(0)
    assert len(snake) == 15
    short = snake_at(Vec2(100, 100), length=3)
    assert not short.wound(0) and len(short) == 3


def test_segment_at_finds_the_segment_nearest_the_head():
    snake = snake_at(Vec2(100, 100), length=30)
    assert snake.segment_at(Vec2(100 - 13, 101)) in (9, 10, 11)
    assert snake.segment_at(Vec2(100, 120)) is None


def test_a_hostile_shot_cuts_the_snake_and_flies_through_entities(turrets, game):
    pos = open_spot(turrets)
    snake = snake_at(pos, length=40)
    hunter = Hunter.at_pos(pos + Vec2(-30, -20))
    turrets.entities.append(hunter)
    # straight down onto the body, 20 segments (26 px) behind the head, passing the hunter
    shot = Projectile(pos + Vec2(-26, -24), 90, 2.0, size=1, col=8, hostile=True)
    turrets.projectiles.append(shot)
    for _ in range(20):
        tick(turrets, snake)
    assert hunter.alive
    assert not shot.alive and 18 <= len(snake) <= 21
    assert "hurt" in game.sm.effects_played


def test_a_hostile_shot_kills_a_snake_too_short_to_lose_half(turrets):
    pos = open_spot(turrets)
    snake = snake_at(pos, length=2)
    turrets.projectiles.append(Projectile(pos + Vec2(0, -10), 90, 2.0, size=1, col=8, hostile=True))
    for _ in range(10):
        tick(turrets, snake)
    assert turrets.snake_killed


def test_turret_warns_then_fires_at_a_snake_in_sight(turrets, game):
    pos = open_spot(turrets)
    snake = snake_at(pos)
    turret = Turret.at_pos(pos + Vec2(-4, 40))
    turret.left = Turret.WARN
    turrets.entities.append(turret)
    tick(turrets, snake, Turret.WARN / 2)
    assert turret.sees and not turrets.projectiles  # glowing, not firing yet
    tick(turrets, snake, Turret.WARN)
    assert len(turrets.projectiles) == 1 and turrets.projectiles[0].hostile
    assert turret.left == pytest.approx(Turret.RELOAD)
    assert game.sm.effects_played == ["shoot"]


def test_turret_holds_fire_out_of_range(turrets):
    pos = open_spot(turrets)
    snake = snake_at(pos)
    turret = Turret.at_pos(pos + Vec2(0, Turret.RANGE + 10))
    turret.left = 0
    turrets.entities.append(turret)
    tick(turrets, snake, 1.0)
    assert not turret.sees and not turrets.projectiles
    assert turret.left == Turret.WARN  # whenever it sees the snake again, it warns first


def test_turret_holds_fire_behind_a_wall(turrets):
    tilemap = pyxel.tilemaps[turrets.tm]
    for ty in range(turrets.cfg.height // 8):
        for tx in range(turrets.cfg.width // 8 - 8):
            a, b = turrets.tile_center((tx, ty)), turrets.tile_center((tx + 7, ty))
            ends_free = tilemap.pget(tx, ty) in FLOOR_TILES and tilemap.pget(tx + 7, ty) in FLOOR_TILES
            if ends_free and not turrets.clear_line(a, b):
                snake, turret = snake_at(a), Turret.at_pos(b - Vec2(4, 4))
                turret.left = 0
                turrets.entities.append(turret)
                tick(turrets, snake, 1.0)
                assert not turret.sees and not turrets.projectiles
                return
    raise AssertionError("no wall between two floor tiles found")


def test_turret_leads_a_moving_snake(turrets):
    pos = open_spot(turrets)
    snake = snake_at(pos, orient=0)  # heading east
    turret = Turret.at_pos(pos + Vec2(-4, 60))  # straight south of the head
    aim = turret.intercept(snake, Turret.SHOT_SPEED)
    assert aim.x > 10  # ahead of the head, not at it


def test_shots_hit_a_turret_three_times_to_destroy_it(turrets):
    pos = open_spot(turrets)
    snake = snake_at(pos)
    turret = Turret.at_pos(pos + Vec2(30, -4))
    turret.left = 99  # not shooting back
    turrets.entities.append(turret)
    for _ in range(Turret.HEALTH):
        turrets.projectiles += Gun(ammo=1).shots(snake)
        for _ in range(10):
            tick(turrets, snake)
    assert not turret.alive and turret.killed


def test_ramming_a_turret_wrecks_it_for_half_the_snake(turrets):
    snake = snake_at(Vec2(100, 100), length=20)
    turret = Turret.at_pos(Vec2(98, 96))
    turret.on_intersect(snake, turrets)
    assert not turret.alive and turret.killed and len(snake) == 10
    turret.on_intersect(snake, turrets)  # wrecked already: nothing more
    assert len(snake) == 10 and not turrets.snake_killed
    Turret.at_pos(Vec2(98, 96)).on_intersect(snake_at(Vec2(100, 100), length=3), turrets)
    assert turrets.snake_killed  # too short to lose half


def test_bot_stocks_up_on_the_weapon_it_carries_only(turrets):
    from snake_quest.entity import SpreadPickup

    pos = open_spot(turrets)
    snake = snake_at(pos, length=10)
    snake.weapon = Gun(ammo=5)
    spread, gun = SpreadPickup.at_pos(pos + Vec2(20, -4)), GunPickup.at_pos(pos + Vec2(60, -4))
    turrets.entities += [spread, gun]
    assert bot.target(snake, turrets) == gun.pos + Vec2(4, 4)  # not the spread, which would replace the gun


def test_bot_turns_to_aim_at_turrets_only_when_close_unless_hunting(turrets):
    pos = open_spot(turrets, tiles=28)
    snake = snake_at(pos, length=10)
    snake.weapon = Gun(ammo=5)
    controller = PathController(lambda snake, map: None)
    turrets.entities.append(Turret.at_pos(pos + Vec2(PathController.DEFENCE + 20, 30)))
    assert controller._aim(snake, turrets) is not None
    assert controller._aim(snake, turrets, reach=PathController.DEFENCE) is None
    turrets.entities.append(Hunter.at_pos(pos + Vec2(PathController.DEFENCE + 20, -30)))
    assert controller._aim(snake, turrets, reach=PathController.DEFENCE) is not None  # it moves: aim at any range


def test_bot_dodges_a_shot_coming_head_on(turrets):
    pos = open_spot(turrets)
    snake = snake_at(pos, length=10)
    turrets.projectiles.append(Projectile(pos + Vec2(30, 0), 180, 2.0, size=1, col=8, hostile=True))
    controller = PathController(lambda snake, map: snake.head.pos + Vec2(100, 0))
    assert controller.steer(snake, turrets) != 0.0


def test_bot_does_not_hunt_turrets(turrets):
    pos = open_spot(turrets)
    snake = snake_at(pos, length=30)
    snake.weapon = Gun(ammo=10)
    turrets.entities.append(Turret.at_pos(pos + Vec2(40, 0)))
    assert bot.target(snake, turrets) is None  # nothing else to do: no apples here
