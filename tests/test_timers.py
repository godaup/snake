import datetime
from types import SimpleNamespace

from timers import Timer

SECOND = datetime.timedelta(seconds=1)


def make_map(dt=SECOND):
    return SimpleNamespace(game=SimpleNamespace(dt=dt))


def run(timer, map, steps):
    for _ in range(steps):
        timer.update(map=map, snake=None)


def test_one_shot_timer_fires_once_after_duration():
    calls = []
    timer = Timer(duration=2 * SECOND, callback=lambda map, snake: calls.append(1))
    map = make_map()

    run(timer, map, 2)
    assert calls == []  # fires only once the measured time strictly exceeds the duration
    run(timer, map, 1)
    assert calls == [1]
    assert not timer.alive
    run(timer, map, 5)
    assert calls == [1]


def test_repeating_timer_fires_initial_plus_fire_n_repeats():
    calls = []
    timer = Timer(duration=0 * SECOND, callback=lambda map, snake: calls.append(1), frequency=SECOND, fire_n=2)
    run(timer, make_map(), 20)
    assert len(calls) == 3
    assert not timer.alive


def test_unlimited_timer_keeps_firing():
    calls = []
    timer = Timer(duration=0 * SECOND, callback=lambda map, snake: calls.append(1), frequency=SECOND, fire_n=0)
    run(timer, make_map(datetime.timedelta(seconds=1.5)), 10)
    assert len(calls) == 10
    assert timer.alive


def test_disabled_timer_does_not_fire():
    calls = []
    timer = Timer(duration=0 * SECOND, callback=lambda map, snake: calls.append(1))
    timer.enabled = False
    run(timer, make_map(), 3)
    assert calls == []


def test_callback_receives_map_and_snake():
    received = []
    timer = Timer(duration=0 * SECOND, callback=lambda map, snake: received.append((map, snake)))
    map = make_map()
    timer.update(map=map, snake="snake")
    assert received == [(map, "snake")]
