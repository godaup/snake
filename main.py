""" main pyxel game engine """
from enum import Enum
from pathlib import Path

import omegaconf
import pyxel
import datetime

from sound import SoundManager
from states.abstract import GameState
from states.menu import MenuState
from states.pause import PauseState
from states.running import RunningState
from states.death import DeathState


class StateID(Enum):
    MENU = 0
    PAUSE = 1
    RUNNING = 2
    DEATH = 3


class Game:
    def __init__(self):
        """define variables and start, inital values are likely overwritten immediately in start"""
        self.cfg: omegaconf.DictConfig = omegaconf.DictConfig({})
        self.sm: SoundManager = SoundManager()
        self.stateID: StateID = StateID.MENU
        self._stateIMPLs: dict[StateID, GameState] = {}
        self.score = 0
        self.level_counter: int = 1
        self.initialized: bool = False
        self.dt: datetime.timedelta = datetime.timedelta(seconds=1)
        self.background: int = 0
        self._ref_time = datetime.datetime = datetime.datetime.now()
        self.start()

    def start(self) -> None:
        """Performs a soft restart, settings are re-loaded, objects are re-created and pyxel is re-initialized"""
        if self.initialized:
            pyxel.quit()
            self.initialized = False
        self.reload_settings()
        self.sm = SoundManager(effects=self.cfg.effects, music=self.cfg.music)
        pyxel.init(width=self.cfg.width, height=self.cfg.height, title='Snake', fps=self.cfg.fps,
                   display_scale=self.cfg.scale)
        self.initialized = True
        pyxel.load(filename="assets.pyxres")
        self.stateID = StateID.MENU
        self._stateIMPLs: dict[StateID, GameState] = {StateID.MENU: MenuState(self),
                                                      StateID.PAUSE: PauseState(self),
                                                      StateID.RUNNING: RunningState(self),
                                                      StateID.DEATH: DeathState(self)}
        self.background = self.cfg.background
        pyxel.run(self.update, self.draw)

    def reload_settings(self) -> None:
        """Load settings from yaml file."""
        self.cfg = omegaconf.OmegaConf.load(Path(__file__).parent / 'settings.yaml')

    def change_state(self, state: StateID) -> None:
        """Updates state and mouse visibility."""
        if state == self.stateID:
            raise RuntimeError
        # stop music
        self.sm.interrupt()
        # set mouse visibility
        pyxel.mouse(visible=self._stateIMPLs[state].is_visible())
        # play new music
        self.sm.play(music=self._stateIMPLs[state].get_music())
        self.stateID = state

    def update(self) -> None:
        """Update dt and call correct state dependent update."""
        now = datetime.datetime.now()
        self.dt = now - self._ref_time
        self._ref_time = now
        self._stateIMPLs[self.stateID].update()

    def draw(self) -> None:
        """Call correct state dependent draw."""
        self._stateIMPLs[self.stateID].draw()

    @staticmethod
    def center_text(text, page_width, char_width=pyxel.FONT_WIDTH):
        """Helper function for calculating the start x value for centered text."""

        text_width = len(text) * char_width
        return (page_width - text_width) // 2


if __name__ == "__main__":
    Game()
