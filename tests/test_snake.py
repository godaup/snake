import datetime

import pytest

from snake_quest.snake import INIT_SPEED, MAX_SPEED, MIN_SPEED, SPAWN_DELAY, Snake, SnakeSeg
from snake_quest.utils import Vec2

DT = datetime.timedelta(seconds=1 / 24)


def straight_snake(length, size=2, spacing=1):
    """Snake heading in +x with its body trailing in -x."""
    snake = Snake(pos=Vec2(100, 100), orient=0, size=size)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(100 - spacing * i, 100), size, 0) for i in range(1, length)]
    return snake


def test_head_moves_along_orientation():
    snake = straight_snake(1)
    snake.update(dt=DT, map=None)
    assert snake.head.pos.x == pytest.approx(100 + INIT_SPEED)
    assert snake.head.pos.y == pytest.approx(100)

    snake.orient = 90
    snake.update(dt=DT, map=None)
    assert snake.head.pos.y == pytest.approx(100 + INIT_SPEED)


def test_body_follows_head():
    snake = straight_snake(3)
    before = [Vec2(seg.pos.x, seg.pos.y) for seg in snake.segs]
    snake.update(dt=DT, map=None)
    assert snake.segs[1].pos == before[0]
    assert snake.segs[2].pos == before[1]


def test_turn_wraps_around():
    snake = straight_snake(1)
    snake.turn(-10)
    assert snake.orient == 350
    snake.turn(20)
    assert snake.orient == 10


@pytest.mark.parametrize(("value", "expected"), [(100, MAX_SPEED), (-5, MIN_SPEED), (2.5, 2.5)])
def test_speed_is_clamped(value, expected):
    snake = straight_snake(1)
    snake.speed = value
    assert snake.speed == expected


def test_grows_one_segment_per_spawn_delay():
    snake = straight_snake(1)
    snake.grow = 2
    big_dt = SPAWN_DELAY * 2
    # first update only accumulates the delay, the second one spawns
    snake.update(dt=big_dt, map=None)
    assert len(snake) == 1
    snake.update(dt=big_dt, map=None)
    assert len(snake) == 2
    assert snake.grow == 1


def test_negative_grow_shrinks_every_frame():
    snake = straight_snake(10)
    snake.grow = -2
    snake.update(dt=DT, map=None)
    assert len(snake) == 8
    snake.update(dt=DT, map=None)
    assert len(snake) == 6


def test_shrinking_below_zero_length_kills():
    snake = straight_snake(3)
    snake.grow = -4
    with pytest.raises(RuntimeError, match="Dead"):
        snake.update(dt=DT, map=None)


def test_self_intersect():
    assert not straight_snake(3).self_intersect()  # too short to bite itself
    assert not straight_snake(10, spacing=3).self_intersect()

    snake = straight_snake(10, spacing=3)
    snake.segs[5].pos = Vec2(snake.head.pos.x + 1, snake.head.pos.y)
    assert snake.self_intersect()


def test_covers():
    snake = straight_snake(3, size=2, spacing=2)
    assert snake.covers(Vec2(97, 100))
    assert not snake.covers(Vec2(100, 110))


def test_collision_points_are_ahead_of_head():
    snake = straight_snake(1, size=2)
    hor, ver = snake.get_collision_points()
    assert hor == Vec2(102, 100)
    assert ver.x == 100
    assert ver.y == pytest.approx(100)
