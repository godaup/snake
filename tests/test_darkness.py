import omegaconf
import pytest
import pyxel

from snake_quest.darkness import SOFT_EDGE, Darkness
from snake_quest.entity import GoldenApple
from snake_quest.states.running import RunningStateHandler
from snake_quest.utils import Vec2

LIGHT = 30


@pytest.fixture
def running(assets, game):
    running = RunningStateHandler(game)
    running.map.darkness = Darkness(omegaconf.OmegaConf.create({"light": LIGHT}), game)
    running.map.entities.clear()
    running.cam.update()
    return running


def screen(running, world: Vec2) -> tuple[int, int]:
    return int(world.x + running.cam.offset.x), int(world.y + running.cam.offset.y)


def lit(running, world: Vec2, size: int = 3) -> bool:
    """Any pixel around a world position that isn't black."""
    x, y = screen(running, world)
    return any(pyxel.pget(x + dx, y + dy) != 0 for dx in range(-size, size + 1) for dy in range(-size, size + 1))


def border_wall(running, game) -> Vec2:
    """A point on the hedge at the top border, which is never black when lit."""
    return Vec2(running.snake.head.pos.x, game.cfg.header.h + 3)


def test_only_the_light_around_the_head_shows(running, game):
    running.draw()
    head = running.snake.head.pos
    assert lit(running, head)
    assert (head - border_wall(running, game)).length() > LIGHT + SOFT_EDGE
    assert not lit(running, border_wall(running, game))


def test_glowing_entities_light_their_surroundings(running, game):
    wall = border_wall(running, game)
    apple = GoldenApple.at_pos(wall + Vec2(-4, 4))
    running.map.entities.append(apple)
    running.draw()
    assert lit(running, wall)


def test_hud_stays_visible(running, game):
    running.draw()
    assert any(pyxel.pget(x, 1) != 0 for x in range(game.cfg.width))


def test_debug_shows_the_whole_level(running, game):
    game.cfg.debug = True
    running.draw()
    assert lit(running, border_wall(running, game))


def test_level_option_creates_darkness(assets, game, monkeypatch):
    original = omegaconf.OmegaConf.load

    def with_darkness(path):
        cfg = original(path)
        if str(path).endswith("classic.yaml"):
            cfg.darkness = {"light": 25}
        return cfg

    monkeypatch.setattr(omegaconf.OmegaConf, "load", with_darkness)
    running = RunningStateHandler(game)
    assert running.map.darkness.light == 25
