"""main pyxel game engine"""

import datetime
from pathlib import Path

import omegaconf
import pyxel

from snake_quest import difficulty
from snake_quest.campaign import load_campaign
from snake_quest.difficulty import Difficulty
from snake_quest.profile import Profile
from snake_quest.sound import SoundManager
from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.states.countdown import CountdownHandler
from snake_quest.states.credits import CreditsStateHandler
from snake_quest.states.customize import CustomizeStateHandler
from snake_quest.states.death import DeathStateHandler
from snake_quest.states.highscores import HighscoresStateHandler
from snake_quest.states.level_complete import LevelCompleteStateHandler
from snake_quest.states.menu import MenuStateHandler
from snake_quest.states.menu_common import Backdrop
from snake_quest.states.mission import MissionStateHandler
from snake_quest.states.pause import PauseStateHandler
from snake_quest.states.running import RunningStateHandler
from snake_quest.states.select import SelectStateHandler
from snake_quest.states.settings import SettingsStateHandler
from snake_quest.states.victory import VictoryStateHandler

SETTINGS = Path(__file__).parent / "settings.yaml"
# vendor and app name for pyxel.user_data_dir(), where the profile (highscores, palette) is saved
USER_DATA = ("godaup", "snake-quest")


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
        self.music: int | None = None  # what is playing now

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
            quit_key=pyxel.KEY_NONE,  # ESC pauses and goes back in menus; quitting is in the menus
        )
        self.initialized = True
        self.campaign.load_sprites()
        self.profile = Profile.load(Path(pyxel.user_data_dir(*USER_DATA)) / "profile.json")
        self.profile.assign_arcs(lambda level: self.campaign.arc_of(level).name)
        self.backdrop = Backdrop(self)
        self.stateID = StateID.DEATH
        self._state_handlers: dict[StateID, GameStateHandler] = {
            StateID.MENU: MenuStateHandler(self),
            StateID.PAUSE: PauseStateHandler(self),
            StateID.RUNNING: RunningStateHandler(self),
            StateID.DEATH: DeathStateHandler(self),
            StateID.COUNTDOWN: CountdownHandler(self),
            StateID.VICTORY: VictoryStateHandler(self),
            StateID.HIGHSCORES: HighscoresStateHandler(self),
            StateID.CREDITS: CreditsStateHandler(self),
            StateID.CUSTOMIZE: CustomizeStateHandler(self),
            StateID.MISSION: MissionStateHandler(self),
            StateID.LEVEL_COMPLETE: LevelCompleteStateHandler(self),
            StateID.SELECT: SelectStateHandler(self),
            StateID.SETTINGS: SettingsStateHandler(self),
        }
        self.apply_settings()
        self.change_state(StateID.MENU)
        pyxel.run(self.update, self.draw)

    def apply_settings(self) -> None:
        """Use the profile's volumes and display settings (at start, and as they change on the settings screen)."""
        self.sm.set_volume(music=self.profile.music_volume, sound=self.profile.sound_volume)
        pyxel.fullscreen(self.profile.fullscreen)
        pyxel.screen_mode(self.profile.screen_mode)

    @property
    def difficulty(self) -> Difficulty:
        """The difficulty played: --difficulty for this run, else the one chosen in the menu."""
        return difficulty.load(self.cfg, self.cfg.get("start_difficulty") or self.profile.difficulty)

    @property
    def handler(self) -> "GameStateHandler":
        return self._state_handlers[self.stateID]

    @property
    def running_handler(self) -> "RunningStateHandler":
        """The current level, also drawn underneath the overlays (mission, countdown, level complete)."""
        return self._state_handlers[StateID.RUNNING]

    def reload_settings(self) -> None:
        """Load settings from yaml file and apply overrides."""
        self.cfg = omegaconf.OmegaConf.merge(omegaconf.OmegaConf.load(SETTINGS), self.overrides)

    def change_state(self, state: StateID) -> None:
        """Updates state, mouse visibility and music, and tells the new state it is entered."""
        assert isinstance(state, StateID)
        handler = self._state_handlers[state]
        pyxel.mouse(visible=handler.is_visible())
        # switch music only if the new state wants a different one, so menu screens share the theme
        music = handler.get_music()
        if music != self.music:
            self.sm.interrupt()
            self.sm.play(music=music)
            self.music = music
        handler.on_enter()
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

    def restart(self):
        self.score = 0
        self.level_counter = self.start_level
        self._state_handlers[StateID.RUNNING] = RunningStateHandler(self)
        self.change_state(state=StateID.RUNNING)

    def unlocked_arcs(self) -> list:
        """The arcs that can be started: the first, and each one after an arc played through."""
        arcs = self.campaign.arcs
        return [arc for i, arc in enumerate(arcs) if i == 0 or arcs[i - 1].name in self.profile.arcs_done]

    def play(self) -> None:
        """PLAY in the menu: the overview map, where an open arc is chosen."""
        self.change_state(StateID.SELECT)

    def start_arc(self, arc) -> None:
        """A new game from the first level of `arc` (also where it restarts after a game over)."""
        self.start_level = arc.first
        self.restart()

    def level_up(self):
        """Go on from the level complete screen: the next level (it opens with its mission) or the victory screen.
        Finishing an arc's last level remembers the arc (checkpoint), and a game over in the next arc restarts at its
        first level. Each arc has its own highscores, so the score starts again from 0 in the next arc (the level
        complete screen has recorded it)."""
        arc = self.campaign.arc_of(self.level_counter)
        ending = self.level_counter in self.campaign.endings  # the story's last level or the bonus arc's
        if self.level_counter == arc.last:
            self.profile.complete_arc(arc.name)
            if not ending:
                self.start_level = self.level_counter + 1
                self.score = 0
        if ending:
            self.change_state(StateID.VICTORY)
            return
        self.level_counter += 1
        self._state_handlers[StateID.RUNNING] = RunningStateHandler(self)
        self.change_state(StateID.RUNNING)
