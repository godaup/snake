import datetime
from types import SimpleNamespace

import pytest
import pyxel

from snake_quest.controls import ChaseController, Controller, KeyboardController, ScriptedController
from snake_quest.entity import GoldenApple
from snake_quest.snake import Gun, Snake
from snake_quest.states import StateID
from snake_quest.states.running import RunningStateHandler
from snake_quest.utils import Vec2

FRAME = datetime.timedelta(seconds=1 / 24)


def snake_with(controller: Controller) -> Snake:
    snake = Snake(pos=Vec2(100, 100), orient=0, size=2, controller=controller)
    snake.grow = 0
    return snake


def test_default_controller_goes_straight():
    snake = Snake(pos=Vec2(100, 100), orient=30, size=2)
    snake.update(dt=FRAME, map=None)
    assert snake.orient == 30


def test_scripted_controller_steers_frame_by_frame_then_goes_straight():
    snake = snake_with(ScriptedController([1, 1, -0.5]))
    orients = []
    for _ in range(4):
        snake.update(dt=FRAME, map=None)
        orients.append(snake.orient)
    turn = snake.turn_speed
    assert orients == [turn, 2 * turn, round(1.5 * turn), round(1.5 * turn)]


def test_keyboard_controller(monkeypatch):
    held = set()
    monkeypatch.setattr(pyxel, "btn", lambda key: key in held)
    keyboard = KeyboardController()
    assert keyboard.steer(None, None) == 0
    held.add(pyxel.KEY_LEFT)
    assert keyboard.steer(None, None) == -1
    held.clear()
    held.add(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
    assert keyboard.steer(None, None) == 1


@pytest.mark.parametrize("target", [Vec2(100, 20), Vec2(20, 100), Vec2(180, 180)])
def test_chase_controller_reaches_its_target(target):
    snake = snake_with(ChaseController(lambda snake, map: target))
    for _ in range(200):
        snake.update(dt=FRAME, map=None)
        if (snake.head.pos - target).length() < 3:
            return
    pytest.fail(f"never reached {target}, ended at {snake.head.pos}")


def test_chase_controller_without_target_goes_straight():
    snake = snake_with(ChaseController(lambda snake, map: None))
    snake.update(dt=FRAME, map=None)
    assert snake.orient == 0


def test_weapon_fires_only_when_the_controller_says_so():
    snake = snake_with(ScriptedController(fire_frames={1}))
    snake.weapon = Gun(snake)
    snake.weapon._last_time -= datetime.timedelta(seconds=10)  # ready
    level_map = SimpleNamespace(projectiles=[])
    snake.update(dt=FRAME, map=level_map)
    assert level_map.projectiles == []
    snake.update(dt=FRAME, map=level_map)
    assert len(level_map.projectiles) == 1


def test_a_bot_can_play_a_level(assets, game):
    """The running state steers through the snake's controller, so a bot can play: chase the nearest golden apple."""
    running = RunningStateHandler(game)

    def nearest_golden(snake, map):
        goldens = [ent for ent in map.entities if isinstance(ent, GoldenApple)]
        center = Vec2(4, 4)
        return min((ent.pos + center for ent in goldens), key=lambda p: (p - snake.head.pos).length(), default=None)

    running.snake.controller = ChaseController(nearest_golden)
    for _ in range(24 * 10):
        running.update()
        assert StateID.DEATH not in game.requested_states
    assert game.score >= 5
