import pytest
import pyxel

from snake_quest.debug import describe_tile, draw_overlay
from snake_quest.entity import GoldenApple
from snake_quest.states.running import RunningStateHandler
from snake_quest.utils import Vec2


@pytest.fixture
def running(assets, game):
    return RunningStateHandler(game)


def test_describes_walls_with_tile_and_world_coordinates(running, game):
    corner = Vec2(3, 3 + game.cfg.header.h)  # the map border is hedge
    assert describe_tile(running, corner) == "TILE 0,0 WALL (15,8) POS 3,3"


def test_names_the_entity_under_the_mouse(running, game):
    apple = GoldenApple.at_pos(Vec2(80, 80 + game.cfg.header.h))
    running.map.entities.append(apple)
    assert "GOLDEN" in describe_tile(running, Vec2(84, 84 + game.cfg.header.h))


def test_nothing_outside_the_map(running, game):
    assert describe_tile(running, Vec2(-10, game.cfg.header.h)) is None
    assert describe_tile(running, Vec2(running.map.cfg.width + 5, 50)) is None


@pytest.mark.parametrize("debug", [True, False])
def test_overlay_is_drawn_only_in_debug_mode(running, game, monkeypatch, debug):
    game.cfg.debug = debug
    monkeypatch.setattr(pyxel, "mouse_x", 200, raising=False)
    monkeypatch.setattr(pyxel, "mouse_y", 100, raising=False)
    running.cam.update()
    running.draw()
    label_corner = [pyxel.pget(x, game.cfg.header.h + 3) for x in range(2, 100)]
    assert (7 in label_corner) is debug  # white label text on the left, away from the mouse


def test_overlay_skips_the_header(running, game, monkeypatch):
    monkeypatch.setattr(pyxel, "mouse_x", 10, raising=False)
    monkeypatch.setattr(pyxel, "mouse_y", 2, raising=False)
    game.cfg.debug = True
    draw_overlay(running)  # must not fail or draw a label for the HUD
