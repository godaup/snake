"""main pyxel game engine"""

import datetime
from pathlib import Path

import omegaconf
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.sound import SoundManager
from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.states.countdown import CountdownHandler
from snake_quest.states.death import DeathStateHandler
from snake_quest.states.menu import MenuStateHandler
from snake_quest.states.pause import PauseStateHandler
from snake_quest.states.running import RunningStateHandler
from snake_quest.states.victory import VictoryStateHandler

SETTINGS = Path(__file__).parent / "settings.yaml"


class Game:
    def __init__(self, overrides: dict | None = None, start_level: int = 1):
        """define variables and start, inital values are likely overwritten immediately in start

        overrides are merged over settings.yaml, e.g. {"music": False}
        """
        self.overrides: dict = overrides or {}
        self.start_level: int = start_level
        self.campaign = load_campaign()
        self.next_stateID: StateID = StateID.MENU
        self.cfg: omegaconf.DictConfig = omegaconf.DictConfig({})
        self.sm: SoundManager = SoundManager()
        self.stateID: StateID = StateID.MENU

        self._state_handlers: dict[StateID, GameStateHandler] = {}
        self.score = 0
        self.level_counter: int = start_level
        self.initialized: bool = False
        self.dt: datetime.timedelta = datetime.timedelta(seconds=1)
        self._ref_time: datetime.datetime = datetime.datetime.now()
        self.start()

    def start(self) -> None:
        """Performs a soft restart, settings are re-loaded, objects are re-created and pyxel is re-initialized"""
        if self.initialized:
            pyxel.quit()
            self.initialized = False
        self.reload_settings()
        self.sm = SoundManager(effects=self.cfg.effects, music=self.cfg.music)
        pyxel.init(
            width=self.cfg.width,
            height=self.cfg.header.h + self.cfg.area.h + self.cfg.footer.h,
            title="Snake Quest",
            fps=self.cfg.fps,
            display_scale=self.cfg.scale,
        )
        self.initialized = True
        self.campaign.load_sprites()
        self.stateID = StateID.DEATH
        self._state_handlers: dict[StateID, GameStateHandler] = {
            StateID.MENU: MenuStateHandler(self),
            StateID.PAUSE: PauseStateHandler(self),
            StateID.RUNNING: RunningStateHandler(self),
            StateID.DEATH: DeathStateHandler(self),
            StateID.COUNTDOWN: CountdownHandler(self),
            StateID.VICTORY: VictoryStateHandler(self),
        }
        self.change_state(StateID.MENU)
        pyxel.run(self.update, self.draw)

    @property
    def handler(self) -> "GameStateHandler":
        return self._state_handlers[self.stateID]

    def reload_settings(self) -> None:
        """Load settings from yaml file and apply overrides."""
        self.cfg = omegaconf.OmegaConf.merge(omegaconf.OmegaConf.load(SETTINGS), self.overrides)

    def change_state(self, state: StateID) -> None:
        """Updates state and mouse visibility."""
        assert isinstance(state, StateID)
        # stop music
        self.sm.interrupt()
        # set mouse visibility
        pyxel.mouse(visible=self._state_handlers[state].is_visible())
        # play new music
        self.sm.play(music=self._state_handlers[state].get_music())
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
        # msg = f"{self.stateID}"
        # pyxel.text(self.handler.center_text(msg), 1, msg, 6)

    def restart(self):
        self.score = 0
        self.level_counter = self.start_level
        self._state_handlers[StateID.RUNNING] = RunningStateHandler(self)
        self.change_state(state=StateID.RUNNING)

    def level_up(self):
        if self.level_counter == len(self.campaign):
            self.change_state(StateID.VICTORY)
            return
        self.level_counter += 1
        # start a new running handler
        self._state_handlers[StateID.RUNNING] = RunningStateHandler(self)
