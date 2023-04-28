""" main pyxel game engine """
from enum import Enum
from pathlib import Path

import omegaconf
import pyxel

from map import Map
from snake import Snake
from sound import SoundManager
from states.abstract import GameState
from states.menu import MenuState
from states.pause import PauseState
from states.running import RunningState


class State(Enum):
    MENU = 0
    PAUSE = 1
    RUNNING = 2


class Game:
    def __init__(self):
        """define variables and start"""
        self.cfg = None
        self.sm = None
        self.state = None
        self._states = None
        self.level_counter = 1
        self.initialized = False
        self.start()

    def start(self) -> None:
        """Performs a soft restart, settings are re-loaded, objects are re-created and pyxel is re-initialized"""
        if self.initialized:
            pyxel.quit()
            self.initialized = False
        self.reload_settings()
        self.sm = SoundManager()
        pyxel.init(width=self.cfg.width, height=self.cfg.height, title='Snake', fps=self.cfg.fps,
                   display_scale=self.cfg.scale)
        self.initialized = True
        pyxel.load(filename="assets.pyxres")
        self.state = State.MENU
        self._states: dict[State, GameState] = {State.MENU: MenuState(self),
                                                State.PAUSE: PauseState(self),
                                                State.RUNNING: RunningState(self)}
        pyxel.run(self.update, self.draw)

    def reload_settings(self) -> None:
        """Load settings from yaml file."""
        self.cfg = omegaconf.OmegaConf.load(Path(__file__).parent / 'settings.yaml')

    def change_state(self, state: State) -> None:
        """Updates state and mouse visibility."""
        if state == self.state:
            raise RuntimeError
        if state == State.MENU:
            pyxel.mouse(visible=True)
        else:
            pyxel.mouse(visible=False)
        self.state = state

    def update(self) -> None:
        """Call correct state dependent update."""
        self._states[self.state].update()

    def draw(self) -> None:
        """Call correct state dependent draw."""
        self._states[self.state].draw()


if __name__ == "__main__":
    Game()
