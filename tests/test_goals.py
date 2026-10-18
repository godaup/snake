import datetime
from types import SimpleNamespace

import pytest

from snake_quest.entity import Apple, Enemy, GoldenApple
from snake_quest.goals import GOALS, load_goals
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2

SECOND = datetime.timedelta(seconds=1)


@pytest.fixture
def map():
    return SimpleNamespace(game=SimpleNamespace(score=10), defeated=0, entities=[], tile_at=lambda pos: (0, 0))


def snake_of_length(n):
    snake = Snake(pos=Vec2(50, 50), orient=0, size=2)
    snake.segs += [SnakeSeg(Vec2(50 - i, 50), 2, 0) for i in range(1, n)]
    return snake


def only_goal(cfg, map):
    (goal,) = load_goals(cfg, map=map)
    return goal


def test_score_counts_from_level_start(map):
    goal = only_goal({"score": 5}, map)
    map.game.score = 14
    assert not goal.done(map, None)
    map.game.score = 15
    assert goal.done(map, None)


def test_length(map):
    goal = only_goal({"length": 3}, map)
    assert not goal.done(map, snake_of_length(2))
    assert goal.done(map, snake_of_length(3))


def test_exit(map):
    goal = only_goal({"exit": [0, 2]}, map)
    snake = snake_of_length(1)
    assert not goal.done(map, snake)
    map.tile_at = lambda pos: (0, 2)
    assert goal.done(map, snake)


def test_survive(map):
    goal = only_goal({"survive": 3}, map)
    for _ in range(2):
        goal.update(map, None, SECOND)
    assert not goal.done(map, None)
    goal.update(map, None, SECOND)
    assert goal.done(map, None)


def test_defeat(map):
    goal = only_goal({"defeat": 2}, map)
    map.defeated = 1
    assert not goal.done(map, None)
    map.defeated = 2
    assert goal.done(map, None)


def test_hold_length_resets_when_too_short(map):
    goal = only_goal({"hold_length": {"length": 3, "seconds": 2}}, map)
    long, short = snake_of_length(3), snake_of_length(2)
    goal.update(map, long, SECOND)
    goal.update(map, short, SECOND)  # dropped below: the clock restarts
    goal.update(map, long, SECOND)
    assert not goal.done(map, long)
    goal.update(map, long, SECOND)
    assert goal.done(map, long)


def test_collect_all_ignores_other_entities(map):
    goal = only_goal({"collect_all": "golden"}, map)
    golden = GoldenApple.at_pos(Vec2(0, 0))
    map.entities = [golden, Apple.at_pos(Vec2(8, 8)), Enemy.at_pos(Vec2(16, 16))]
    assert not goal.done(map, None)
    golden.alive = False
    assert goal.done(map, None)


def test_all_goals_must_hold(map):
    goals = load_goals({"score": 1, "length": 2}, map=map)
    assert len(goals) == 2
    map.game.score = 11
    assert [g.done(map, snake_of_length(1)) for g in goals] == [True, False]


@pytest.mark.parametrize("cfg", [{}, None])
def test_level_needs_a_goal(map, cfg):
    with pytest.raises(ValueError, match="at least one goal"):
        load_goals(cfg, map=map)


def test_unknown_goal_type(map):
    with pytest.raises(ValueError, match="unknown goal types"):
        load_goals({"scroe": 1}, map=map)


@pytest.mark.parametrize(
    "cfg",
    [
        {"score": 5},
        {"length": 3},
        {"exit": [0, 2]},
        {"survive": 3},
        {"defeat": 2},
        {"hold_length": {"length": 3, "seconds": 2}},
        {"collect_all": "golden"},
    ],
    ids=lambda cfg: next(iter(cfg)),
)
def test_every_goal_has_a_description(map, cfg):
    assert only_goal(cfg, map).describe()


def test_every_registered_goal_is_tested():
    assert set(GOALS) == {"score", "length", "exit", "survive", "defeat", "hold_length", "collect_all"}
