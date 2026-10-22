"""Small helpers shared by the game and the bots: vectors and the snake's head geometry."""

from dataclasses import dataclass

import pyxel


@dataclass
class Vec2:
    """A 2D vector or point in px (world positions include the header height in y)."""

    x: float = 0
    y: float = 0

    def __add__(self, other):
        if not isinstance(other, Vec2):
            raise TypeError()
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, other):
        if not isinstance(other, (int, float)):
            raise TypeError()
        return Vec2(other * self.x, other * self.y)

    def length(self):
        """The vector's length in px."""
        return pyxel.sqrt(self.x**2 + self.y**2)


def collision_points(head: Vec2, orient: float, size: float) -> tuple[Vec2, Vec2]:
    """The two points of a snake's head tested against walls: its horizontal and its vertical extreme in the
    direction it is heading."""
    hor = Vec2(x=head.x + pyxel.cos(orient) * size, y=head.y)
    ver = Vec2(x=head.x, y=head.y + pyxel.sin(orient) * size)
    return hor, ver


def drift(heading: float, orient: float, grip: float) -> float:
    """The direction a snake moves in next frame: where it points (`orient`) with full grip, on ice (grip < 1) only
    that share of the way from where it has been moving."""
    if grip >= 1:
        return orient
    return (heading + ((orient - heading + 180) % 360 - 180) * grip) % 360
