import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import ENTITY_NAMES, Hunter
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
FRAME = datetime.timedelta(seconds=1 / 24)


@pytest.fixture
def hunted(assets, game):
    game.level_counter = CAMPAIGN.resolve("hunted")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    return level_map


def snake_along(level_map, length=30, x=100, y=100) -> Snake:
    """A straight snake heading east, head at (x, y) in map coordinates."""
    header = level_map.header
    snake = Snake(pos=Vec2(x, y + header), orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(x - i * 1.3, y + header), 2, 0) for i in range(1, length)]
    return snake


def awake_hunter(pos: Vec2) -> Hunter:
    hunter = Hunter.at_pos(pos - Vec2(4, 4))  # centred on pos
    hunter.asleep = False
    return hunter


def test_hunter_is_a_registered_hostile_entity():
    assert ENTITY_NAMES["hunter"] is Hunter
    assert Hunter.hostile


def test_the_wilds_is_the_second_arc():
    level = CAMPAIGN.level(CAMPAIGN.resolve("hunted"))
    assert level.arc == "The Wilds" and level.resources.name == "arc2.pyxres"
    assert level.number == 6


def test_sleeps_until_the_snake_comes_near(hunted):
    snake = snake_along(hunted)
    hunter = Hunter.at_pos(snake.head.pos + Vec2(Hunter.WAKE + 20, 0))
    hunter.left = 100  # a long nap
    hunter.update(snake, hunted)
    assert hunter.asleep
    hunter.pos = snake.head.pos + Vec2(Hunter.WAKE - 20, 0)
    hunter.update(snake, hunted)
    assert not hunter.asleep


def test_wakes_when_its_nap_is_over(hunted, game):
    snake = snake_along(hunted)
    hunter = Hunter.at_pos(snake.head.pos + Vec2(200, 0))
    hunter.left = 0.01  # nap nearly over
    hunter.update(snake, hunted)
    assert not hunter.asleep


def test_a_sleeping_hunter_is_harmless(hunted):
    snake = snake_along(hunted)
    hunter = Hunter.at_pos(snake.head.pos)
    hunter.on_intersect(snake, hunted)
    assert not hunted.snake_killed


def test_chases_the_tail_along_the_way(hunted):
    snake = snake_along(hunted, x=200, y=100)
    tail = snake.segs[-1].pos
    hunter = awake_hunter(tail + Vec2(-60, 0))
    before = (hunter.center - tail).length()
    for _ in range(10):
        hunter.update(snake, hunted)
    assert (hunter.center - tail).length() < before - 10


def test_bite_takes_a_chunk_off_the_tail_then_rests(hunted, game):
    snake = snake_along(hunted, length=30)
    hunter = awake_hunter(snake.segs[20].pos)
    hunter.update(snake, hunted)
    assert len(snake) == 30 - Hunter.CHUNK
    assert hunter.state == "retreat" and hunter.left == Hunter.RETREAT
    assert game.sm.effects_played == ["hurt"]
    assert not hunted.snake_killed


def test_bite_on_a_short_snake_is_the_end(hunted):
    snake = snake_along(hunted, length=Hunter.CHUNK)
    awake_hunter(snake.segs[5].pos).update(snake, hunted)
    assert hunted.snake_killed


def test_running_into_an_awake_hunter_is_the_end(hunted):
    snake = snake_along(hunted)
    awake_hunter(snake.head.pos).on_intersect(snake, hunted)
    assert hunted.snake_killed


def test_hunters_get_faster_with_the_difficulty(hunted, game):
    game.profile.difficulty = "nightmare"
    snake = snake_along(hunted, x=300, y=100)
    hunter = awake_hunter(snake.segs[-1].pos + Vec2(-80, 0))
    start = hunter.center
    hunter.update(snake, hunted)
    assert (hunter.center - start).length() == pytest.approx(Hunter.SPEED * game.difficulty.speed)


def test_spawns_can_keep_away_from_the_snake(hunted):
    snake = snake_along(hunted)
    for _ in range(20):
        pos = hunted.new_pos(snake=snake, away=150)
        assert (pos + Vec2(4, 4) - snake.head.pos).length() >= 150
    spawn = hunted.create_callback({"type": "spawn", "entity": "hunter", "away": 150})
    spawn(hunted, snake)
    assert (hunted.entities[-1].center - snake.head.pos).length() >= 150


def test_bot_keeps_away_from_an_awake_hunter(hunted, game):
    snake = snake_along(hunted, x=150, y=100)
    hunted.entities.append(awake_hunter(snake.head.pos + Vec2(30, 0)))  # right ahead
    target = snake.head.pos + Vec2(120, 0)  # straight through it
    bot = PathController(lambda snake, map: target)
    assert bot.steer(snake, hunted) != 0.0


def run_until_break(hunter, snake, level_map):
    """Hunt until the hunt time is over; returns the state it breaks into."""
    hunter.left = 0.01
    hunter.update(snake, level_map)
    return hunter.state


def test_after_a_hunt_it_rests_or_takes_a_detour(hunted, monkeypatch):
    snake = snake_along(hunted, x=300, y=150)
    hunter = awake_hunter(snake.segs[-1].pos + Vec2(-100, 0))
    monkeypatch.setattr(pyxel, "rndf", lambda low, high: low)  # 0 < DETOUR_CHANCE: a detour
    assert run_until_break(hunter, snake, hunted) == "detour"
    hunter.state = "hunt"
    monkeypatch.setattr(pyxel, "rndf", lambda low, high: high)  # 1 >= DETOUR_CHANCE: a rest
    assert run_until_break(hunter, snake, hunted) == "rest"


def test_resting_it_stays_put_with_its_eyes_closed_then_hunts_again(hunted, monkeypatch):
    snake = snake_along(hunted, x=300, y=150)
    hunter = awake_hunter(snake.segs[-1].pos + Vec2(-100, 0))
    hunter.state, hunter.left = "rest", 1.0
    start = Vec2(hunter.pos.x, hunter.pos.y)
    hunter.update(snake, hunted)
    assert hunter.pos == start
    hunter.draw(Vec2(0, 0))
    assert hunter.img_x == 8 * Hunter.ASLEEP_IMG_X
    hunter.left = 0.01
    hunter.update(snake, hunted)
    assert hunter.state == "hunt"


def test_a_detour_moves_slowly_and_harmlessly(hunted, monkeypatch):
    snake = snake_along(hunted, x=300, y=150)
    hunter = awake_hunter(snake.segs[-1].pos + Vec2(-100, 0))
    monkeypatch.setattr(pyxel, "rndf", lambda low, high: low)
    run_until_break(hunter, snake, hunted)
    start = hunter.center
    hunter.update(snake, hunted)
    assert (hunter.center - start).length() <= Hunter.DETOUR_SPEED + 1e-6


@pytest.mark.parametrize("name", ["easy", "nightmare"])
def test_breaks_scale_with_the_difficulty(hunted, game, monkeypatch, name):
    game.profile.difficulty = name
    snake = snake_along(hunted, x=300, y=150)
    hunter = awake_hunter(snake.segs[-1].pos + Vec2(-100, 0))
    monkeypatch.setattr(pyxel, "rndf", lambda low, high: high)  # a rest of PAUSE[1] seconds at medium
    run_until_break(hunter, snake, hunted)
    assert hunter.left == pytest.approx(Hunter.PAUSE[1] * game.difficulty.hostile)
