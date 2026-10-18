"""3 - 2 - 1 - GO! over the dimmed level, each number pulsing from big to normal size."""

import math

from snake_quest.hud import BigText
from snake_quest.states import StateID
from snake_quest.states.overlay import OverlayStateHandler

COUNT_FROM = 3
GO_SECONDS = 0.6
COLORS = {3: 8, 2: 9, 1: 10}
COL_GO = 11
SCALE_MIN, SCALE_PULSE = 4, 3


class CountdownHandler(OverlayStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        self.text = BigText(scale=SCALE_MIN)
        self.remaining = float(COUNT_FROM)

    def on_enter(self) -> None:
        self.remaining = float(COUNT_FROM)

    @staticmethod
    def is_visible() -> bool:
        return False

    def label(self) -> str:
        return str(math.ceil(self.remaining)) if self.remaining > 0 else "GO!"

    def scale(self) -> float:
        """Each number starts big and shrinks during its second; GO! shrinks over its own short time."""
        if self.remaining > 0:
            within = self.remaining - math.floor(self.remaining) or 1.0  # 1 at the start of a second, towards 0
        else:
            within = 1 + self.remaining / GO_SECONDS
        return SCALE_MIN + SCALE_PULSE * max(within, 0)

    def update(self) -> None:
        self.remaining -= self.game.dt.total_seconds()
        if self.remaining <= -GO_SECONDS:
            self.game.change_state(StateID.RUNNING)

    def draw_overlay(self) -> None:
        label = self.label()
        col = COLORS.get(math.ceil(self.remaining), COL_GO) if self.remaining > 0 else COL_GO
        center_x = self.game.cfg.width / 2
        self.text.draw(center_x + 2, self.area_center_y + 2, label, 0, scale=self.scale())  # shadow
        self.text.draw(center_x, self.area_center_y, label, col, scale=self.scale())
