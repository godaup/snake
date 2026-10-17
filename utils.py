from dataclasses import dataclass

import pyxel


@dataclass
class Vec2:
    """A simple 2D vector"""
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
        return pyxel.sqrt(self.x ** 2 + self.y ** 2)
