"""Level select: the overview map of the campaign (`worldmap.py`). Every open arc (the first one, and each one after an
arc played through, see `profile.arcs_done`) can be started from its first level; the others lie under fog, which
lifts the first time an arc is seen open (`profile.arcs_seen`). A small snake crawls along the road through the
selected arc and over to the next one chosen."""

from typing import TYPE_CHECKING

import pyxel

from snake_quest.controls import ChaseController
from snake_quest.palettes import palette
from snake_quest.snake import Snake
from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.states.menu_common import (
    COL_DIM,
    COL_HIGHLIGHT,
    COL_TEXT,
    MENU_MUSIC,
    Title,
    back,
    centered_text,
    confirm,
    down,
    left,
    panel,
    right,
    up,
)
from snake_quest.states.worldmap import REGION_W, WorldMap
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.game import Game

CAM_EASE = 4.0  # share of the way to the selected region the camera pans per second
REVEAL_DELAY, REVEAL_SECONDS = 0.6, 1.6  # a newly opened arc's fog lifts after a moment
PACE = 28  # px per second the snake's target moves along the road
LEASH = 14  # px: the target waits while the snake is farther behind
PATROL = 30  # px of road at the end of the last open arc the snake walks while a locked arc is selected
PANEL_H = 34


class SelectStateHandler(GameStateHandler):
    """The overview map where an arc is chosen to play; see the module's docstring."""

    def __init__(self, game: "Game"):
        super().__init__(game=game)
        self.width = game.cfg.width
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        self.arcs = game.campaign.arcs
        self.atlas = WorldMap(self.arcs, self.height)
        self.titles = [Title(arc.name.upper(), scale=2) for arc in self.arcs]
        self.selected = 0
        self.fog = [1.0] * len(self.arcs)
        self.lifting: list[int] = []  # arcs whose fog is lifting
        self.cam_x = 0.0
        self.t = 0.0
        self.s = 0.0  # where along the road the snake heads
        self.dir = 1
        self.snake = self._new_snake(self.atlas.point(0))

    @staticmethod
    def is_visible() -> bool:
        return True

    def get_music(self) -> int | None:
        return MENU_MUSIC

    def _new_snake(self, pos: Vec2) -> Snake:
        """The little snake that walks the road, in the player's colours, at `pos`."""
        snake = Snake(pos=pos, orient=0, size=2, controller=ChaseController(lambda snake, map: self.target()))
        snake.grow = 14
        snake.recolor(palette(self.game.profile.palette))
        return snake

    def open_arcs(self) -> list[int]:
        """Indexes of the arcs that can be started."""
        unlocked = self.game.unlocked_arcs()
        return [index for index, arc in enumerate(self.arcs) if arc in unlocked]

    def on_enter(self) -> None:
        """Select the furthest open arc; an arc seen open for the first time comes out of the fog, and the snake
        crawls over into it from the arc before."""
        open_arcs = self.open_arcs()
        seen = self.game.profile.arcs_seen
        self.lifting = [i for i in open_arcs if i > 0 and self.arcs[i].name not in seen]
        self.fog = [0.0 if i in open_arcs and i not in self.lifting else 1.0 for i in range(len(self.arcs))]
        self.game.profile.see_arcs([self.arcs[i].name for i in open_arcs])
        self.selected = open_arcs[-1]
        start = self.selected - 1 if self.lifting else self.selected
        self.s = self.atlas.span(start)[0 if start == self.selected else 1]
        self.dir = 1
        self.snake = self._new_snake(self.atlas.point(self.s))
        self.cam_x = self.cam_target(start)
        self.t = 0.0

    def cam_target(self, index: int) -> float:
        """Where the camera's left edge goes to show arc `index`, kept within the map."""
        x = self.atlas.region_x(index) + REGION_W / 2 - self.width / 2
        return max(0.0, min(x, self.atlas.width - self.width))

    def choose(self, index: int) -> None:
        """Start arc `index` if it is open."""
        if index in self.open_arcs():
            self.game.start_arc(self.arcs[index])

    def best(self, index: int) -> int | None:
        """The best score in arc `index` at the difficulty chosen, or None."""
        table = self.game.profile.table(self.game.difficulty.name, self.arcs[index].name)
        return table[0].score if table else None

    def info_lines(self, index: int) -> list[str]:
        """The two lines of the info panel about arc `index`."""
        arc = self.arcs[index]
        levels = f"ARC {index + 1}   LEVELS {arc.first}-{arc.last}"
        if index not in self.open_arcs():
            return [f"{levels}   LOCKED", f"FINISH {self.arcs[index - 1].name.upper()} TO OPEN IT"]
        if arc.name in self.game.profile.arcs_done:
            levels += "   DONE"
        label = self.game.difficulty.label
        best = self.best(index)
        return [levels, f"{label} BEST {best}" if best is not None else f"NO {label} SCORE YET"]

    def target(self) -> Vec2:
        """The point on the road the snake chases: it walks the selected arc to and fro (or the end of the last open
        one, while a locked arc is selected), and along the road to another arc when one is chosen."""
        open_arcs = self.open_arcs()
        if self.selected in open_arcs:
            low, high = self.atlas.span(self.selected)
        else:
            high = self.atlas.span(open_arcs[-1])[1]
            low = high - PATROL
        if self.s <= low:
            self.dir = 1
        elif self.s >= high:
            self.dir = -1
        point = self.atlas.point(self.s)
        if (point - self.snake.head.pos).length() < LEASH:
            self.s += self.dir * PACE * min(self.game.dt.total_seconds(), 0.1)
        return point

    def update(self) -> None:
        seconds = min(self.game.dt.total_seconds(), 0.1)
        self.t += seconds
        if self.t > REVEAL_DELAY:
            for index in self.lifting:
                self.fog[index] = max(0.0, self.fog[index] - seconds / REVEAL_SECONDS)
        count = len(self.arcs)
        if left() or up():
            self.selected = max(self.selected - 1, 0)
        if right() or down():
            self.selected = min(self.selected + 1, count - 1)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and pyxel.mouse_y < self.height - PANEL_H - 8:
            index = self.atlas.region_at(pyxel.mouse_x + self.cam_x)
            if index is not None:
                if index == self.selected:
                    self.choose(index)
                    return
                self.selected = index
        self.cam_x += (self.cam_target(self.selected) - self.cam_x) * min(1.0, CAM_EASE * seconds)
        self.snake.update(dt=self.game.dt, map=None)
        if back():
            self.game.change_state(StateID.MENU)
        elif confirm():
            self.choose(self.selected)

    def draw(self) -> None:
        done = {i for i, arc in enumerate(self.arcs) if arc.name in self.game.profile.arcs_done}
        self.atlas.draw(self.cam_x, self.t, self.fog, done)
        self.snake.draw(Vec2(-self.cam_x, 0))
        width = self.width
        self.titles[self.selected].draw(width / 2, 16, self.t)
        blink = int(self.t * 2) % 2 == 0
        if blink and self.selected > 0:
            pyxel.text(6, self.height / 2 - 20, "<", COL_HIGHLIGHT)
        if blink and self.selected < len(self.arcs) - 1:
            pyxel.text(width - 10, self.height / 2 - 20, ">", COL_HIGHLIGHT)
        top = self.height - PANEL_H - 4
        panel(16, top, width - 32, PANEL_H)
        first, second = self.info_lines(self.selected)
        locked = self.selected not in self.open_arcs()
        centered_text(top + 5, first, COL_DIM if locked else COL_HIGHLIGHT, width)
        centered_text(top + 14, second, COL_DIM if locked else COL_TEXT, width)
        centered_text(top + 24, "LEFT / RIGHT: ARC   ENTER: PLAY   ESC: BACK", COL_DIM, width)
