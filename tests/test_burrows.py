import datetime

import pytest

from snake_quest import bot
from snake_quest.campaign import load_campaign
from snake_quest.entity import ENTITY_NAMES, Hunter, Nest
from snake_quest.goals import load_goals
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun

CAMPAIGN = load_campaign()


@pytest.fixture
def burrows(assets, game):
    game.level_counter = CAMPAIGN.resolve("burrows")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    return level_map


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def tick(nest, snake, level_map, seconds):
    level_map.game.dt = datetime.timedelta(seconds=seconds)
    nest.update(snake, level_map)


def test_nest_is_a_registered_hostile_entity():
    assert ENTITY_NAMES["nest"] is Nest and Nest.hostile


def test_sends_out_hunting_beetles_up_to_its_brood(burrows):
    nest = Nest.at_pos(Vec2(200, 150))
    burrows.entities.append(nest)
    snake = snake_at(Vec2(200 - Nest.ALERT / 2, 150))
    for _ in range(Nest.BROOD + 2):
        tick(nest, snake, burrows, Nest.SPAWN)
    beetles = [ent for ent in burrows.entities if isinstance(ent, Hunter)]
    assert len(beetles) == Nest.BROOD
    assert all(beetle.state == "hunt" for beetle in beetles)
    beetles[0].alive = False  # one shot: the nest replaces it
    tick(nest, snake, burrows, Nest.SPAWN)
    assert sum(isinstance(ent, Hunter) and ent.alive for ent in burrows.entities) == Nest.BROOD


def test_stays_quiet_while_the_snake_is_far(burrows):
    nest = Nest.at_pos(Vec2(400, 150))
    burrows.entities.append(nest)
    tick(nest, snake_at(Vec2(400 - Nest.ALERT - 40, 150)), burrows, 10 * Nest.SPAWN)
    assert burrows.entities == [nest]


def test_shots_destroy_it_and_count(burrows):
    nest = Nest.at_pos(Vec2(200, 150))
    for _ in range(Nest.HEALTH - 1):
        nest.hit(1)
        assert nest.alive and nest.flash > 0
    nest.hit(1)
    assert not nest.alive and nest.killed


def test_running_into_it_is_the_end(burrows):
    Nest.at_pos(Vec2(200, 150)).on_intersect(snake_at(Vec2(200, 150)), burrows)
    assert burrows.snake_killed


def test_destroy_all_goal(burrows):
    nests = [Nest.at_pos(Vec2(100, 100)), Nest.at_pos(Vec2(300, 100))]
    burrows.entities += nests
    (goal,) = load_goals({"destroy_all": "nest"}, map=burrows)
    assert goal.describe() == "Destroy every nest"
    nests[0].alive = False
    assert goal.status(burrows, None) == "NEST 1/2" and not goal.done(burrows, None)
    nests[1].alive = False
    assert goal.done(burrows, None)


def test_bot_goes_for_the_nests_first_once_armed(burrows):
    snake = snake_at(Vec2(150, 150), length=30)
    snake.weapon = Gun(ammo=10)
    nest = Nest.at_pos(Vec2(300, 150))
    beetle = Hunter.at_pos(Vec2(180, 150))
    burrows.entities += [nest, beetle]
    burrows.goals = load_goals({"destroy_all": "nest"}, map=burrows)
    assert bot.target(snake, burrows) == nest.pos + Vec2(4, 4)
