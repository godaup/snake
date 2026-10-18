import datetime

from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.widget import ImgInfo, Widget

COL_TEXT_COUNTDOWN = 0
COL_COUNTDOWN = 8
COUNTDOWN_SIZE = 38


class CountdownHandler(GameStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        self.remaining = None
        self.img_1 = ImgInfo(nr=1, u=0, v=0, h=32, w=32, collkey=0)
        self.img_2 = ImgInfo(nr=1, u=0, v=40, h=32, w=32, collkey=0)
        self.img_3 = ImgInfo(nr=1, u=0, v=80, h=32, w=32, collkey=0)
        self.wdg = Widget(
            x=(self.game.cfg.width - COUNTDOWN_SIZE) // 2,
            y=self.game.cfg.area.h // 2 + self.game.cfg.header.h + COUNTDOWN_SIZE // 2,
            w=COUNTDOWN_SIZE,
            h=COUNTDOWN_SIZE,
            img=self.img_3,
            bg=COL_COUNTDOWN,
            border=None,
        )

    def update(self) -> None:
        if self.remaining is None:
            self.remaining = datetime.timedelta(seconds=3)
            self.wdg.enabled = True
        self.remaining -= self.game.dt
        if self.remaining.seconds + 1 in [1, 2, 3]:
            self.wdg.img = {3: self.img_3, 2: self.img_2, 1: self.img_1}[self.remaining.seconds + 1]
        if self.remaining <= datetime.timedelta(0):
            self.wdg.enabled = False
            self.remaining = None
            self.game.change_state(StateID.RUNNING)

    @staticmethod
    def is_visible() -> bool:
        return False

    def draw(self) -> None:
        """Draw a widget with some text information."""
        self.wdg.draw()
