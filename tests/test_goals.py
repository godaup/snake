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
def test_every_goal_has_a_description_and_status(map, cfg):
    goal = only_goal(cfg, map)
    assert goal.describe()
    status = goal.status(map, snake_of_length(1))
    assert status and len(status) <= 20  # fits a footer slot
    progress = goal.progress(map, snake_of_length(1))
    assert progress is None or 0 <= progress <= 1


def test_progress_values(map):
    score = only_goal({"score": 4}, map)
    map.game.score = 11
    assert (score.status(map, None), score.progress(map, None)) == ("SCORE 1/4", 0.25)
    map.game.score = 99
    assert score.progress(map, None) == 1  # clamped

    assert only_goal({"exit": [0, 2]}, map).progress(map, None) is None

    survive = only_goal({"survive": 4}, map)
    survive.update(map, None, SECOND)
    assert (survive.status(map, None), survive.progress(map, None)) == ("SURVIVE 3s", 0.25)


def test_collect_all_counts_collected_and_new_spawns(map):
    goldens = [GoldenApple.at_pos(Vec2(i * 8, 0)) for i in range(4)]
    map.entities = list(goldens)
    goal = only_goal({"collect_all": "golden"}, map)
    goldens[0].alive = False
    assert goal.status(map, None) == "GOLDEN 1/4"
    map.entities += [GoldenApple.at_pos(Vec2(64, 0)), GoldenApple.at_pos(Vec2(72, 0))]  # a timer spawned two
    assert goal.status(map, None) == "GOLDEN 1/6"  # the eaten one still counts as collected
    assert goal.progress(map, None) == 1 / 6


def test_every_registered_goal_is_tested():
    assert set(GOALS) == {"score", "length", "exit", "survive", "defeat", "hold_length", "collect_all"}


@pytest.mark.parametrize(
    ("cfg", "text"),
    [
        ({"score": 1}, "Score 1 point"),
        ({"score": 5}, "Score 5 points"),
        ({"survive": 1}, "Survive 1 second"),
        ({"defeat": 1}, "Defeat 1 enemy"),
        ({"defeat": 3}, "Defeat 3 enemies"),
        ({"hold_length": {"length": 9, "seconds": 1}}, "Stay 9 long for 1 second"),
    ],
)
def test_descriptions_use_singular_and_plural(map, cfg, text):
    assert only_goal(cfg, map).describe() == text
