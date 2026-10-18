import datetime
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

import omegaconf
import pyxel

from snake_quest.campaign import Level
from snake_quest.entity import ENTITY_NAMES, ENTITY_TILES, Entity
from snake_quest.goals import Goal, load_goals
from snake_quest.timers import Timer
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.game import Game
    from snake_quest.snake import Projectile, Snake

# sprite tile coordinates (image bank 0) with a fixed meaning in every tilemap
EMPTY_TILE = (0, 0)
# the wall tile level designers paint with; replaced by a hedge variant when the map loads
WALL_TILE = (0, 3)
# hedge variant for each combination of wall neighbours: tile (mask, 8) with mask bits N=1, E=2, S=4, W=8
WALL_VARIANT_ROW = 8
WALL_TILES = frozenset({WALL_TILE} | {(mask, WALL_VARIANT_ROW) for mask in range(16)})
# floor decorations (grass, flowers, stones): drawn, but walkable and free for spawning
DECOR_TILES = frozenset((k, 9) for k in range(6))
FLOOR_TILES = frozenset({EMPTY_TILE} | DECOR_TILES)
# level design helper marking the intended route (e.g. through the maze); hidden until revealed
PATH_TILE = (3, 0)
CRUMBS_PER_SECOND = 6  # how fast a firefly lights the breadcrumbs
CRUMBS_FADE = 3.0  # seconds a timed reveal takes to fade out at its end


class Map:
    def __init__(self, level: Level, game: "Game"):
        self.level = level
        self.cfg = omegaconf.OmegaConf.load(level.path)
        # fresh tilemaps for every level: entity tiles are erased from them below
        level.load_tilemaps()

        self.start = Vec2(self.cfg.start.x, self.cfg.start.y)
        self.game = game
        self.timers: list[Timer] = []
        # create initial game objects
        self.entities: list[Entity] = []
        # world positions of path tiles, drawn as breadcrumbs once revealed
        self.path: list[Vec2] = []
        self.path_revealed = False
        self.crumbs_shown = 0.0  # how many breadcrumbs are visible, grows while revealing
        self.reveal_left: float | None = None  # seconds until a timed reveal is gone; None: shown for good
        # iterate over tilemap
        for tile_x in range(self.cfg.width // 8):
            for tile_y in range(self.cfg.height // 8):
                img_x, img_y = pyxel.tilemaps[self.cfg.tm].pget(tile_x, tile_y)
                if (img_x, img_y) in FLOOR_TILES or (img_x, img_y) in WALL_TILES:
                    continue
                if (img_x, img_y) == PATH_TILE:
                    self.path.append(Vec2(x=tile_x * 8, y=tile_y * 8 + self.game.cfg.header.h))
                    pyxel.tilemaps[self.cfg.tm].pset(tile_x, tile_y, EMPTY_TILE)
                    continue
                e_cls = ENTITY_TILES.get((img_x, img_y))
                if e_cls is not None:
                    self.entities.append(e_cls.at_pos(Vec2(x=tile_x * 8, y=tile_y * 8 + self.game.cfg.header.h)))
                    # remove entity from 'background'
                    pyxel.tilemaps[self.cfg.tm].pset(tile_x, tile_y, EMPTY_TILE)
        self._autotile_walls()
        # create timers by rules
        if "timers" in self.cfg:
            for v in self.cfg.timers.values():
                cb = self.create_callback(description=v.callback)
                self.timers.append(
                    Timer(
                        duration=datetime.timedelta(seconds=v.duration),
                        callback=cb,
                        frequency=datetime.timedelta(seconds=v.frequency) if v.frequency > 0 else None,
                        fire_n=v.fire_n,
                    )
                )
        # projectiles
        self.projectiles: list[Projectile] = []
        # entities killed by damage in this level, see DefeatGoal
        self.defeated = 0
        self.goals: list[Goal] = load_goals(self.cfg.goal, map=self)

    def update(self, snake: "Snake"):
        # remove dead entities
        deads = [ent for ent in self.entities if not ent.alive]
        for dead in deads:
            self.defeated += dead.killed
            self.entities.remove(dead)
        # remove dead timers
        deads = [tmr for tmr in self.timers if not tmr.alive]
        for dead in deads:
            self.timers.remove(dead)
        # remove dead projectiles
        deads = [proj for proj in self.projectiles if not proj.alive]
        for dead in deads:
            self.projectiles.remove(dead)
        # check snake intersections
        p, q = snake.get_collision_points()
        for ent in self.entities:
            if ent.covers(p) or ent.covers(q):
                ent.on_intersect(snake=snake, map=self)
        # update alive entities
        for ent in self.entities:
            ent.update(snake=snake, map=self)
        # update alive projectiles
        for proj in self.projectiles:
            proj.update(map=self, snake=snake)
        # update alive timers
        for tmr in self.timers:
            tmr.update(map=self, snake=snake)
        # light up breadcrumbs one after another
        if self.path_revealed and self.crumbs_shown < len(self.path):
            self.crumbs_shown += self.game.dt.total_seconds() * CRUMBS_PER_SECOND
        if self.path_revealed and self.reveal_left is not None:
            self.reveal_left -= self.game.dt.total_seconds()
            if self.reveal_left <= 0:
                self.path_revealed = False
                self.reveal_left = None
        # update time based goals
        for goal in self.goals:
            goal.update(map=self, snake=snake, dt=self.game.dt)

    def draw(self, offset: Vec2):
        pyxel.bltm(
            x=0,
            y=self.game.cfg.header.h,
            tm=self.cfg.tm,
            u=-offset.x,
            v=-offset.y,
            w=self.game.cfg.width,
            h=self.game.cfg.area.h,
        )
        shown = len(self.path) if self.game.cfg.debug else int(self.crumbs_shown) if self.path_revealed else 0
        alpha = self.crumbs_alpha()
        if alpha < 1:
            pyxel.dither(alpha)
        for pos in self.path[:shown]:
            pyxel.blt(pos.x + offset.x, pos.y + offset.y, 0, PATH_TILE[0] * 8, PATH_TILE[1] * 8, 8, 8, colkey=0)
        pyxel.dither(1.0)
        for ent in self.entities:
            ent.draw(offset)
        for proj in self.projectiles:
            proj.draw(offset=offset)

    def new_pos(self, w: int = 8, h: int = 8, snake: Optional["Snake"] = None) -> Vec2:
        _x, _y = 0, 0
        invalid = True
        while invalid:
            invalid = False
            _x = pyxel.rndi(0, self.cfg.width - w)
            _y = pyxel.rndi(0, self.cfg.height - h) + self.game.cfg.header.h
            for pos in [Vec2(_x, _y), Vec2(_x + w, _y), Vec2(_x, _y + h), Vec2(_x + w, _y + h)]:
                # no walls at the for corners
                if self.tile_at(pos) not in FLOOR_TILES:
                    invalid = True
                    break
                # no other entities
                for ent in self.entities:
                    if ent.covers(pos):
                        invalid = True
                        break
                # no snake intersection
                if snake and snake.covers(point=pos):
                    invalid = True
                    break
        return Vec2(_x, _y)

    def crumbs_alpha(self) -> float:
        """1 while the breadcrumbs shine, falling to 0 during the last CRUMBS_FADE seconds of a timed reveal."""
        if self.game.cfg.debug or self.reveal_left is None:
            return 1.0
        return max(0.0, min(1.0, self.reveal_left / CRUMBS_FADE))

    def reveal_path(self, origin: Vec2 | None = None, seconds: float | None = None) -> None:
        """Show the breadcrumbs. Without an origin all at once; with one (e.g. where a firefly was eaten) one by one,
        nearest first by walking distance through the corridors, so they light up along the route."""
        self.path_revealed = True
        # visible for `seconds`, then fading out over CRUMBS_FADE; a new reveal restarts the clock
        self.reveal_left = None if seconds is None else seconds + CRUMBS_FADE
        if origin is None:
            self.crumbs_shown = float(len(self.path))
            return
        distance = self.walking_distances(origin)
        self.path.sort(key=lambda pos: distance.get(self._tile_xy(pos), float("inf")))
        self.crumbs_shown = 0.0

    def _tile_xy(self, pos: Vec2) -> tuple[int, int]:
        return int(pos.x) // 8, (int(pos.y) - self.game.cfg.header.h) // 8

    def walking_distances(self, origin: Vec2) -> dict[tuple[int, int], int]:
        """Steps from `origin` to every floor tile reachable from it (breadth first, through non-wall tiles)."""
        tilemap = pyxel.tilemaps[self.cfg.tm]
        width, height = self.cfg.width // 8, self.cfg.height // 8
        start = self._tile_xy(origin)
        distance = {start: 0}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                inside = 0 <= nxt[0] < width and 0 <= nxt[1] < height
                if inside and nxt not in distance and tilemap.pget(*nxt) not in WALL_TILES:
                    distance[nxt] = distance[x, y] + 1
                    queue.append(nxt)
        return distance

    def tile_at(self, pos: Vec2) -> tuple[int, int]:
        """Sprite tile shown at a world position."""
        return pyxel.tilemaps[self.cfg.tm].pget(pos.x // 8, (pos.y - self.game.cfg.header.h) // 8)

    def check_on_wall(self, pos: Vec2) -> bool:
        return self.tile_at(pos) in WALL_TILES

    def _autotile_walls(self) -> None:
        """Replace every wall tile with the hedge variant matching its wall neighbours (outside the map counts
        as wall, so borders stay closed)."""
        tilemap = pyxel.tilemaps[self.cfg.tm]
        width, height = self.cfg.width // 8, self.cfg.height // 8

        def is_wall(x: int, y: int) -> bool:
            return not (0 <= x < width and 0 <= y < height) or tilemap.pget(x, y) in WALL_TILES

        variants = {}
        for y in range(height):
            for x in range(width):
                if tilemap.pget(x, y) in WALL_TILES:
                    mask = is_wall(x, y - 1) | is_wall(x + 1, y) << 1 | is_wall(x, y + 1) << 2 | is_wall(x - 1, y) << 3
                    variants[x, y] = (mask, WALL_VARIANT_ROW)
        for (x, y), tile in variants.items():
            tilemap.pset(x, y, tile)

    def create_callback(self, description: dict) -> Callable[["Map", "Snake"], None]:
        if description["type"] == "spawn":

            def callback(map: "Map", snake: "Snake"):
                # generate next entity
                if "pos" in description:
                    new_pos = Vec2(*description["pos"])
                else:
                    new_pos: Vec2 = map.new_pos(snake=snake)
                ent_cls: Entity = ENTITY_NAMES[description["entity"]]
                # optional cap: don't add more while `max` of them are on the map already
                limit = description.get("max")
                if limit is not None and sum(isinstance(e, ent_cls) and e.alive for e in map.entities) >= limit:
                    return
                map.entities.append(ent_cls.at_pos(new_pos))

            return callback
        elif description["type"] == "grow":

            def callback(map: "Map", snake: "Snake"):
                snake.grow += description["value"]

            return callback

    def check_win(self, snake: "Snake") -> bool:
        # all conditions must be met
        return all(goal.done(map=self, snake=snake) for goal in self.goals)
