import datetime

import omegaconf
import pytest
import pyxel

from snake_quest import difficulty
from snake_quest.campaign import load_campaign
from snake_quest.entity import Apple
from snake_quest.goals import CollapseGoal, ExitGoal
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import CRACK_TILE, RUBBLE_TILE, WALL_TILES
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
SECOND = datetime.timedelta(seconds=1)


@pytest.fixture
def collapse(assets, game):
    game.level_counter = CAMPAIGN.resolve("collapse")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    return level_map


def cave_in(level_map) -> CollapseGoal:
    return next(goal for goal in level_map.goals if isinstance(goal, CollapseGoal))


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def far_away(level_map) -> Snake:
    goal = cave_in(level_map)
    return snake_at(level_map.tile_center(goal.order[-1]))


def test_rubble_is_a_wall_and_cracks_are_floor():
    assert RUBBLE_TILE in WALL_TILES and CRACK_TILE not in WALL_TILES


def test_nothing_comes_down_before_the_start(collapse):
    goal, snake = cave_in(collapse), far_away(collapse)
    goal.update(collapse, snake, SECOND)
    assert goal.front() == 0 and goal.filled == 0
    assert goal.status(collapse, snake).startswith("CAVE-IN IN")
    assert goal.done(collapse, snake)


def test_the_front_cracks_then_buries_the_way_from_the_start(collapse):
    goal, snake = cave_in(collapse), far_away(collapse)
    tilemap = pyxel.tilemaps[collapse.tm]
    for _ in range(round(goal.start) + 3):
        goal.update(collapse, snake, SECOND)
    assert goal.filled > 0 and goal.cracked > goal.filled
    assert tilemap.pget(*goal.order[0]) == RUBBLE_TILE
    assert collapse.check_on_wall(collapse.start)
    assert tilemap.pget(*goal.order[goal.filled]) == CRACK_TILE  # next in line: cracked
    # nearest first: what is buried is no farther along than the front
    assert all(goal.along[tile] < goal.front() for tile in goal.order[: goal.filled])
    assert goal.status(collapse, snake).endswith("m BEHIND")


def test_a_caught_body_is_cut_off_and_a_caught_head_is_the_end(collapse):
    goal = cave_in(collapse)
    tile = goal.order[40]
    snake = snake_at(collapse.tile_center(goal.order[300]), length=1)
    snake.segs += [SnakeSeg(collapse.tile_center(t), 2, 0) for t in goal.order[299:40:-10]]  # back along the way
    snake.segs += [SnakeSeg(collapse.tile_center(tile), 2, 0)] * 3  # the tail lies on `tile`
    length = len(snake)
    goal.elapsed = goal.start + goal.along[tile] / goal.speed - 0.01
    goal.update(collapse, snake, datetime.timedelta(seconds=0.05))
    assert len(snake) == length - 3 and not collapse.snake_killed
    head = snake_at(collapse.tile_center(goal.order[goal.filled + 1]), length=3)
    goal.update(collapse, head, datetime.timedelta(seconds=1))
    assert collapse.snake_killed


def test_what_lies_in_the_way_is_buried(collapse):
    goal, snake = cave_in(collapse), far_away(collapse)
    apple = Apple.at_pos(collapse.tile_center(goal.order[5]) - Vec2(4, 4))
    collapse.entities.append(apple)
    for _ in range(round(goal.start) + 2):
        goal.update(collapse, snake, SECOND)
    assert not apple.alive


def test_the_ground_trembles_when_it_is_near(collapse):
    goal = cave_in(collapse)
    tile = goal.order[200]
    snake = snake_at(collapse.tile_center(tile))
    goal.elapsed = goal.start + (goal.along[tile] - goal.NEAR / 4) / goal.speed
    goal.update(collapse, snake, datetime.timedelta(0))
    assert collapse.shake == 2
    goal.elapsed = goal.start + (goal.along[tile] - goal.NEAR * 3) / goal.speed
    goal.update(collapse, snake, datetime.timedelta(0))
    assert collapse.shake == 0


def test_harder_difficulties_bring_it_down_faster(game):
    cfg = omegaconf.OmegaConf.create({"goal": {"collapse": {"speed": 24, "start": 5, "warn": 1.5}}})
    easy = difficulty.apply(cfg, difficulty.load(game.cfg, "easy")).goal.collapse.speed
    hard = difficulty.apply(cfg, difficulty.load(game.cfg, "hard")).goal.collapse.speed
    assert easy < 24 < hard


def test_the_level_runs_from_one_end_to_the_other(collapse):
    goal = cave_in(collapse)
    exits = [goal_ for goal_ in collapse.goals if isinstance(goal_, ExitGoal)]
    assert exits
    (exit_tile, *_) = exits[0].tiles(collapse)
    assert exit_tile in goal.along and goal.along[exit_tile] > 0.9 * max(goal.along.values())
