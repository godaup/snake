""" main pyxel game engine """
import datetime
from enum import Enum
from pathlib import Path

import omegaconf
import pyxel

from sound import SoundManager
from states.abstract import GameStateHandler
from states.menu import MenuStateHandler
from states.pause import PauseStateHandler
from states.running import RunningStateHandler
from states.death import DeathStateHandler


from states import StateID


class Game:
    def __init__(self):
        """define variables and start, inital values are likely overwritten immediately in start"""
        self.next_stateID: StateID = StateID.MENU
        self.cfg: omegaconf.DictConfig = omegaconf.DictConfig({})
        self.sm: SoundManager = SoundManager()
        self.stateID: StateID = StateID.MENU
        from states.abstract import GameStateHandler
        self._state_handlers: dict[StateID, GameStateHandler] = {}
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
        self._state_handlers: dict[StateID, GameStateHandler] = {StateID.MENU: MenuStateHandler(self),
                                                                 StateID.PAUSE: PauseStateHandler(self),
                                                                 StateID.RUNNING: RunningStateHandler(self),
                                                                 StateID.DEATH: DeathStateHandler(self)}
        self.background = self.cfg.background
        self.change_state(StateID.DEATH)
        pyxel.run(self.update, self.draw)

    @property
    def handler(self) -> 'GameStateHandler':
        return self._state_handlers[self.stateID]

    def reload_settings(self) -> None:
        """Load settings from yaml file."""
        self.cfg = omegaconf.OmegaConf.load(Path(__file__).parent / 'settings.yaml')

    def change_state(self, state: StateID) -> None:
        """Updates state and mouse visibility."""
        assert isinstance(state, StateID)
        # stop music
        self.sm.interrupt()
        # set mouse visibility
        pyxel.mouse(visible=self.handler.is_visible())
        # play new music
        self.sm.play(music=self.handler.get_music())
        # do not set stateID directly, we want update to be performed first on the new handler
        self.next_stateID = state

    def update(self) -> None:
        """Update dt and call correct state dependent update."""
        now = datetime.datetime.now()
        self.dt = now - self._ref_time
        self._ref_time = now
        self.handler.update()

    def draw(self) -> None:
        """Call correct state dependent draw."""
        self.handler.draw()
        self.stateID = self.next_stateID

        # debugging
        msg = f"{self.stateID}"
        pyxel.text(self.handler.center_text(msg), 1, msg, 6)

    def restart(self):
        self.score = 0
        self.level_counter = 1
        self._state_handlers[StateID.RUNNING] = RunningStateHandler(self)
        self.change_state(state=StateID.RUNNING)


if __name__ == "__main__":
    Game()
