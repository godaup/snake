import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import Apple, GunPickup, Hunter
from snake_quest.hud import Hud
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import FLOOR_TILES
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun, Projectile

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def armed(assets, game):
    game.level_counter = CAMPAIGN.resolve("armed")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    return level_map


def snake_at(level_map, x=100, y=100, length=20) -> Snake:
    snake = Snake(pos=Vec2(x, y + level_map.header), orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(x - i * 1.3, y + level_map.header), 2, 0) for i in range(1, length)]
    return snake


def open_row(level_map, tiles=16) -> tuple[int, int]:
    """Map coordinates (x, y) of the middle of a row of `tiles` floor tiles, with floor above and below too."""
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(2, level_map.cfg.height // 8 - 2):
        for tx in range(2, level_map.cfg.width // 8 - tiles - 2):
            if all(tilemap.pget(tx + dx, ty + dy) in FLOOR_TILES for dx in range(tiles) for dy in (-1, 0, 1)):
                return (tx + tiles // 2) * 8, ty * 8 + 4
    raise AssertionError("no open row")


def fly(level_map, frames=30):
    for _ in range(frames):
        for proj in level_map.projectiles:
            if proj.alive:
                proj.update(level_map, FRAME)


def test_gun_fires_one_shot_per_cooldown_and_uses_ammo(armed, game):
    snake = snake_at(armed)
    gun = Gun(ammo=2)
    gun.update(snake, armed, fire=True, seconds=FRAME)
    gun.update(snake, armed, fire=True, seconds=FRAME)  # still cooling down
    assert len(armed.projectiles) == 1 and gun.ammo == 1
    gun.update(snake, armed, fire=True, seconds=Gun.COOLDOWN)
    gun.update(snake, armed, fire=True, seconds=Gun.COOLDOWN)
    assert len(armed.projectiles) == 2 and gun.ammo == 0  # out of ammo
    assert game.sm.effects_played == ["shoot", "shoot"]


def test_shots_never_hit_the_snake(armed):
    snake = snake_at(armed, length=40)
    snake.orient = 180  # shooting back along its own body
    armed.projectiles += Gun(ammo=1).shots(snake)
    fly(armed)
    assert len(snake) == 40


def test_a_shot_kills_a_hunter_and_counts_as_defeated(armed, game):
    snake = snake_at(armed, *open_row(armed))
    hunter = Hunter.at_pos(snake.head.pos + Vec2(40, -4))
    apple = Apple.at_pos(snake.head.pos + Vec2(20, -4))  # in the way, but shots fly through pickups
    armed.entities += [apple, hunter]
    armed.projectiles += Gun(ammo=1).shots(snake)
    fly(armed)
    assert apple.alive and not hunter.alive and hunter.killed
    assert not armed.projectiles[0].alive  # used up by the hit
    armed.update(snake)
    assert armed.defeated == 1


def test_shots_end_at_walls_and_after_their_lifetime(armed):
    snake = snake_at(armed, x=20, y=100)
    snake.orient = 180  # towards the hedge at the left border
    armed.projectiles += Gun(ammo=1).shots(snake)
    fly(armed, 10)
    assert not armed.projectiles[0].alive
    shot = Projectile(pos=Vec2(200, 150), orient=90, speed=0, size=1, col=10)
    shot.update(armed, Projectile.LIFETIME)
    assert not shot.alive


def test_dead_projectiles_are_removed(armed):
    snake = snake_at(armed)
    shot = Projectile(pos=Vec2(200, 150), orient=0, speed=1, size=1, col=10)
    shot.alive = False
    armed.projectiles.append(shot)
    armed.update(snake)
    assert armed.projectiles == []


def test_gun_pickup_gives_the_gun_then_ammo(armed, game):
    snake = snake_at(armed)
    GunPickup.at_pos(Vec2(0, 0)).on_intersect(snake, armed)
    assert isinstance(snake.weapon, Gun) and snake.weapon.ammo == GunPickup.AMMO
    GunPickup.at_pos(Vec2(0, 0)).on_intersect(snake, armed)
    assert snake.weapon.ammo == 2 * GunPickup.AMMO
    assert game.sm.effects_played == ["pickup", "pickup"]


def test_snake_fires_through_its_controller(armed):
    class Trigger(PathController):
        def steer(self, snake, map):
            return 0.0

        def fire(self, snake, map):
            return True

    snake = snake_at(armed)
    snake.controller = Trigger(lambda snake, map: None)
    snake.weapon = Gun(ammo=5)
    snake.update(dt=datetime.timedelta(seconds=FRAME), map=armed)
    assert len(armed.projectiles) == 1


def test_hud_shows_the_ammo(armed, game):
    snake = snake_at(armed)
    hud = Hud(game=game, level_map=armed, snake=snake)
    assert "GUN" not in hud.right_lines()[1]
    snake.weapon = Gun(ammo=7)
    assert hud.right_lines()[1].startswith("GUN 7")


def test_spawn_with_tunes_the_entity(armed):
    snake = snake_at(armed)
    armed.create_callback({"type": "spawn", "entity": "hunter", "with": {"SPEED": 1.1}})(armed, snake)
    assert armed.entities[-1].SPEED == 1.1
    assert Hunter.SPEED != 1.1  # only that one
    with pytest.raises(ValueError, match="no setting"):
        armed.create_callback({"type": "spawn", "entity": "hunter", "with": {"SPEEED": 1}})(armed, snake)


def test_bot_shoots_what_is_ahead_but_not_behind(armed):
    snake = snake_at(armed, *open_row(armed))
    snake.weapon = Gun(ammo=5)
    bot = PathController(lambda snake, map: None)
    armed.entities.append(Hunter.at_pos(snake.head.pos + Vec2(60, -4)))
    assert bot.fire(snake, armed)
    armed.entities[0].pos = snake.head.pos + Vec2(-60, -4)
    assert not bot.fire(snake, armed)
