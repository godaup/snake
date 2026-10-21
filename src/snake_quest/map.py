import datetime
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

import omegaconf
import pyxel

from snake_quest import difficulty
from snake_quest.bosses import Boss, load_boss
from snake_quest.campaign import Level
from snake_quest.darkness import Darkness
from snake_quest.entity import ENTITY_NAMES, ENTITY_TILES, Entity
from snake_quest.goals import Goal, load_goals
from snake_quest.tiles import (
    BELT_TILES,
    DOOR_OPEN_TILE,
    DOOR_TILE,
    EMPTY_TILE,
    FLOOR_TILES,
    GATE_TILES,
    HAZARD_CUT,
    HAZARD_TILE,
    ICE_GRIP,
    ICE_TILE,
    LEVER_TILES,
    LOCK_TILES,
    MIRROR_TILE,
    PATH_TILE,
    PLATE_TILES,
    TORN_WEB_TILE,
    TRAIL_CRUMBLE,
    TRAIL_CRUMBLE_TILE,
    TRAIL_TILE,
    WALL_TILE,
    WALL_TILES,
    WALL_VARIANT_ROW,
    WEB_HOLD,
    WEB_REGROW,
    WEB_SLOW,
    WEB_TILE,
    TileKind,
    tile_kind,
)
from snake_quest.timers import Timer
from snake_quest.utils import Vec2
from snake_quest.workshop import Works

if TYPE_CHECKING:
    from snake_quest.game import Game
    from snake_quest.snake import Snake
    from snake_quest.weapons import Projectile

PORTAL_SPIN = 12  # degrees per frame of the sparkle circling each portal
COL_PORTAL_SPARK = 7
COL_DOOR_WARN = 8
NEW_POS_TRIES = 300  # attempts at keeping a spawn `away` from the snake before taking any free spot
CHASE_EVERY = 0.25  # seconds between updates of the hunters' way to the snake's tail
CRUMBS_PER_SECOND = 6  # how fast a firefly lights the breadcrumbs
CRUMBS_FADE = 3.0  # seconds a timed reveal takes to fade out at its end
TRAIL_GAP = 16  # px: no trail is laid this close to the head (a snake that is still short would run into it)


class Map:
    def __init__(self, level: Level, game: "Game"):
        self.level = level
        # the level as tuned for medium, scaled for the difficulty played
        self.cfg = difficulty.apply(omegaconf.OmegaConf.load(level.path), game.difficulty)
        # fresh tilemaps for every level: entity tiles are erased from them below
        level.load_tilemaps()

        self.start = Vec2(self.cfg.start.x, self.cfg.start.y)
        # optional colour swaps for drawing the tilemap, e.g. hedges as stone walls: {3: 5, 11: 13}
        self.tint: dict[int, int] = {int(k): int(v) for k, v in self.cfg.get("tint", {}).items()}
        # plain copies of config values read in hot paths (OmegaConf lookups are slow, bots call tile_xy a lot)
        self.header: int = game.cfg.header.h
        self.tm: int = self.cfg.tm
        self.game = game
        self.timers: list[Timer] = []
        # create initial game objects
        self.entities: list[Entity] = []
        # world positions of path tiles, drawn as breadcrumbs once revealed
        self.path: list[Vec2] = []
        self.path_revealed = False
        self.crumbs_shown = 0.0  # how many breadcrumbs are visible, grows while revealing
        self.reveal_left: float | None = None  # seconds until a timed reveal is gone; None: shown for good
        # portal tile -> the other portal of its colour (tile coordinates)
        self.portals: dict[tuple[int, int], tuple[int, int]] = {}
        portal_colours: dict[tuple[int, int], list[tuple[int, int]]] = {}
        self._portal_lock: tuple[int, int] | None = None  # portal the head arrived on, inactive until it leaves
        self._head_tile: tuple[int, int] | None = None
        self.ice = False  # any ice tiles (bots then simulate the drift)
        self.mirror = False  # any mirrored floor
        self.grip: float = float(self.cfg.get("grip", 1.0))  # the level's grip everywhere (zero gravity: low)
        self.gravity: float = float(self.cfg.get("gravity", 1.0))  # times every planet's mass
        self._wells: list | None = None  # see wells
        self.web = False  # any webs (painted, or spun later by spiders: they set it); bots then weigh them
        self.torn: dict[tuple[int, int], float] = {}  # torn web tile -> seconds until it grows back
        # optional: the tail leaves a wall behind for `trail.seconds` (tile -> [the tile it covers, seconds left])
        self.trail_seconds: float = float(self.cfg.trail.seconds) if "trail" in self.cfg else 0.0
        self.trail: dict[tuple[int, int], list] = {}
        self.snake_killed = False  # set when a hazard cuts more than the snake has, or a hunter bites the head
        self.walls_version = 0  # raised whenever walls change for good (dig, fill): caches of walls start over
        self.shake = 0  # px the camera trembles by (set by a cave-in coming near)
        # walking distances from the tail (see chase) and from the head (see flight), recomputed now and then
        self._fields: dict[str, dict[tuple[int, int], int]] = {}
        self._field_age: dict[str, float] = {}
        # iterate over tilemap
        for tile_x in range(self.cfg.width // 8):
            for tile_y in range(self.cfg.height // 8):
                img_x, img_y = pyxel.tilemaps[self.cfg.tm].pget(tile_x, tile_y)
                kind = tile_kind((img_x, img_y))
                self.ice |= kind == TileKind.ICE
                self.mirror |= kind == TileKind.MIRROR
                self.web |= kind == TileKind.WEB
                if kind == TileKind.PORTAL:
                    portal_colours.setdefault((img_x, img_y), []).append((tile_x, tile_y))
                    continue
                if kind not in (None, TileKind.PATH):
                    continue
                if kind == TileKind.PATH:
                    self.path.append(Vec2(x=tile_x * 8, y=tile_y * 8 + self.header))
                    pyxel.tilemaps[self.cfg.tm].pset(tile_x, tile_y, EMPTY_TILE)
                    continue
                e_cls = ENTITY_TILES.get((img_x, img_y))
                if e_cls is not None:
                    self.entities.append(e_cls.at_pos(Vec2(x=tile_x * 8, y=tile_y * 8 + self.header)))
                    # remove entity from 'background'
                    pyxel.tilemaps[self.cfg.tm].pset(tile_x, tile_y, EMPTY_TILE)
        for colour, pair in portal_colours.items():
            if len(pair) != 2:
                raise ValueError(f"{level.name}: portal tile {colour} appears {len(pair)} times, it needs a pair")
            self.portals[pair[0]], self.portals[pair[1]] = pair[1], pair[0]
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
        # entities eaten (removed without being killed), e.g. meals for The Hunger
        self.eaten = 0
        self.goals: list[Goal] = load_goals(self.cfg.goal, map=self)
        # optional: the play area is dark except around the head and glowing entities
        self.darkness = Darkness(self.cfg.darkness, game) if "darkness" in self.cfg else None
        tilemap = pyxel.tilemaps[self.tm]
        # the Workshop's machinery (arc 7: crates, plates, gates, locks, belts, levers), if the level has any
        workshop = set(PLATE_TILES) | set(GATE_TILES) | set(LOCK_TILES) | set(BELT_TILES) | set(LEVER_TILES)
        has_works = any(ent.block for ent in self.entities) or any(
            tilemap.pget(x, y) in workshop for y in range(self.cfg.height // 8) for x in range(self.cfg.width // 8)
        )
        self.works: Works | None = Works(self) if has_works or "plan" in self.cfg else None
        self.boss: Boss | None = load_boss(self.cfg.boss, map=self) if "boss" in self.cfg else None
        # optional: airlock doors that take turns, `airlock: {cycle: s, warn: s}` (see _cycle_doors)
        self.doors = (
            [
                (x, y)
                for y in range(self.cfg.height // 8)
                for x in range(self.cfg.width // 8)
                if tilemap.pget(x, y) in (DOOR_TILE, DOOR_OPEN_TILE)
            ]
            if "airlock" in self.cfg
            else []
        )
        self.door_cycle = float(self.cfg.airlock.cycle) if self.doors else 0.0
        self.door_warn = float(self.cfg.airlock.warn) if self.doors else 0.0
        self.door_left = self.door_cycle  # seconds until the doors swap
        self.closing: set[tuple[int, int]] = set()  # open doors about to shut (blinking; bots keep out)

    def update(self, snake: "Snake"):
        # remove dead entities
        deads = [ent for ent in self.entities if not ent.alive]
        for dead in deads:
            self.defeated += dead.tally and dead.killed
            self.eaten += dead.tally and not dead.killed
            self.entities.remove(dead)
            self.entities.extend(dead.pieces)  # what it broke into (asteroids)
        # remove dead timers
        deads = [tmr for tmr in self.timers if not tmr.alive]
        for dead in deads:
            self.timers.remove(dead)
        # remove dead projectiles
        deads = [proj for proj in self.projectiles if not proj.alive]
        for dead in deads:
            self.projectiles.remove(dead)
        self._wells = None
        self._step_on_tiles(snake)
        if self.works:
            self.works.update(snake)
        if self.torn:
            self._regrow_webs(snake, self.game.dt.total_seconds())
        if self.doors:
            self._cycle_doors(snake, self.game.dt.total_seconds())
        if self.trail_seconds:
            self._lay_trail(snake, self.game.dt.total_seconds())
        # check snake intersections
        p, q = snake.get_collision_points()
        for ent in self.entities:
            if ent.covers(p) or ent.covers(q):
                ent.on_intersect(snake=snake, map=self)
        for name in self._field_age:
            self._field_age[name] += self.game.dt.total_seconds()
        # update alive entities
        for ent in list(self.entities):  # a copy: entities may add others (nests send out beetles)
            ent.update(snake=snake, map=self)
        # update alive projectiles
        for proj in self.projectiles:
            proj.update(map=self, seconds=self.game.dt.total_seconds(), snake=snake)
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
        if self.boss:
            self.boss.update(map=self, snake=snake, dt=self.game.dt)
        # update time based goals
        for goal in self.goals:
            goal.update(map=self, snake=snake, dt=self.game.dt)

    def draw(self, offset: Vec2):
        if self.darkness and not self.game.cfg.debug:
            pyxel.pal(0, self.darkness.floor)
        for colour, replacement in self.tint.items():
            pyxel.pal(colour, replacement)
        pyxel.bltm(
            x=0,
            y=self.header,
            tm=self.cfg.tm,
            u=-offset.x,
            v=-offset.y,
            w=self.game.cfg.width,
            h=self.game.cfg.area.h,
        )
        pyxel.pal()
        header = self.header
        angle = pyxel.frame_count * PORTAL_SPIN
        for x, y in self.portals:
            spark_x = x * 8 + 4 + offset.x + round(pyxel.cos(angle) * 3)
            spark_y = y * 8 + 4 + header + offset.y + round(pyxel.sin(angle) * 3)
            pyxel.pset(spark_x, spark_y, COL_PORTAL_SPARK)
        shown = len(self.path) if self.game.cfg.debug else int(self.crumbs_shown) if self.path_revealed else 0
        alpha = self.crumbs_alpha()
        if alpha < 1:
            pyxel.dither(alpha)
        for pos in self.path[:shown]:
            pyxel.blt(pos.x + offset.x, pos.y + offset.y, 0, PATH_TILE[0] * 8, PATH_TILE[1] * 8, 8, 8, colkey=0)
        pyxel.dither(1.0)
        if self.works:
            self.works.draw(offset)
        if self.closing and pyxel.frame_count % 6 < 3:  # doors about to shut blink
            for x, y in self.closing:
                pyxel.rectb(x * 8 + offset.x, y * 8 + header + offset.y, 8, 8, COL_DOOR_WARN)
        for ent in self.entities:
            ent.draw(offset)
        for proj in self.projectiles:
            proj.draw(offset=offset)

    def new_pos(
        self, w: int = 8, h: int = 8, snake: Optional["Snake"] = None, away: float = 0, clear: list | None = None
    ) -> Vec2:
        """A free spot: floor at all four corners, no entity, not on the snake, and (if possible within a few hundred
        tries) at least `away` px from its head and outside the `clear` circles ([x, y, radius] in world px)."""
        _x, _y = 0, 0
        invalid, tries = True, 0
        while invalid:
            invalid, tries = False, tries + 1
            _x = pyxel.rndi(0, self.cfg.width - w)
            _y = pyxel.rndi(0, self.cfg.height - h) + self.header
            center = Vec2(_x + w / 2, _y + h / 2)
            too_close = snake and away and (center - snake.head.pos).length() < away
            too_close = too_close or any((center - Vec2(x, y)).length() < r for x, y, r in clear or ())
            if too_close and tries < NEW_POS_TRIES:
                invalid = True
                continue
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

    def _step_on_tiles(self, snake: "Snake") -> None:
        """Effects of the tile under the snake's head: portals move it to their partner, thorns cut the tail, ice
        makes it drift, mirrored floor swaps left and right, webs hold it."""
        snake.grip = self.grip_at(snake.head.pos)
        snake.mirrored = self.mirror and self.tile_at(snake.head.pos) == MIRROR_TILE
        tile = self.tile_xy(snake.head.pos)
        entered = tile != self._head_tile
        self._head_tile = tile
        if tile != self._portal_lock:
            self._portal_lock = None
        partner = self.portals.get(tile)
        if partner is not None and self._portal_lock is None:
            snake.head.pos = self.tile_center(partner)
            self._portal_lock = self._head_tile = partner
            self.game.sm.effect("portal")
            return
        if entered and self.tile_at(snake.head.pos) == HAZARD_TILE:
            self.game.sm.effect("hurt")
            self.snake_killed = not snake.cut(HAZARD_CUT)
        if entered and self.web and self.tile_at(snake.head.pos) == WEB_TILE:
            self.game.sm.effect("hurt")
            snake.boost(WEB_SLOW, WEB_HOLD)
            self.tear_web(tile)

    def _cycle_doors(self, snake: "Snake", seconds: float) -> None:
        """Every `cycle` seconds the airlock doors swap: the open ones shut (blinking for `warn` seconds before), the
        shut ones open. A door shutting on the body cuts it there; on the head it is the end."""
        tilemap = pyxel.tilemaps[self.tm]
        self.door_left -= seconds
        opened = [tile for tile in self.doors if tilemap.pget(*tile) == DOOR_OPEN_TILE]
        self.closing = set(opened) if self.door_left <= self.door_warn else set()
        if self.door_left > 0:
            return
        self.door_left = self.door_cycle
        shut = [tile for tile in self.doors if tilemap.pget(*tile) == DOOR_TILE]
        for tile in opened:
            tilemap.pset(*tile, DOOR_TILE)
            self._walls_changed(tile)
        for tile in shut:
            tilemap.pset(*tile, DOOR_OPEN_TILE)
            self._walls_changed(tile)
        self.closing = set()
        index = next((i for i, seg in enumerate(snake.segs) if self.tile_xy(seg.pos) in set(opened)), None)
        if index == 0:
            self.snake_killed = True
        elif index is not None:
            snake.segs = snake.segs[:index]
            self.game.sm.effect("hurt")

    def tear_web(self, tile: tuple[int, int]) -> None:
        """A web is torn (the snake ran into it, a flare burnt it): it grows back after WEB_REGROW seconds."""
        pyxel.tilemaps[self.tm].pset(*tile, TORN_WEB_TILE)
        self.torn[tile] = WEB_REGROW

    def spin_web(self, tile: tuple[int, int]) -> bool:
        """A new web on a floor tile (a spider spins it); False where there is no plain floor."""
        tilemap = pyxel.tilemaps[self.tm]
        if tilemap.pget(*tile) not in FLOOR_TILES:
            return False
        tilemap.pset(*tile, WEB_TILE)
        self.web = True
        return True

    def clear_web(self, tile: tuple[int, int]) -> None:
        """Floor again where a web (whole or torn) was, e.g. a spider's oldest when it spins a new one."""
        tilemap = pyxel.tilemaps[self.tm]
        if tilemap.pget(*tile) in (WEB_TILE, TORN_WEB_TILE):
            tilemap.pset(*tile, EMPTY_TILE)
        self.torn.pop(tile, None)

    def _regrow_webs(self, snake: "Snake", seconds: float) -> None:
        """Torn webs grow back once their time is up and nothing of the snake lies on them."""
        tilemap = pyxel.tilemaps[self.tm]
        covered = {self.tile_xy(seg.pos) for seg in snake.segs}
        for tile in list(self.torn):
            self.torn[tile] -= seconds
            if self.torn[tile] <= 0 and tile not in covered:
                del self.torn[tile]
                if tilemap.pget(*tile) == TORN_WEB_TILE:
                    tilemap.pset(*tile, WEB_TILE)

    def _lay_trail(self, snake: "Snake", seconds: float) -> None:
        """The tail turns the floor it leaves into a wall, which crumbles (TRAIL_CRUMBLE_TILE) and is gone after
        `trail_seconds`. Only plain floor turns: portals, exits, thorns and ice stay as they are."""
        tilemap = pyxel.tilemaps[self.tm]
        for tile, entry in list(self.trail.items()):
            entry[1] -= seconds
            if entry[1] <= 0:
                tilemap.pset(*tile, entry[0])
                del self.trail[tile]
            elif entry[1] <= TRAIL_CRUMBLE:
                tilemap.pset(*tile, TRAIL_CRUMBLE_TILE)
        tail = snake.segs[-1].pos
        tile = self.tile_xy(tail)
        if tile in self.trail or (tail - snake.head.pos).length() < TRAIL_GAP:
            return
        under = tilemap.pget(*tile)
        if under in FLOOR_TILES:
            self.trail[tile] = [under, self.trail_seconds]
            tilemap.pset(*tile, TRAIL_TILE)

    def pull(self, pos: Vec2, heading: float) -> float:
        """Degrees the planets turn a heading at `pos` by this frame (see Planet); the snake and the bots' arcs both use
        it."""
        return sum(ent.pull(pos, heading, self.gravity) for ent in self.wells if ent.alive)

    @property
    def wells(self) -> list:
        """What pulls: the planets on the map (looked up once per update: bots ask very often)."""
        if self._wells is None:
            self._wells = [ent for ent in self.entities if hasattr(ent, "pull")]
        return self._wells

    def grip_at(self, pos: Vec2) -> float:
        """How well the snake's heading follows its steering there (see `utils.drift`): ice's ICE_GRIP, else the level's
        `grip` (1: at once; low in zero gravity)."""
        return ICE_GRIP if self.ice and self.tile_at(pos) == ICE_TILE else self.grip

    def tile_center(self, tile: tuple[int, int]) -> Vec2:
        return Vec2(tile[0] * 8 + 4, tile[1] * 8 + 4 + self.header)

    def chase(self, snake: "Snake") -> dict[tuple[int, int], int]:
        """Walking distances (tiles) from the snake's tail to every reachable tile, shared by all hunters and computed
        again every CHASE_EVERY seconds."""
        return self._field("chase", snake.segs[-1].pos)

    def flight(self, snake: "Snake") -> dict[tuple[int, int], int]:
        """Walking distances (tiles) from the snake's head, for prey running away from it; shared like chase."""
        return self._field("flight", snake.head.pos)

    def field(self, name: str, origin: Vec2) -> dict[tuple[int, int], int]:
        """Walking distances (tiles) from `origin`, shared under `name` like chase (e.g. the mice's way to a key)."""
        return self._field(name, origin)

    def _field(self, name: str, origin: Vec2) -> dict[tuple[int, int], int]:
        if name not in self._fields or self._field_age[name] >= CHASE_EVERY:
            self._fields[name], self._field_age[name] = self.walking_distances(origin), 0.0
        return self._fields[name]

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
        self.path.sort(key=lambda pos: distance.get(self.tile_xy(pos), float("inf")))
        self.crumbs_shown = 0.0

    def tile_xy(self, pos: Vec2) -> tuple[int, int]:
        return int(pos.x) // 8, (int(pos.y) - self.header) // 8

    def walking_distances(self, origin: Vec2) -> dict[tuple[int, int], int]:
        """Steps from `origin` to every floor tile reachable from it (breadth first, through non-wall tiles; a portal
        leads to its partner in one step)."""
        tilemap = pyxel.tilemaps[self.cfg.tm]
        width, height = self.cfg.width // 8, self.cfg.height // 8
        start = self.tile_xy(origin)
        distance = {start: 0}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            portal = [self.portals[x, y]] if (x, y) in self.portals else []
            for nxt in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1), *portal]:
                inside = 0 <= nxt[0] < width and 0 <= nxt[1] < height
                if inside and nxt not in distance and tilemap.pget(*nxt) not in WALL_TILES:
                    distance[nxt] = distance[x, y] + 1
                    queue.append(nxt)
        return distance

    def tile_at(self, pos: Vec2) -> tuple[int, int]:
        """Sprite tile shown at a world position."""
        return pyxel.tilemaps[self.tm].pget(pos.x // 8, (pos.y - self.header) // 8)

    def check_on_wall(self, pos: Vec2) -> bool:
        tile = self.tile_at(pos)
        if tile not in WALL_TILES:
            return False
        return self.works is None or not self.works.unlocks(tile)  # a lock the snake has the key for opens

    def clear_line(self, a: Vec2, b: Vec2, step: float = 4) -> bool:
        """Whether no wall lies on the straight line from `a` to `b` (tested every `step` px)."""
        delta = b - a
        steps = int(delta.length() // step)
        return not any(self.check_on_wall(a + delta * (i / steps)) for i in range(1, steps))

    def dig(self, tile: tuple[int, int]) -> bool:
        """Rock dug away for good (moles): floor where a wall was, the walls around it autotiled again. The map's
        border stays closed. False where there was nothing to dig."""
        x, y = tile
        tilemap = pyxel.tilemaps[self.tm]
        inside = 0 < x < self.cfg.width // 8 - 1 and 0 < y < self.cfg.height // 8 - 1
        if not inside or tilemap.pget(x, y) not in WALL_TILES:
            return False
        tilemap.pset(x, y, EMPTY_TILE)
        self._walls_changed(tile)
        return True

    def fill(self, tile: tuple[int, int], wall: tuple[int, int]) -> None:
        """A wall tile (e.g. rubble) put down for good where there was floor; the walls around it autotiled again."""
        pyxel.tilemaps[self.tm].pset(*tile, wall)
        self._walls_changed(tile)

    def _walls_changed(self, tile: tuple[int, int]) -> None:
        tilemap = pyxel.tilemaps[self.tm]
        width, height = self.cfg.width // 8, self.cfg.height // 8

        def is_wall(x: int, y: int) -> bool:
            return not (0 <= x < width and 0 <= y < height) or tilemap.pget(x, y) in WALL_TILES

        for x in range(tile[0] - 1, tile[0] + 2):
            for y in range(tile[1] - 1, tile[1] + 2):
                if 0 <= x < width and 0 <= y < height and tilemap.pget(x, y)[1] == WALL_VARIANT_ROW:
                    mask = is_wall(x, y - 1) | is_wall(x + 1, y) << 1 | is_wall(x, y + 1) << 2 | is_wall(x - 1, y) << 3
                    tilemap.pset(x, y, (mask, WALL_VARIANT_ROW))
        self.walls_version += 1
        self._fields.clear()  # hunters and prey find the new ways at once

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
                if tilemap.pget(x, y) == WALL_TILE:
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
                    new_pos: Vec2 = map.new_pos(
                        snake=snake, away=description.get("away", 0), clear=description.get("clear")
                    )
                ent_cls: Entity = ENTITY_NAMES[description["entity"]]
                # optional: `count` at once (a wave), each at a spot of its own
                for index in range(description.get("count", 1)):
                    # optional cap: don't add more while `max` of them are on the map already
                    limit = description.get("max")
                    if limit is not None and sum(isinstance(e, ent_cls) and e.alive for e in map.entities) >= limit:
                        return
                    if index:
                        new_pos = map.new_pos(
                            snake=snake, away=description.get("away", 0), clear=description.get("clear")
                        )
                    ent = ent_cls.at_pos(new_pos)
                    # optional per-level tuning of the entity's settings, e.g. {SPEED: 1.1}
                    for name, value in description.get("with", {}).items():
                        if not hasattr(ent_cls, name):
                            raise ValueError(f"{description['entity']} has no setting {name!r}")
                        setattr(ent, name, value)
                    map.entities.append(ent)

            return callback
        elif description["type"] == "grow":

            def callback(map: "Map", snake: "Snake"):
                snake.grow += description["value"]

            return callback

    def check_win(self, snake: "Snake") -> bool:
        # all conditions must be met
        return all(goal.done(map=self, snake=snake) for goal in self.goals)
