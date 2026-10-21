import datetime

import pytest

from snake_quest.bosses import MothershipBoss
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.space import EnginePod, Mothership, Raider
from snake_quest.utils import Vec2
from snake_quest.weapons import Projectile

CAMPAIGN = load_campaign()
FRAME = datetime.timedelta(seconds=1 / 24)


@pytest.fixture
def sector(assets, game):
    game.level_counter = CAMPAIGN.resolve("mothership")
    game.dt = FRAME
    return Map(level=CAMPAIGN.level(game.level_counter), game=game)


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def run(boss, sector, snake, seconds):
    for _ in range(round(seconds * 24)):
        boss.update(sector, snake, FRAME)


def shoot(sector, ship):
    shot = Projectile(ship.center - Vec2(24, 0), 0, 4, 1, 10)
    for _ in range(8):
        if shot.alive:  # (the map drops spent shots)
            shot.update(sector, 1 / 24)
    return shot


def drop_pods(boss, sector, snake):
    for pod in boss.pods:
        pod.hit(pod.health)
    boss.update(sector, snake, FRAME)


def test_the_ship_flies_its_course_with_its_pods(sector):
    boss, snake = sector.boss, snake_at(Vec2(60, 60))
    assert isinstance(boss, MothershipBoss) and isinstance(boss.ship, Mothership)
    assert len(boss.pods) == 3 and all(isinstance(pod, EnginePod) for pod in boss.pods)
    start = boss.ship.center
    run(boss, sector, snake, 2)
    assert boss.ship.center != start
    for pod, (dx, dy) in zip(boss.pods, boss.PODS, strict=True):
        assert pod.center == boss.ship.center + Vec2(dx, dy)


def test_shielded_while_the_pods_stand(sector):
    boss = sector.boss
    ship = boss.ship
    assert ship.shielded and ship.armored
    shoot(sector, ship)
    assert ship.health == boss.full and ship.flash > 0  # glanced off
    assert boss.target() == boss.pods[0].center


def test_each_pod_lost_costs_a_ninth(sector):
    boss, snake = sector.boss, snake_at(Vec2(60, 60))
    boss.pods[0].hit(boss.pods[0].health)
    boss.update(sector, snake, FRAME)
    assert boss.ship.health == pytest.approx(boss.full * 8 / 9)
    drop_pods(boss, sector, snake)
    assert not boss.ship.shielded and boss.ship.health == pytest.approx(boss.full * 2 / 3)
    boss.update(sector, snake, FRAME)
    assert boss.phase == 1 and boss.phase_message()


def test_the_bay_opens_and_shuts_and_drops_raiders(sector):
    boss, snake = sector.boss, snake_at(Vec2(60, 60))
    drop_pods(boss, sector, snake)
    ship = boss.ship
    assert not ship.open and not ship.exposed and boss.target() is None
    run(boss, sector, snake, boss.setting("closed") + 0.1)
    assert ship.open and ship.exposed and boss.target() == ship.center
    health = ship.health
    shoot(sector, ship)
    assert ship.health == health - 1
    run(boss, sector, snake, boss.setting("call") + 0.1)  # past its open time: shut again, the raiders out
    assert any(isinstance(ent, Raider) for ent in sector.entities)
    assert not ship.open


def test_the_last_phase_pulls_the_snake_in(sector):
    boss, snake = sector.boss, snake_at(Vec2(60, 60))
    drop_pods(boss, sector, snake)
    boss.ship.health = boss.full * 0.3
    boss.update(sector, snake, FRAME)
    boss.update(sector, snake, FRAME)
    assert boss.phase == 2 and boss.ship.tractor > 0
    near = boss.ship.center + Vec2(0, 60)
    assert boss.ship.pull(near, 0, 1.0) < 0  # going right below it: turned up, towards it
    sector._wells = None
    assert boss.ship in sector.wells


def test_raiders_shoot_when_lined_up(sector):
    snake = snake_at(Vec2(300, 300))
    raider = Raider.at_pos(Vec2(240, 296))
    raider.heading, raider.left = 0, 0
    sector.projectiles.clear()
    raider.update(snake, sector)
    assert any(shot.hostile for shot in sector.projectiles)


def test_its_hull_is_the_end_and_bots_keep_out_of_its_way(sector):
    boss, snake = sector.boss, snake_at(Vec2(60, 60))
    boss.ship.on_intersect(snake, sector)
    assert sector.snake_killed
    assert boss.danger() in PathController(lambda snake, map: None).threats(snake, sector)


def test_defeated_when_its_health_is_gone(sector):
    boss, snake = sector.boss, snake_at(Vec2(60, 60))
    drop_pods(boss, sector, snake)
    boss.ship.health = 0
    boss.update(sector, snake, FRAME)
    assert boss.defeated(sector) and boss.bar(sector, snake) == 0
