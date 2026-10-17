import datetime
from pathlib import Path

import omegaconf
import pytest
import pyxel

ROOT = Path(__file__).resolve().parent.parent


class FakeGame:
    """Stand-in for main.Game, which cannot be constructed in tests because it enters pyxel.run."""

    def __init__(self):
        self.cfg = omegaconf.OmegaConf.load(ROOT / "settings.yaml")
        self.score = 0
        self.level_counter = 1
        self.dt = datetime.timedelta(seconds=1 / self.cfg.fps)
        self.requested_states = []
        self.level_ups = 0

    def change_state(self, state):
        self.requested_states.append(state)

    def level_up(self):
        self.level_ups += 1


@pytest.fixture(scope="session", autouse=True)
def pyxel_headless():
    cfg = omegaconf.OmegaConf.load(ROOT / "settings.yaml")
    pyxel.init(cfg.width, cfg.header.h + cfg.area.h + cfg.footer.h, title="Snake tests", headless=True)


@pytest.fixture
def assets():
    """Reload resources for every test: Map erases entity tiles from the in-memory tilemaps."""
    pyxel.load(str(ROOT / "assets.pyxres"))
    pyxel.rseed(0)


@pytest.fixture
def game():
    return FakeGame()
