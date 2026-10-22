"""Pieces shared by the menu screens: animated backdrop, big title, panels and menu input."""

import datetime
import random
from typing import TYPE_CHECKING

import pyxel

from snake_quest.controls import ChaseController
from snake_quest.palettes import palette
from snake_quest.snake import Snake
from snake_quest.tiles import DECOR_TILES, WALL_VARIANT_ROW
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.game import Game

MENU_MUSIC = 1  # theme song, see tools/compose_theme.py; music 0 is reserved for the levels
COL_PANEL, COL_PANEL_BORDER, COL_TEXT, COL_HIGHLIGHT, COL_DIM = 1, 5, 7, 10, 13
TITLE_COLORS = (11, 10, 9, 14, 12)
DEMO_TURN_SPEED = 6
N, E, S, W = 1, 2, 4, 8


# ---- input ------------------------------------------------------------------------------------------------------


def pressed(*keys: int) -> bool:
    """Whether any of `keys` was pressed this frame, repeating while held (for moving through menus)."""
    return any(pyxel.btnp(key, hold=10, repeat=4) for key in keys)


def up() -> bool:
    """Menu up: the up arrow, W or the d-pad."""
    return pressed(pyxel.KEY_UP, pyxel.KEY_W, pyxel.GAMEPAD1_BUTTON_DPAD_UP)


def down() -> bool:
    """Menu down: the down arrow, S or the d-pad."""
    return pressed(pyxel.KEY_DOWN, pyxel.KEY_S, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)


def left() -> bool:
    """Menu left: the left arrow, A or the d-pad."""
    return pressed(pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)


def right() -> bool:
    """Menu right: the right arrow, D or the d-pad."""
    return pressed(pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)


def confirm() -> bool:
    """Menu confirm: Enter, Space or the gamepad's A."""
    return any(pyxel.btnp(key) for key in (pyxel.KEY_RETURN, pyxel.KEY_SPACE, pyxel.GAMEPAD1_BUTTON_A))


def back() -> bool:
    """Menu back: Esc, Backspace or the gamepad's B."""
    return any(pyxel.btnp(key) for key in (pyxel.KEY_ESCAPE, pyxel.KEY_BACKSPACE, pyxel.GAMEPAD1_BUTTON_B))


# ---- drawing helpers --------------------------------------------------------------------------------------------


def text_width(text: str) -> int:
    """The width of `text` in px in Pyxel's font."""
    return len(text) * pyxel.FONT_WIDTH


def centered_text(y: int, text: str, col: int, width: int) -> None:
    """Centred text with a 1px dark shadow, so it stays readable when the demo snake crawls behind it."""
    x = (width - text_width(text)) // 2
    pyxel.text(x + 1, y + 1, text, 0)
    pyxel.text(x, y, text, col)


def panel(x: int, y: int, w: int, h: int) -> None:
    """A menu panel: a filled box with a border."""
    pyxel.rect(x, y, w, h, COL_PANEL)
    pyxel.rectb(x, y, w, h, COL_PANEL_BORDER)


class Title:
    """A line of text drawn big: rendered once into an image, then blitted scaled with a shadow and colour cycle."""

    def __init__(self, text: str, scale: int = 3):
        self.scale = scale
        self.w, self.h = text_width(text), pyxel.FONT_HEIGHT
        self.image = pyxel.Image(self.w, self.h)
        self.image.cls(0)
        self.image.text(0, 0, text, 7)

    def draw(self, center_x: float, center_y: float, t: float) -> None:
        """Draw the title centred at (`center_x`, `center_y`), bobbing gently and cycling its colours with time `t` in
        seconds."""
        y = center_y + pyxel.sin(t * 90) * 2  # gentle bob
        x0, y0 = center_x - self.w / 2, y - self.h / 2  # blt scales around the centre of the target rectangle
        for dx, dy, col in ((2, 2, 1), (0, 0, TITLE_COLORS[int(t * 2) % len(TITLE_COLORS)])):
            pyxel.pal(7, col)
            pyxel.blt(x0 + dx, y0 + dy, self.image, 0, 0, self.w, self.h, colkey=0, scale=self.scale)
        pyxel.pal()


# ---- backdrop ---------------------------------------------------------------------------------------------------


class Drifter:
    """A decoration tile floating across the screen."""

    def __init__(self, rng: random.Random, width: int, height: int):
        self.width, self.height = width, height
        self.tile = rng.choice(sorted(DECOR_TILES))
        self.pos = Vec2(rng.uniform(0, width), rng.uniform(0, height))
        self.vel = Vec2(rng.uniform(-6, -2), rng.uniform(-3, 3))  # px per second, a slow breeze to the left

    def update(self, seconds: float) -> None:
        """Drift on by its velocity, wrapping round the screen."""
        self.pos = self.pos + self.vel * seconds
        self.pos.x %= self.width + 16
        self.pos.y %= self.height + 16

    def draw(self) -> None:
        """Draw its sprite."""
        pyxel.blt(self.pos.x - 8, self.pos.y - 8, 0, self.tile[0] * 8, self.tile[1] * 8, 8, 8, colkey=0)


class Backdrop:
    """Animated garden behind every menu screen: hedge frame, drifting flowers and a demo snake following a looping
    figure. One instance is shared by all menu screens, so the animation continues when switching between them."""

    def __init__(self, game: "Game", seed: int = 3):
        self.game = game
        self.width = game.cfg.width
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        rng = random.Random(seed)
        self.drifters = [Drifter(rng, self.width, self.height) for _ in range(28)]
        self.t = 0.0
        self.snake = Snake(
            pos=Vec2(self.width / 2, self.height * 0.75),
            orient=0,
            size=2,
            controller=ChaseController(lambda snake, map: self.target()),
            turn_speed=DEMO_TURN_SPEED,
        )
        self.snake.grow = 36
        self.recolor()

    def recolor(self) -> None:
        """Recolour the demo snake to the palette chosen in the profile."""
        self.snake.recolor(palette(self.game.profile.palette))

    def target(self) -> Vec2:
        """A slow figure-eight over the screen for the demo snake to chase."""
        return Vec2(
            self.width / 2 + (self.width / 2 - 40) * pyxel.sin(self.t * 23),
            self.height / 2 + (self.height / 2 - 36) * pyxel.sin(self.t * 46),
        )

    def update(self, dt: datetime.timedelta) -> None:
        """Advance the drifting decorations and the demo snake by the frame's time."""
        seconds = min(dt.total_seconds(), 0.1)  # don't jump after a pause or a slow frame
        self.t += seconds
        for drifter in self.drifters:
            drifter.update(seconds)
        self.snake.update(dt=dt, map=None)

    def draw(self) -> None:
        """Clear the screen and draw the decorations, the demo snake and the hedge frame."""
        pyxel.cls(self.game.cfg.area.bg)
        for drifter in self.drifters:
            drifter.draw()
        self.snake.draw(Vec2(0, 0))
        self._draw_frame()

    def _draw_frame(self) -> None:
        """A one-tile hedge ring around the screen, autotiled like map walls (outside the screen counts as wall)."""
        cols, rows = self.width // 8, (self.height + 7) // 8

        def is_wall(tx: int, ty: int) -> bool:
            return not (0 < tx < cols - 1 and 0 < ty < rows - 1)

        for ty in range(rows):
            for tx in range(cols):
                if not is_wall(tx, ty):
                    continue
                mask = (
                    is_wall(tx, ty - 1) * N
                    | is_wall(tx + 1, ty) * E
                    | is_wall(tx, ty + 1) * S
                    | is_wall(tx - 1, ty) * W
                )
                y = min(ty * 8, self.height - 8)  # the bottom row overlaps so the frame hugs the screen edge
                pyxel.blt(tx * 8, y, 0, mask * 8, WALL_VARIANT_ROW * 8, 8, 8)
