"""The overview map of the level select: one region per arc, side by side, joined by a road through all levels.

Each region is drawn once into an image from its arc's `map` theme in campaign.yaml: the ground colour, hedge clumps
(tinted like the arc's levels), scattered decorations and props, and its boss's sprite at the last stop. The caller
draws fog over regions that are not open yet; one more region after the last arc always lies under fog (more to come).
"""

import random
from dataclasses import dataclass
from itertools import pairwise

import pyxel

from snake_quest.campaign import Arc
from snake_quest.states.menu_common import Title
from snake_quest.tiles import WALL_VARIANT_ROW
from snake_quest.utils import Vec2

REGION_W = 240  # px per arc
LEAD = 40  # map before the first region
MID_Y = 100  # the road's middle height
ROAD_SWING = 36  # px up and down from it
SWING = (-0.9, 0.7, -0.4, 0.9, 0.0)  # road height at the stops of an arc, times ROAD_SWING
TOP, BOTTOM = 34, 168  # walls and props stay between the title and the info panel
NODE_R, BOSS_R = 5, 7
ROAD_CLEAR = 12  # px kept free of walls and props around the road
WALL_CLUMPS, DECOR, PROPS = 8, 36, 6
COL_ROAD, COL_ROAD_DOT, COL_ROAD_EDGE = 15, 4, 0
COL_NODE, COL_NODE_DONE, COL_NODE_EDGE, COL_NODE_TEXT = 7, 11, 0, 0
COL_FOG, COL_CLOUD, COL_CLOUD_LIGHT = 1, 5, 13
N, E, S, W = 1, 2, 4, 8


@dataclass
class Stop:
    """A level on the road."""

    pos: Vec2
    number: int  # its campaign number
    arc: int  # index of its arc
    boss: bool  # the arc's last level


class WorldMap:
    def __init__(self, arcs: list[Arc], height: int):
        self.arcs = arcs
        self.height = height
        self.width = LEAD + (len(arcs) + 1) * REGION_W  # one fogged region more
        self.stops: list[Stop] = []
        for index, arc in enumerate(arcs):
            rng = random.Random(index)
            count = arc.last - arc.first + 1
            x0 = self.region_x(index)
            for step in range(count):
                x = x0 + REGION_W / 2 if count == 1 else x0 + 30 + step * (REGION_W - 60) / (count - 1)
                y = MID_Y + SWING[step % len(SWING)] * ROAD_SWING + rng.randint(-6, 6)
                self.stops.append(Stop(Vec2(x, y), arc.first + step, index, step == count - 1))
        self.road = [Vec2(0, MID_Y), *(stop.pos for stop in self.stops), Vec2(self.width, MID_Y)]
        self.lengths = [0.0]  # road length up to each point
        for a, b in pairwise(self.road):
            self.lengths.append(self.lengths[-1] + (b - a).length())
        self.image: pyxel.Image | None = None
        self.unknown = Title("?", scale=4)

    @staticmethod
    def region_x(index: int) -> int:
        return LEAD + index * REGION_W

    def region_at(self, x: float) -> int | None:
        """Index of the arc whose region is at map x, None before the first or in the fog after the last."""
        index = int((x - LEAD) // REGION_W)
        return index if 0 <= index < len(self.arcs) else None

    # ---- the road ---------------------------------------------------------------------------------------------

    def span(self, index: int) -> tuple[float, float]:
        """Road distances of the first and last stop of arc `index`."""
        stops = [i for i, stop in enumerate(self.stops) if stop.arc == index]
        return self.lengths[stops[0] + 1], self.lengths[stops[-1] + 1]  # road[0] is the start before any stop

    def point(self, s: float) -> Vec2:
        """The point `s` px along the road."""
        s = max(0.0, min(s, self.lengths[-1]))
        for i in range(len(self.road) - 1):
            if s <= self.lengths[i + 1] or i == len(self.road) - 2:
                a, b = self.road[i], self.road[i + 1]
                part = self.lengths[i + 1] - self.lengths[i]
                return a + (b - a) * ((s - self.lengths[i]) / part if part else 0)
        return self.road[-1]

    def road_distance(self, pos: Vec2) -> float:
        best = float("inf")
        for a, b in pairwise(self.road):
            ab = b - a
            t = max(0.0, min(1.0, ((pos - a).x * ab.x + (pos - a).y * ab.y) / max(ab.x * ab.x + ab.y * ab.y, 1e-9)))
            best = min(best, (pos - (a + ab * t)).length())
        return best

    # ---- drawing ----------------------------------------------------------------------------------------------

    def render(self) -> None:
        """Draw the regions and the road into the map image (needs the sprites loaded)."""
        img = pyxel.Image(self.width, self.height)
        img.cls(0)
        for index, arc in enumerate(self.arcs):  # ground first: a region's ragged edge overlaps the one before
            ground = arc.theme.get("ground", 0)
            x0 = 0 if index == 0 else self.region_x(index)
            img.rect(x0, 0, self.region_x(index + 1) - x0, self.height, ground)
            if index > 0:
                rng = random.Random(100 + index)
                for y in range(0, self.height + 5, 5):
                    img.circ(x0 + rng.randint(-5, 5), y, 5, ground)
        self._draw_road(img)
        for index, arc in enumerate(self.arcs):
            self._draw_region(img, index, arc.theme)
        self.image = img

    def _draw_road(self, img: pyxel.Image) -> None:
        for a, b in pairwise(self.road):
            steps = max(int((b - a).length()), 1)
            for i in range(steps + 1):
                p = a + (b - a) * (i / steps)
                img.circ(p.x, p.y, 3, COL_ROAD_EDGE)
        for a, b in pairwise(self.road):
            steps = max(int((b - a).length()), 1)
            for i in range(steps + 1):
                p = a + (b - a) * (i / steps)
                img.circ(p.x, p.y, 2, COL_ROAD)
        s = 0.0
        while s < self.lengths[-1]:
            p = self.point(s)
            img.pset(p.x, p.y, COL_ROAD_DOT)
            s += 6

    def _free(self, x: float, y: float, size: int, taken: set[tuple[int, int]]) -> bool:
        """A size x size sprite at (x, y) keeps clear of the road and of the cells already taken."""
        if self.road_distance(Vec2(x + size / 2, y + size / 2)) < ROAD_CLEAR + size / 2:
            return False
        cells = {
            (int(x) // 8 + dx, int(y) // 8 + dy) for dx in range(-1, size // 8 + 1) for dy in range(-1, size // 8 + 1)
        }
        return not cells & taken

    def _draw_region(self, img: pyxel.Image, index: int, theme: dict) -> None:
        rng = random.Random(index)
        x0, x1 = self.region_x(index), self.region_x(index + 1)
        walls: set[tuple[int, int]] = set()
        placed = 0
        for _attempt in range(WALL_CLUMPS * 10):
            if placed == WALL_CLUMPS:
                break
            w, h = rng.randint(2, 5), rng.randint(1, 3)
            cx, cy = rng.randrange(x0 // 8 + 1, x1 // 8 - w), rng.randrange(TOP // 8, BOTTOM // 8 - h)
            clump = {(cx + dx, cy + dy) for dx in range(w) for dy in range(h)}
            if all(self.road_distance(Vec2(x * 8 + 4, y * 8 + 4)) >= ROAD_CLEAR + 4 for x, y in clump):
                walls |= clump
                placed += 1
        for colour, replacement in theme.get("tint", {}).items():
            img.pal(int(colour), int(replacement))
        for x, y in walls:
            mask = (
                ((x, y - 1) in walls) * N
                | ((x + 1, y) in walls) * E
                | ((x, y + 1) in walls) * S
                | ((x - 1, y) in walls) * W
            )
            img.blt(x * 8, y * 8, 0, mask * 8, WALL_VARIANT_ROW * 8, 8, 8, colkey=0)
        img.pal()
        taken = set(walls)
        for tiles, count in ((theme.get("props", []), PROPS), (theme.get("decor", []), DECOR)):
            if not tiles:
                continue
            for _ in range(count):
                for _attempt in range(10):
                    x, y = rng.randrange(x0 + 4, x1 - 12), rng.randrange(TOP, BOTTOM)
                    if self._free(x, y, 8, taken):
                        u, v = rng.choice(tiles)
                        img.blt(x, y, 0, u * 8, v * 8, 8, 8, colkey=0)
                        taken.add((x // 8, y // 8))
                        break

    def draw(self, cam_x: float, t: float, fog: list[float], done: set[int]) -> None:
        """The map with its left edge at map x `cam_x`: regions, the stops (finished arcs' in green), fog over
        region i as thick as fog[i] (0: clear, 1: hidden), and the fog after the last arc."""
        if self.image is None:
            self.render()
        pyxel.blt(-cam_x, 0, self.image, 0, 0, self.width, self.height)
        for stop in self.stops:
            x, y = stop.pos.x - cam_x, stop.pos.y
            if not -20 < x < pyxel.width + 20 or fog[stop.arc] >= 1:
                continue
            radius = BOSS_R if stop.boss else NODE_R
            pyxel.circ(x, y, radius + 1, COL_NODE_EDGE)
            pyxel.circ(x, y, radius, COL_NODE_DONE if stop.arc in done else COL_NODE)
            label = str(stop.number)
            pyxel.text(x - len(label) * 2 + 1, y - 2, label, COL_NODE_TEXT)
            boss = self.arcs[stop.arc].theme.get("boss")
            if stop.boss and boss:
                bob = pyxel.sin(t * 120 + stop.number * 40) * 2
                pyxel.blt(x - 8, y - 28 + bob, 0, boss[0] * 8, boss[1] * 8, 16, 16, colkey=0)
        for index in range(len(self.arcs) + 1):
            amount = fog[index] if index < len(fog) else 1.0
            if amount > 0:
                self._draw_fog(index, cam_x, t, amount)

    def _draw_fog(self, index: int, cam_x: float, t: float, amount: float) -> None:
        x0 = self.region_x(index) - cam_x - 6
        x1 = (self.width if index == len(self.arcs) else self.region_x(index + 1)) - cam_x + 6
        if x1 < 0 or x0 > pyxel.width:
            return
        pyxel.dither(min(amount * 1.2, 1.0))
        pyxel.rect(x0, 0, x1 - x0, self.height, COL_FOG)
        rng = random.Random(index)
        span = x1 - x0 + 24
        for _ in range(16):  # slowly drifting clouds, spilling over the fog's edges
            x = x0 - 12 + (rng.uniform(0, span) + t * rng.uniform(2, 5)) % span
            y, r = rng.uniform(TOP - 10, BOTTOM + 10), rng.randint(9, 18)
            for dx, dy, scale, col in (
                (0, 0, 1, COL_CLOUD),
                (0.8, 0.2, 0.7, COL_CLOUD),
                (-0.35, -0.4, 0.35, COL_CLOUD_LIGHT),
            ):
                pyxel.circ(x + r * dx, y + r * dy, r * scale, col)
        pyxel.dither(1.0)
        if amount > 0.5:
            self.unknown.draw((x0 + x1) / 2, MID_Y, t)
