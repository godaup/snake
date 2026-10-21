import datetime

import pytest
import pyxel

from snake_quest.bosses import BOSSES, BroodMotherBoss
from snake_quest.campaign import load_campaign
from snake_quest.caves import BroodMother, EggSac, Spiderling
from snake_quest.controls import PathController
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import WEB_TILE
from snake_quest.utils import Vec2
from snake_quest.weapons import Projectile

CAMPAIGN = load_campaign()
FRAME = datetime.timedelta(seconds=1 / 24)


@pytest.fixture
def lair(assets, game):
    game.level_counter = CAMPAIGN.resolve("brood")
    game.dt = FRAME
    return Map(level=CAMPAIGN.level(game.level_counter), game=game)


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def far(lair) -> Snake:
    return snake_at(Vec2(60, 60))


def run(boss, lair, snake, seconds):
    for _ in range(round(seconds * 24)):
        boss.update(lair, snake, FRAME)


def burst_sacs(boss, lair, snake):
    for sac in boss.sacs:
        sac.hit(sac.health)
    boss.update(lair, snake, FRAME)


def test_registered_and_in_the_level(lair):
    assert BOSSES["brood"] is BroodMotherBoss
    boss = lair.boss
    assert isinstance(boss, BroodMotherBoss) and boss.mother in lair.entities
    assert len(boss.sacs) == 4 and all(sac in lair.entities for sac in boss.sacs)
    assert boss.mother.state == "hang" and boss.mother.w == 16


def test_in_her_lair_she_is_out_of_reach(lair):
    mother = lair.boss.mother
    assert not mother.exposed and not mother.covers(mother.center) and not mother.avoid
    shot = Projectile(mother.center - Vec2(10, 0), 0, 3, 1, 10)
    for _ in range(5):
        shot.update(lair, 1 / 24)
    assert mother.health == lair.boss.full and shot.alive  # it flew underneath her


def test_egg_sacs_hatch_spiderlings_and_hurt_her_when_destroyed(lair):
    boss, snake = lair.boss, far(lair)
    sac = boss.sacs[0]
    assert isinstance(sac, EggSac) and sac.BROOD_CLS is Spiderling and sac.light > 0
    sac.left = 0
    sac.update(snake_at(sac.pos + Vec2(20, 4)), lair)
    assert any(isinstance(ent, Spiderling) for ent in lair.entities)
    sac.hit(sac.health)
    boss.update(lair, snake, FRAME)
    assert boss.mother.health == pytest.approx(boss.full - boss.sac_damage)
    assert boss.target() == next(s for s in boss.sacs if s.alive).pos + Vec2(4, 4)


def test_without_her_sacs_she_climbs_into_the_dark(lair):
    boss, snake = lair.boss, far(lair)
    burst_sacs(boss, lair, snake)
    boss.update(lair, snake, FRAME)
    assert boss.phase == 1 and boss.mother.state == "ceiling"
    assert not boss.mother.exposed and not boss.mother.covers(boss.mother.center)
    assert boss.target() is None and boss.phase_message()


def test_she_drops_where_the_head_is_heading_and_crushes(lair):
    boss = lair.boss
    snake = snake_at(Vec2(320, 300), length=30)
    burst_sacs(boss, lair, snake)
    run(boss, lair, snake, boss.setting("drop") + 0.1)
    assert boss.mother.state == "shadow"
    centre, radius = boss.danger()
    assert centre.x > snake.head.pos.x  # ahead of the head, going right
    snake.segs[0].pos = Vec2(centre.x, centre.y)  # the snake stays put under her
    run(boss, lair, snake, boss.setting("warn") + 0.1)
    assert boss.mother.state == "rest" and len(snake) == 15  # half of it
    webs = sum(
        pyxel.tilemaps[lair.tm].pget(x, y) == WEB_TILE
        for x in range(lair.tile_xy(centre)[0] - 4, lair.tile_xy(centre)[0] + 5)
        for y in range(lair.tile_xy(centre)[1] - 4, lair.tile_xy(centre)[1] + 5)
    )
    assert webs > 0  # she webs the cave around her


def test_dazed_she_takes_shots_but_cannot_bite(lair):
    boss, snake = lair.boss, far(lair)
    burst_sacs(boss, lair, snake)
    mother = boss.mother
    mother.state = "rest"
    health = mother.health
    assert mother.exposed and not mother.avoid
    assert boss.target() == mother.center
    mother.hit(1)
    assert mother.health == health - 1
    mother.on_intersect(snake, lair)
    assert not lair.snake_killed


def test_the_last_phase_dims_the_light_and_hatches_her_young(lair):
    boss, snake = lair.boss, far(lair)
    burst_sacs(boss, lair, snake)
    boss.mother.health = boss.full * 0.3
    boss.update(lair, snake, FRAME)
    boss.update(lair, snake, FRAME)
    assert boss.phase == 2 and lair.darkness.light == boss.setting("light")[1]
    count = sum(isinstance(ent, Spiderling) for ent in lair.entities)
    boss.mother.pos = Vec2(300, 300)
    boss._land(lair, snake)
    hatched = round(boss.setting("hatch"))
    assert hatched > 0 and sum(isinstance(ent, Spiderling) for ent in lair.entities) == count + hatched


def test_defeated_when_her_health_is_gone(lair):
    boss, snake = lair.boss, far(lair)
    burst_sacs(boss, lair, snake)
    boss.mother.state = "rest"
    boss.mother.hit(boss.full)
    boss.update(lair, snake, FRAME)
    assert boss.defeated(lair) and not boss.mother.alive
    assert boss.bar(lair, snake) == 0


def test_bots_keep_out_of_her_shadow(lair):
    boss = lair.boss
    boss.mother.state = "shadow"
    snake = far(lair)
    threats = PathController(lambda snake, map: None).threats(snake, lair)
    assert boss.danger() in threats
    assert isinstance(boss.mother, BroodMother)
