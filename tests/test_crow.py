"""Boss: The Crow (level 40, the Keeper's): it is bitten only on the ground, steals apples and pulls up hedges, swoops
at the tail, and a hedge across its swoop brings it down."""

import datetime

import pytest

from snake_quest.bosses import CrowBoss
from snake_quest.campaign import load_campaign
from snake_quest.keeper import FallenApple, Jackdaw, PetController
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
FRAME = datetime.timedelta(seconds=1 / 24)
HEADER = 20


@pytest.fixture
def garden(assets, game):
    game.level_counter = CAMPAIGN.resolve("crow")
    game.dt = FRAME
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.timers.clear()
    return level_map


def snake_at(tile, length=30) -> Snake:
    pos = Vec2(tile[0] * 8 + 4, tile[1] * 8 + 4 + HEADER)
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(pos - Vec2(1.3 * i, 0), 2, 0) for i in range(1, length)]
    return snake


def run(level_map, snake, frames):
    for _ in range(frames):
        level_map.update(snake)


def test_the_crow_is_bitten_only_on_the_ground(garden):
    boss: CrowBoss = garden.boss
    crow = boss.crow
    snake = snake_at((20, 16))
    crow.state = "fly"
    crow.on_intersect(snake, garden)
    assert crow.health == boss.full
    crow.state = "perch"
    crow.on_intersect(snake, garden)
    assert crow.health == boss.full - 1 and crow.bitten
    crow.on_intersect(snake, garden)  # a moment's grace
    assert crow.health == boss.full - 1
    run(garden, snake, 1)
    assert crow.state == "fly"  # up and away


def test_the_thief_sits_on_an_apple_and_eats_it(garden):
    boss: CrowBoss = garden.boss
    snake = snake_at((5, 20))
    apple = FallenApple.at_pos(Vec2(200, 100))
    garden.entities.append(apple)
    boss.left = 0
    boss.crow.state = "hover"
    for _ in range(24 * 10):
        run(garden, snake, 1)
        if boss.crow.state == "perch":
            break
    assert boss.crow.state == "perch" and boss.target() == boss.crow.center
    assert (boss.crow.center - (apple.pos + Vec2(4, 4))).length() < 1
    run(garden, snake, round(boss.setting("perch") * 24) + 2)
    assert not apple.alive and boss.target() is None


def test_without_apples_it_pulls_up_a_planted_hedge_and_the_hand_gets_it_back(garden):
    boss: CrowBoss = garden.boss
    snake = snake_at((5, 20))
    garden.entities = [boss.crow]
    hand = garden.hand
    hand.left["hedge"] -= 1
    hand.planted.add((15, 8))
    garden.fill((15, 8), (0, 8))
    boss.left = 0
    boss.crow.state = "hover"
    run(garden, snake, 24 * 15)
    assert (15, 8) not in hand.planted and hand.left["hedge"] == 10


def swoop(boss: CrowBoss, garden, snake):
    """Phase 2, a swoop marked from the crow's spot towards the snake."""
    boss.phase = 1
    boss.crow.pos = Vec2(40, 40)
    boss.crow.state = "hover"
    boss.left = 0
    run(garden, snake, 1)
    assert boss.crow.state == "warn"
    return boss.crow.line


def test_a_swoop_warns_along_its_line_and_cuts_the_tail(garden):
    boss: CrowBoss = garden.boss
    snake = snake_at((25, 16), length=60)
    start, end = swoop(boss, garden, snake)
    assert boss.swoop_line() == (start, end)
    assert isinstance(boss.danger(), list) and boss.danger()
    before = len(snake)
    run(garden, snake, round(boss.setting("warn") * 24) + 2 + int((end - start).length() / boss.DIVE) + 4)
    assert len(snake) == before - round(boss.setting("chunk"))
    assert boss.crow.state == "fly"


def test_a_hedge_across_the_swoop_brings_the_crow_down(garden):
    boss: CrowBoss = garden.boss
    snake = snake_at((25, 16), length=60)
    start, end = swoop(boss, garden, snake)
    tile = garden.tile_xy(start + (end - start) * 0.5)
    garden.hand.sprouts[tile] = 0.4
    before = len(snake)
    run(garden, snake, round(boss.setting("warn") * 24) + 2 + int((end - start).length() / boss.DIVE) + 4)
    assert boss.crow.state == "stunned" and len(snake) == before
    assert boss.target() == boss.crow.center


def test_the_pet_goes_for_the_crow_on_the_ground(garden):
    boss: CrowBoss = garden.boss
    snake = snake_at((20, 16))
    garden.entities.append(FallenApple.at_pos(Vec2(170, 150)))
    boss.crow.pos = Vec2(100, 100)
    boss.crow.state = "stunned"
    pet = PetController()
    assert pet.choose(snake, garden) == boss.crow.center and pet.mood == "bite"


def test_phases_by_health_bring_the_flock_and_dusk(garden):
    boss: CrowBoss = garden.boss
    snake = snake_at((20, 16))
    boss.crow.health = boss.full * 0.6
    run(garden, snake, 1)
    assert boss.phase == 1 and boss.phase_message() == "THE CROW STOOPS"
    boss.crow.health = boss.full * 0.3
    run(garden, snake, 1)
    assert boss.phase == 2
    light = garden.darkness.light
    run(garden, snake, 24 * 25)
    assert garden.darkness.light < light
    assert any(isinstance(ent, Jackdaw) for ent in garden.entities)


def test_the_crow_is_beaten_when_its_health_is_gone(garden):
    boss: CrowBoss = garden.boss
    snake = snake_at((20, 16))
    boss.crow.health = 1
    boss.crow.state = "perch"
    boss.crow.on_intersect(snake, garden)
    assert boss.defeated(garden) and garden.check_win(snake)
