import datetime

import pytest
import pyxel

from snake_quest.bosses import OuroborosBoss
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import Apple, GunPickup, Rival
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import FLOOR_TILES
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun, Projectile

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def arena(assets, game):
    game.level_counter = CAMPAIGN.resolve("ouroboros")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.timers.clear()
    level_map.entities = [level_map.boss.rival]
    game.dt = datetime.timedelta(seconds=FRAME)
    return level_map


def grown(rival: Rival, length=16) -> Snake:
    """The rival's body, laid out straight to the left of its lair, `length` long."""
    body = rival.body
    body.grow = 0
    body.orient = body.heading = 0
    body.segs = body.segs[:1] + [
        SnakeSeg(Vec2(body.head.pos.x - i * 1.2, body.head.pos.y), 2, 8) for i in range(1, length)
    ]
    return body


def player_at(pos: Vec2, length=10) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def test_the_boss_puts_its_rival_at_the_lair(arena):
    boss = arena.boss
    assert isinstance(boss, OuroborosBoss)
    rival = boss.rival
    assert rival.lives == 3 and rival.body is not None
    assert (rival.body.head.pos - Vec2(240, 196)).length() < 1
    assert boss.bar(arena, None) == pytest.approx(2 / 3 + 1 / 3 * len(rival.body) / rival.START)


def test_shot_short_it_loses_a_life_and_comes_back(arena):
    rival = arena.boss.rival
    body = grown(rival, 8)
    snake = player_at(Vec2(60, 60 + arena.header))
    assert rival.covers(body.segs[3].pos)
    rival.hit(1)  # cut to 4: too short
    rival.update(snake, arena)
    assert rival.lives == 2 and rival.body is None and rival.alive
    for _ in range(round(rival.RESPAWN / FRAME) + 2):
        rival.update(snake, arena)
    assert rival.body is not None and (rival.body.head.pos - rival.lair).length() < 3


def test_a_shot_cuts_the_rival_where_it_strikes(arena):
    rival = arena.boss.rival
    body = grown(rival, 30)
    shot = Projectile(body.segs[20].pos - Vec2(0, 6), 90, 5, 1, 10)
    arena.projectiles.append(shot)
    for _ in range(3):
        shot.update(arena, FRAME)
    assert 17 <= len(body) <= 21 and rival.lives == 3  # the first segment it touches, close to the 20th


def test_its_head_in_the_snakes_body_costs_it_a_life(arena):
    rival = arena.boss.rival
    body = grown(rival)
    snake = player_at(body.head.pos + Vec2(30, 0))
    snake.segs.append(SnakeSeg(body.head.pos + Vec2(1, 0), 2, 0))  # right in its way
    rival.update(snake, arena)
    assert rival.lives == 2


def test_the_snakes_head_on_the_rival_is_the_end(arena):
    rival = arena.boss.rival
    body = grown(rival)
    snake = player_at(body.segs[8].pos)
    arena.update(snake)
    assert arena.snake_killed


def test_it_eats_apples_for_itself(arena):
    rival = arena.boss.rival
    body = grown(rival)
    apple = Apple.at_pos(body.head.pos + Vec2(2, -4))
    arena.entities.append(apple)
    score = arena.game.score
    rival.update(player_at(Vec2(60, 60 + arena.header)), arena)
    assert not apple.alive and body.grow == 5 and arena.game.score == score
    assert any(isinstance(ent, Apple) and ent.alive for ent in arena.entities)  # a new one


def test_its_guns_shoot_at_the_snake(arena):
    rival = arena.boss.rival
    body = grown(rival)
    arena.entities.append(GunPickup.at_pos(body.head.pos + Vec2(2, -4)))
    rival.update(player_at(Vec2(60, 60 + arena.header)), arena)
    assert isinstance(body.weapon, Gun) and body.weapon.hostile
    body.weapon.release(body, arena)
    assert arena.projectiles and all(proj.hostile for proj in arena.projectiles)


def test_its_bot_aims_at_the_snakes_head(arena):
    rival = arena.boss.rival
    body = grown(rival)
    body.weapon = Gun(ammo=5, hostile=True)
    controller = body.controller
    controller.prey = player_at(body.head.pos + Vec2(60, 0))
    turn, _ = controller._aim(body, arena)
    assert abs(turn) < 1 and controller.fire(body, arena)


def test_bots_keep_away_from_the_other_snakes_body(arena):
    rival = arena.boss.rival
    body = grown(rival)
    snake = player_at(Vec2(60, 60 + arena.header))
    player_bot = PathController(lambda snake, map: None)
    near_rival = player_bot.threats(snake, arena)
    assert len(near_rival) >= len(body) // 2 and all(radius == player_bot.BODY for _, radius in near_rival)
    body.controller.prey = snake
    assert len(body.controller.threats(body, arena)) == (len(snake) + 1) // 2  # the snake's body, not its own


def test_beaten_when_its_lives_are_gone(arena):
    boss = arena.boss
    rival = boss.rival
    snake = player_at(Vec2(60, 60 + arena.header))
    assert boss.target() == rival.body.segs[-1].pos
    for _ in range(3):
        rival.crash(arena)
    assert boss.defeated(arena) and not rival.alive and boss.target() is None
    rival.update(snake, arena)
    assert rival.body is None  # no comeback


def test_phases_make_it_faster(arena):
    boss = arena.boss
    rival = boss.rival
    snake = player_at(Vec2(60, 60 + arena.header))
    speed = rival.SPEED
    rival.crash(arena)
    boss.update(arena, snake, datetime.timedelta(seconds=FRAME))
    assert boss.phase == 1 and speed < rival.SPEED and boss.phase_message()


def test_the_arena_is_open_around_the_lair(arena):
    tilemap = pyxel.tilemaps[arena.tm]
    lair = arena.tile_xy(Vec2(240, 196))
    assert all(tilemap.pget(lair[0] + dx, lair[1] + dy) in FLOOR_TILES for dx in range(-6, 7) for dy in range(-6, 7))
