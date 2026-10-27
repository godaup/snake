import datetime

import pytest

from snake_quest.controls import ScriptedController
from snake_quest.snake import GEARS, INIT_SPEED, SHIFT_RATE, START_GEAR, Snake, SnakeSeg
from snake_quest.states.running import RunningStateHandler
from snake_quest.utils import Vec2

DT = datetime.timedelta(seconds=1 / 24)


def straight_snake(length, controller=None):
    """Snake heading in +x with its body trailing in -x, 1 px apart."""
    snake = Snake(pos=Vec2(100, 100), orient=0, size=2, controller=controller)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(100 - i, 100), 2, 0) for i in range(1, length)]
    return snake


def run(snake, frames):
    for _ in range(frames):
        snake.update(dt=DT, map=None)


def test_shifting_up_speeds_up_smoothly():
    snake = straight_snake(1, ScriptedController(shifts={0: 1}))
    run(snake, 1)
    assert snake.gear == START_GEAR + 1
    assert GEARS[START_GEAR] < snake.pace < GEARS[START_GEAR + 1]  # on its way
    run(snake, round((GEARS[START_GEAR + 1] - GEARS[START_GEAR]) / SHIFT_RATE * 24) + 1)
    assert snake.effective_speed == pytest.approx(INIT_SPEED * GEARS[START_GEAR + 1])


def test_gears_stop_at_the_lowest_and_highest():
    snake = straight_snake(1, ScriptedController(shifts={frame: -1 for frame in range(10)}))
    run(snake, 10)
    assert snake.gear == 0
    snake.controller = ScriptedController(shifts={frame: 1 for frame in range(10)})
    run(snake, 10)
    assert snake.gear == len(GEARS) - 1


def test_the_maze_speeds_the_snake_up(game, assets):
    game.level_counter = game.campaign.resolve("maze")
    running = RunningStateHandler(game)
    running.intro_pending = False
    running.elapsed = 1000.0  # long past the ramp's top
    running.update()
    assert running.snake.ramp == pytest.approx(running.map.cfg.ramp.max)


def test_levels_have_no_ramp_by_default(game, assets):
    game.level_counter = 1
    running = RunningStateHandler(game)
    running.intro_pending = False
    running.elapsed = 1000.0
    running.update()
    assert running.snake.ramp == 1.0


def test_turning_round_makes_the_tail_the_head():
    snake = straight_snake(10, ScriptedController(reverse_frames=[0]))
    snake.reverses = 1
    tail = snake.segs[-1]
    run(snake, 1)
    assert snake.head is tail
    assert snake.orient == 180
    assert snake.head.pos.x < 100 - 9  # moved on the way the tail came from
    assert snake.head.col == snake.colors.head
    assert snake.reverses == 0


def test_no_turning_round_without_a_reverse_left():
    snake = straight_snake(10, ScriptedController(reverse_frames=[0]))
    head = snake.head
    run(snake, 1)
    assert snake.head is head
    assert snake.orient == 0


def test_a_key_stays_in_the_body_when_turning_round():
    snake = straight_snake(5)
    snake.reverses = 1
    snake.segs[-1].key = 1
    assert snake.turn_round()
    assert snake.head.key is None
    assert snake.segs[1].key == 1
