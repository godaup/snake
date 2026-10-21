import datetime

import pytest
import pyxel

from snake_quest import bot
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import GunPickup, Hunter, Knight, LaserPickup, Mine
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import EMPTY_TILE
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun, Laser, Projectile

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def armored(assets, game):
    game.level_counter = CAMPAIGN.resolve("armored")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    for ty in range(1, 21):  # an open square to play in
        for tx in range(1, 31):
            pyxel.tilemaps[level_map.tm].pset(tx, ty, EMPTY_TILE)
    return level_map


def snake_at(level_map, x=40, y=80, length=20) -> Snake:
    snake = Snake(pos=Vec2(x, y + level_map.header), orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(x - i * 1.3, y + level_map.header), 2, 0) for i in range(1, length)]
    return snake


def put(level_map, cls, x, y=80):
    ent = cls.at_pos(Vec2(x - 4, y - 4 + level_map.header))
    level_map.entities.append(ent)
    return ent


def fly(level_map, frames=30):
    for _ in range(frames):
        for proj in level_map.projectiles:
            if proj.alive:
                proj.update(level_map, FRAME)


def shoot(level_map, weapon, snake):
    level_map.projectiles.extend(weapon.shots(snake))
    fly(level_map)


def test_shots_glance_off_armour(armored):
    knight = put(armored, Knight, 80)
    shoot(armored, Gun(ammo=1), snake_at(armored))
    assert knight.alive and knight.health == Knight.HEALTH
    assert knight.glint > 0
    assert not any(proj.alive for proj in armored.projectiles)


def test_the_laser_pierces_armour_and_what_stands_behind(armored):
    first, second = put(armored, Knight, 70), put(armored, Hunter, 100)
    snake = snake_at(armored)
    shoot(armored, Laser(ammo=1), snake)
    assert first.health == Knight.HEALTH - 1  # hit once, though the beam passed through it for several frames
    assert not second.alive and second.killed
    shoot(armored, Laser(ammo=1), snake)
    assert not first.alive and first.killed


def test_the_laser_beam_has_a_short_range():
    assert Laser(ammo=1).range < Gun(ammo=1).range


def test_a_mine_blast_hurts_armour_too(armored):
    knight = put(armored, Knight, 80)
    mine = put(armored, Mine, 80)
    mine.age = Mine.ARM  # armed
    knight.health = 1
    snake = snake_at(armored, x=200)
    for _ in range(30):
        mine.update(snake, armored)
    assert not knight.alive


def test_a_laser_pickup_replaces_the_gun(armored):
    snake = snake_at(armored)
    snake.weapon = Gun(ammo=5)
    LaserPickup.at_pos(Vec2(0, 0)).on_intersect(snake, armored)
    assert isinstance(snake.weapon, Laser) and snake.weapon.ammo == LaserPickup.AMMO


def test_the_bot_aims_only_what_its_weapon_can_hurt(armored):
    put(armored, Knight, 80)
    controller = PathController(lambda snake, map: None)
    snake = snake_at(armored)
    snake.weapon = Gun(ammo=5)
    assert controller._aim(snake, armored) is None
    snake.weapon = Laser(ammo=5)
    assert controller._aim(snake, armored) is not None


def test_the_bot_hunts_armour_only_with_a_laser(armored):
    knight = put(armored, Knight, 200)
    snake = snake_at(armored, length=30)
    snake.weapon = Gun(ammo=30)
    armored.entities.append(GunPickup.at_pos(Vec2(300, 200)))
    assert bot.target(snake, armored) != knight.pos + Vec2(4, 4)
    snake.weapon = Laser(ammo=30)
    assert bot.target(snake, armored) == knight.pos + Vec2(4, 4)


def test_a_beam_draws_as_a_streak(armored):
    beam = Projectile(Vec2(100, 100), 0, 8, 1, 8, pierce=True)
    beam.draw(Vec2(0, 0))
