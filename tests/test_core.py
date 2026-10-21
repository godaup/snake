import datetime

import omegaconf
import pytest

from snake_quest import bot
from snake_quest.bosses import CoreBoss
from snake_quest.campaign import load_campaign
from snake_quest.entity import ENTITY_NAMES, Core, Drone, Turret
from snake_quest.goals import load_goals
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun

CAMPAIGN = load_campaign()
SECOND = datetime.timedelta(seconds=1)


@pytest.fixture
def arena(assets, game):
    game.level_counter = CAMPAIGN.resolve("core")
    return Map(level=CAMPAIGN.level(game.level_counter), game=game)


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def boss_cfg(**values):
    base = {"type": "core", "pos": [240, 196], "health": 6, "turrets": 3, "ring": 64, "reload": 5.0, "armor": 1}
    base.update({"call": 10, "swarm": 1, **values})
    base.setdefault("phases", [{"below": 1.0}, {"below": 0.5, "turrets": 4, "reload": 4.0}])
    return omegaconf.OmegaConf.create(base)


def fresh_boss(arena, **values) -> CoreBoss:
    arena.entities.clear()
    arena.boss = CoreBoss(boss_cfg(**values), arena)
    return arena.boss


def ring(boss):
    return [turret for turret in boss.ring if turret.alive]


def test_core_is_registered():
    assert ENTITY_NAMES["core"] is Core and Core.hostile


def test_level_puts_the_core_in_its_arena_behind_a_ring_of_turrets(arena):
    boss = arena.boss
    assert isinstance(boss, CoreBoss) and boss.core in arena.entities
    assert boss.core.w == 16 and boss.core.shielded
    assert len(boss.ring) == 3 and all(turret in arena.entities for turret in boss.ring)
    for turret in boss.ring:
        assert (turret.center - boss.core.center).length() == pytest.approx(64, abs=1)
        assert not arena.check_on_wall(turret.center)  # the arena is open
        assert turret.health == 1 and turret.RELOAD == 5.0
    assert boss.label() == "THE CORE I"


def test_the_shield_holds_until_the_ring_falls(arena):
    boss = fresh_boss(arena)
    snake = snake_at(Vec2(60, 60))
    boss.core.hit(1)
    assert boss.core.health == 6  # the shield takes it
    for turret in boss.ring[:-1]:
        turret.hit(1)
    boss.update(arena, snake, SECOND)
    assert boss.core.shielded
    boss.ring[-1].hit(1)
    boss.update(arena, snake, SECOND)
    assert not boss.core.shielded
    boss.core.hit(1)
    assert boss.core.health == 5 and boss.bar(arena, snake) == pytest.approx(5 / 6)


def test_a_new_phase_builds_a_new_ring(arena):
    boss = fresh_boss(arena)
    snake = snake_at(Vec2(60, 60))
    for turret in boss.ring:
        turret.hit(1)
    boss.update(arena, snake, SECOND)
    for _ in range(3):
        boss.core.hit(1)
    boss.update(arena, snake, SECOND)
    assert boss.phase == 1 and boss.core.shielded
    assert len(ring(boss)) == 4 and all(turret.RELOAD == 4.0 for turret in boss.ring)
    assert boss.phase_message() == "THE CORE REBUILDS ITS DEFENCES"


def test_it_launches_drones_up_to_its_swarm(arena):
    boss = fresh_boss(arena, call=1, swarm=2)
    snake = snake_at(Vec2(60, 60))
    for _ in range(5):
        boss.update(arena, snake, SECOND)
    assert sum(isinstance(ent, Drone) for ent in arena.entities) == 2


def test_bots_shoot_the_ring_first_then_the_core(arena):
    boss = fresh_boss(arena)
    assert boss.target() == boss.ring[0].center
    for turret in boss.ring:
        turret.hit(1)
    boss.update(arena, snake_at(Vec2(60, 60)), SECOND)
    assert boss.target() == boss.core.center
    snake = snake_at(Vec2(60, 60), length=30)
    snake.weapon = Gun(ammo=10)
    assert bot.target(snake, arena) == boss.core.center


def test_destroying_the_core_wins(arena):
    boss = fresh_boss(arena)
    (goal,) = load_goals(omegaconf.OmegaConf.create({"boss": "defeated"}), arena)
    snake = snake_at(Vec2(60, 60))
    for turret in boss.ring:
        turret.hit(1)
    boss.update(arena, snake, SECOND)
    for _ in range(6):
        boss.update(arena, snake, SECOND)
        for turret in boss.ring:
            turret.hit(1)
        boss.update(arena, snake, SECOND)
        boss.core.hit(1)
    assert not boss.core.alive and boss.defeated(arena) and goal.done(arena, snake)
    assert isinstance(boss.core, Core) and not any(isinstance(ent, Turret) and ent.alive for ent in boss.ring)
