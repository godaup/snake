"""Darkness (level option `darkness: {light: R}`): the play area is black except for a light around the snake's head
and around entities that glow (`Entity.light`)."""

from typing import TYPE_CHECKING

import pyxel

from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.entity import Entity
    from snake_quest.game import Game
    from snake_quest.snake import Snake

DARK = 0
KEY = 7  # colour of the holes cut into the darkness image, drawn transparent
SOFT_EDGE = 6  # px of half darkness around every light
HALF = 0.5  # dither of the soft edge
FLOOR = 1  # the black floor is drawn in this colour in dark levels, so the lit ground stands out from the dark


class Darkness:
    def __init__(self, cfg, game: "Game"):
        self.light: float = cfg.light  # radius around the head in px; a boss may change it while playing
        self.floor: int = cfg.get("floor", FLOOR)
        self.game = game
        self.image = pyxel.Image(game.cfg.width, game.cfg.area.h)

    def lights(self, snake: "Snake", entities: list["Entity"]) -> list[tuple[Vec2, float]]:
        """Centre (world coordinates) and radius of every light."""
        lights = [(snake.head.pos, self.light)]
        for ent in entities:
            if ent.alive and ent.light:
                lights.append((ent.pos + Vec2(ent.w / 2, ent.h / 2), ent.light))
        return lights

    def draw(self, offset: Vec2, snake: "Snake", entities: list["Entity"]) -> None:
        """Over the drawn play area: black beyond every light's soft edge, half dark within it."""
        header = self.game.cfg.header.h
        lights = self.lights(snake, entities)
        for extra, alpha in ((SOFT_EDGE, 1.0), (0, HALF)):
            self.image.cls(DARK)
            for pos, radius in lights:
                self.image.circ(pos.x + offset.x, pos.y + offset.y - header, max(radius + extra, 0), KEY)
            pyxel.dither(alpha)
            pyxel.blt(0, header, self.image, 0, 0, self.image.width, self.image.height, colkey=KEY)
        pyxel.dither(1.0)
