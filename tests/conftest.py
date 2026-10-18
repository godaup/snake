import datetime
from pathlib import Path

import omegaconf
import pytest
import pyxel

import snake_quest
from snake_quest.campaign import load_campaign
from snake_quest.profile import Profile
from snake_quest.states.menu_common import Backdrop

PACKAGE_DIR = Path(snake_quest.__file__).parent


class FakeGame:
    """Stand-in for game.Game, which cannot be constructed in tests because it enters pyxel.run."""

    def __init__(self):
        self.cfg = omegaconf.OmegaConf.load(PACKAGE_DIR / "settings.yaml")
        self.score = 0
        self.campaign = load_campaign()
        self.level_counter = 1
        self.dt = datetime.timedelta(seconds=1 / self.cfg.fps)
        self.requested_states = []
        self.profile = Profile()  # no path: never written to disk
        self.backdrop = Backdrop(self)
        self.restarts = 0
        self.level_ups = 0

    def change_state(self, state):
        self.requested_states.append(state)

    def level_up(self):
        self.level_ups += 1

    def restart(self):
        self.restarts += 1


@pytest.fixture(scope="session", autouse=True)
def pyxel_headless():
    cfg = omegaconf.OmegaConf.load(PACKAGE_DIR / "settings.yaml")
    pyxel.init(cfg.width, cfg.header.h + cfg.area.h + cfg.footer.h, title="Snake tests", headless=True)


@pytest.fixture
def assets():
    """Shared sprites and sounds; every Map loads fresh tilemaps for its own level."""
    load_campaign().load_sprites()
    pyxel.rseed(0)


@pytest.fixture
def game():
    return FakeGame()
