import datetime
from pathlib import Path

import omegaconf
import pytest
import pyxel

import snake_quest
from snake_quest import difficulty
from snake_quest.campaign import load_campaign
from snake_quest.profile import Profile
from snake_quest.states.menu_common import Backdrop

PACKAGE_DIR = Path(snake_quest.__file__).parent


class FakeSounds:
    """Stand-in for sound.SoundManager that records the effects played."""

    def __init__(self):
        self.effects_played = []

    def effect(self, name):
        self.effects_played.append(name)

    def interrupt(self):
        pass

    def play(self, music=None):
        pass


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
        self.sm = FakeSounds()
        self.backdrop = Backdrop(self)
        self.restarts = 0
        self._running = None
        self.level_ups = 0

    @property
    def difficulty(self):
        """Like Game.difficulty: the profile's choice (medium unless a test changes it)."""
        return difficulty.load(self.cfg, self.cfg.get("start_difficulty") or self.profile.difficulty)

    def change_state(self, state):
        self.requested_states.append(state)

    def level_up(self):
        self.level_ups += 1

    def restart(self):
        self.restarts += 1

    def unlocked_arcs(self):
        arcs = self.campaign.arcs
        return [arc for i, arc in enumerate(arcs) if i == 0 or arcs[i - 1].name in self.profile.arcs_done]

    def play(self):
        self.plays = getattr(self, "plays", 0) + 1

    def start_arc(self, arc):
        self.started_arcs = [*getattr(self, "started_arcs", []), arc]

    def apply_settings(self):
        self.settings_applied = getattr(self, "settings_applied", 0) + 1

    @property
    def running_handler(self):
        """Like Game.running_handler; built on first use (needs the `assets` fixture)."""
        if self._running is None:
            from snake_quest.states.running import RunningStateHandler

            self._running = RunningStateHandler(self)
        return self._running


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
