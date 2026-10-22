"""The Keeper (the bonus arc, levels 36-40, see docs/arc8-keeper.md): the snake moves on its own and the player is the
hand that shapes its garden.

The snake is a pet: a `PetController`, a bot whose choices can be read off the screen (it eats the nearest food by
walking distance, keeps its choice, doesn't know thorns and draws its way). The player's `Hand` plants hedges, apple
trees, lures and lanterns from a level's budgets (`hand: {hedge: 10, ...}`), driven by a `HandInput` (mouse, keys,
gamepad) or, in tests, by a `HandBot` that follows the level's `keeper` plan with human limits."""

import math
from typing import TYPE_CHECKING

import pyxel

from snake_quest.controls import PathController
from snake_quest.entity import Apple, Critter, Entity, GoldenApple, Hunter, register
from snake_quest.tiles import FLOOR_TILES, WALL_TILES, WALL_VARIANT_ROW
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake

TOOLS = ("hedge", "tree", "lure", "lantern")  # in the order of the keys 1-4
SPROUT = 0.4  # seconds a planted hedge sprouts before it is a wall (and then only once the snake has left it)
GROW_CLEAR = 16  # px: a sprout doesn't grow while the head is this close (it would grow into its face)
CLEAR = 24  # px around the head where nothing can be planted
COOLDOWN = 0.15  # seconds between two placements
THRIFT = 1  # points per tool left unused when the level is won
LURE_RANGE = 96  # px: hunters this close to a lure hunt it instead of the tail
PENNED = 3.0  # seconds a hunter shut in by hedges (no way to the tail, none to a lure) lasts
COL_OK, COL_NO, COL_INTENT, COL_TARGET = 11, 8, 7, 10
ICONS = {"hedge": (1, 25), "tree": (3, 25), "lure": (6, 25), "lantern": (9, 25)}  # toolbar and cursor
MOODS = {"eat": (10, 25), "bite": (10, 25), "run": (11, 25), "wander": (12, 25), "light": (13, 25)}
SPROUT_TILES = ((0, 25), (1, 25))
PLANTED_MARK = (2, 25)


@register("fallen")
class FallenApple(Apple):
    """An apple fallen from a tree (or lying where a level put it): a smaller apple (LENGTH segments, a point), and no
    other grows when it is eaten."""

    _img_x = 14
    _img_y = 25
    LENGTH = 3

    def on_intersect(self, snake: "Snake", map: "Map"):
        snake.grow += self.LENGTH
        map.game.score += 1
        map.game.sm.effect("eat")
        self.alive = False


@register("tree")
class Tree(Entity):
    """An apple tree the hand planted (16x16): a sapling for GROW seconds, then every DROP seconds an apple falls on a
    free tile within DROP_REACH tiles, while fewer than CROP of its apples lie about. Bots keep clear of it (`solid`);
    the snake brushing it does no harm."""

    _img_x = 4
    _img_y = 25
    solid = True
    tally = False
    RADIUS = 3  # px: the trunk (bots keep SOLID px more from it; its apples lie a tile out, within reach)
    GROW = 6.0  # seconds
    DROP = 2.5  # seconds between apples (times the difficulty's `helpful` factor)
    CROP = 2
    DROP_REACH = 2  # tiles around the tree

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.h = 16
        self.age = 0.0
        self.left = self.DROP
        self.apples: list[FallenApple] = []

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(8, 8)

    @property
    def grown(self) -> bool:
        """Whether the sapling has grown into a tree that drops apples."""
        return self.age >= self.GROW

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        self.age += seconds
        self.apples = [apple for apple in self.apples if apple.alive]
        if not self.grown:
            return
        self.left -= seconds
        if self.left > 0 or len(self.apples) >= self.CROP:
            return
        self.left = self.DROP * map.game.difficulty.helpful
        spot = self._spot(snake, map)
        if spot is not None:
            apple = FallenApple.at_pos(spot)
            self.apples.append(apple)
            map.entities.append(apple)

    def _spot(self, snake: "Snake", map: "Map") -> Vec2 | None:
        """A free floor tile next to the tree (not under it), picked at random."""
        x0, y0 = map.tile_xy(self.pos)
        tiles = [
            (x, y)
            for x in range(x0 - self.DROP_REACH, x0 + 2 + self.DROP_REACH)
            for y in range(y0 - self.DROP_REACH, y0 + 2 + self.DROP_REACH)
            if not (x0 <= x <= x0 + 1 and y0 <= y <= y0 + 1)
        ]
        while tiles:
            tile = tiles.pop(pyxel.rndi(0, len(tiles) - 1))
            pos = Vec2(tile[0] * 8, tile[1] * 8 + map.header)
            if map.hand is not None and map.hand.free(tile, snake, clear=0):
                return pos
        return None

    def draw(self, offset: "Vec2"):
        if self.grown:
            super().draw(offset)
            return
        bottom = self.pos + offset + Vec2(4, 8)
        pyxel.blt(bottom.x, bottom.y, 0, 3 * 8, 25 * 8, 8, 8, colkey=0)

    def lifted(self) -> None:
        """Taken back by the hand: its apples go with it."""
        self.alive = False
        for apple in self.apples:
            apple.alive, apple.tally = False, False


@register("lure")
class Lure(Entity):
    """A worm on a stick, wriggling. Hunters within LURE_RANGE px hunt it instead of the snake's tail; one that reaches
    it eats for FEED seconds (it sits still), and after BITES meals the lure is gone."""

    _img_x = 6
    _img_y = 25
    tally = False
    light = 6
    BITES = 3
    FEED = 2.5  # seconds
    REACH = 6  # px from its centre to a hunter's

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bites = self.BITES

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(4, 4)

    def update(self, snake: "Snake", map: "Map"):
        for ent in map.entities:
            if not (ent.alive and isinstance(ent, Hunter) and ent.state == "hunt"):
                continue
            if (ent.center - self.center).length() < self.REACH + ent.w / 2:
                ent._begin("rest", self.FEED / map.game.difficulty.helpful)  # shorter meals when harder
                self.bites -= 1
                if self.bites <= 0:
                    self.alive = False
                    return

    def draw(self, offset: "Vec2"):
        self.img_x = 8 * (self._img_x + (pyxel.frame_count // 6) % 2)
        super().draw(offset)


@register("lantern")
class Lantern(Entity):
    """A lantern: a light (LIGHT px) in the dark for OIL seconds, then it goes out and is gone. Sleeping hunters its
    light falls on wake up. The pet sees what it lights, and in the dark walks to it."""

    _img_x = 8
    _img_y = 25
    tally = False
    LIGHT = 40  # px
    OIL = 40.0  # seconds; it burns faster on harder difficulties (their `helpful` factor)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.oil = self.OIL
        self.light = self.LIGHT

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(4, 4)

    def update(self, snake: "Snake", map: "Map"):
        self.oil -= map.game.dt.total_seconds() * map.game.difficulty.helpful
        if self.oil <= 0:
            self.alive = False
            return
        for ent in map.entities:
            if (
                ent.alive
                and isinstance(ent, Hunter)
                and ent.asleep
                and (ent.center - self.center).length() < self.light
            ):
                ent.asleep = False

    def draw(self, offset: "Vec2"):
        if self.oil < 5 and pyxel.frame_count % 8 < 3:  # flickers before it goes out
            self.img_x = 8 * self._img_x
        else:
            self.img_x = 8 * (self._img_x + 1)
        super().draw(offset)


TOOL_ENTITIES = {"tree": Tree, "lure": Lure, "lantern": Lantern}


@register("crow")
class Crow(Entity):
    """The Crow (level 40), moved by its boss (bosses.CrowBoss): it flies over everything, and only on the ground
    (perched on an apple or a hedge, or stunned after crashing into a hedge) can the snake's head bite it, which costs
    it one of its health and sends it up again."""

    _img_x = 0
    _img_y = 27
    tally = False
    PERCHED_IMG_X = 2
    STUNNED_IMG_X = 4
    GRACE = 1.0  # seconds after a bite before the next one counts
    FLASH = 0.3
    COL_SHADOW, COL_LINE = 1, 8

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.h = 16
        self.state = "fly"  # fly, hover, perch, warn, dive, stunned
        self.grace = 0.0
        self.flash = 0.0
        self.bitten = False  # set on a bite, for the boss to send it up
        self.line: tuple[Vec2, Vec2] | None = None  # a swoop's way while it warns and dives

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(8, 8)

    @property
    def grounded(self) -> bool:
        """Whether it is on the ground (perched or stunned): only then can the snake bite it."""
        return self.state in ("perch", "stunned")

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        self.grace = max(self.grace - seconds, 0.0)
        self.flash = max(self.flash - seconds, 0.0)

    def on_intersect(self, snake: "Snake", map: "Map"):
        if not self.grounded or self.grace > 0:
            return
        self.health -= 1
        self.grace, self.flash, self.bitten = self.GRACE, self.FLASH, True
        map.game.sm.effect("caw")
        if self.health <= 0:
            self.alive, self.killed = False, True

    def draw(self, offset: "Vec2"):
        if self.line is not None and self.state == "warn" and pyxel.frame_count % 6 < 4:  # where it will strike
            start, end = self.line
            steps = max(int((end - start).length() // 6), 1)
            for i in range(steps + 1):
                point = start + (end - start) * (i / steps) + offset
                pyxel.pset(point.x, point.y, self.COL_LINE)
            pyxel.circb(end.x + offset.x, end.y + offset.y, 5, self.COL_LINE)
        if not self.grounded:  # its shadow on the ground
            center = self.center + offset
            pyxel.dither(0.5)
            pyxel.elli(center.x - 6, center.y + 6, 12, 5, self.COL_SHADOW)
            pyxel.dither(1.0)
        if self.flash > 0 and pyxel.frame_count % 2:
            return
        self.img_x = 8 * {"perch": self.PERCHED_IMG_X, "stunned": self.STUNNED_IMG_X}.get(self.state, self._img_x)
        super().draw(offset if self.grounded else offset + Vec2(0, -4))


@register("jackdaw")
class Jackdaw(Hunter):
    """One of the Crow's flock: a hunter that flaps after the tail (or a lure) and pecks it (met head first too, like
    any hunter in the Keeper's garden)."""

    _img_x = 6
    _img_y = 27
    ASLEEP_IMG_X = 7
    SPEED = 1.35
    CHUNK = 4
    DETOUR_CHANCE = 0.3
    HUNT = (3.0, 5.0)

    def draw(self, offset: "Vec2"):
        if self.penned > self.PENNED / 2 and pyxel.frame_count % 4 < 2:
            return
        self.img_x = 8 * (self._img_x + (pyxel.frame_count // 4) % 2)
        Entity.draw(self, offset)


class Hand:
    """The player's hand in a Keeper level: what is left of each tool (`left`), what it planted (`planted` hedges,
    `sprouts` still growing, `placed` entities), the cursor (a tile) and the chosen tool. `player` acts on it every
    frame: a HandInput, a HandBot, or None (nobody keeps the garden)."""

    def __init__(self, map: "Map"):
        self.map = map
        cfg = map.cfg.hand
        self.tools = [tool for tool in TOOLS if tool in cfg]
        if not self.tools or any(tool not in TOOLS for tool in cfg):
            raise ValueError(f"{map.level.name}: hand needs tools out of {TOOLS}, got {list(cfg)}")
        self.left = {tool: cfg[tool] for tool in self.tools}  # scaled by difficulty.apply
        self.tool = self.tools[0]
        self.width, self.height = map.cfg.width // 8, map.cfg.height // 8
        self.cursor = (self.width // 2, self.height // 2)
        self.sprouts: dict[tuple[int, int], float] = {}  # tile -> seconds of sprouting left
        self.planted: set[tuple[int, int]] = set()
        self.placed: list[Entity] = []
        self.cooldown = 0.0
        self.player = None
        self.offset = Vec2(0, 0)  # the camera's, for the mouse

    # ---- rules --------------------------------------------------------------------------------------------------

    def free(self, tile: tuple[int, int], snake: "Snake", clear: float = CLEAR) -> bool:
        """Whether something can go on `tile`: plain floor inside the level, no sprout, entity or segment on it, and
        not within `clear` px of the head."""
        x, y = tile
        if not (0 <= x < self.width and 0 <= y < self.height) or tile in self.sprouts:
            return False
        if pyxel.tilemaps[self.map.tm].pget(x, y) not in FLOOR_TILES:
            return False
        left, top = x * 8, y * 8 + self.map.header
        for ent in self.map.entities:
            overlaps = (
                ent.pos.x < left + 8 and left < ent.pos.x + ent.w and ent.pos.y < top + 8 and top < ent.pos.y + ent.h
            )
            if ent.alive and overlaps:
                return False
        center = Vec2(left + 4, top + 4)
        margin = 4 + snake.size
        if any(abs(seg.pos.x - center.x) < margin and abs(seg.pos.y - center.y) < margin for seg in snake.segs):
            return False
        return (snake.head.pos - center).length() >= clear

    def tiles_of(self, tool: str, tile: tuple[int, int]) -> list[tuple[int, int]]:
        """The tiles a tool takes when put on `tile`: a tree four (`tile` its top left), the others one."""
        x, y = tile
        return [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)] if tool == "tree" else [tile]

    def can_place(self, tool: str, tile: tuple[int, int], snake: "Snake") -> bool:
        """Whether `tool` can go on `tile` now: some left, and every tile it takes free (plain floor, nothing on it,
        away from the head)."""
        if self.left.get(tool, 0) <= 0:
            return False
        clear = CLEAR + 4 if tool == "tree" else CLEAR
        return all(self.free(t, snake, clear) for t in self.tiles_of(tool, tile))

    def place(self, tool: str, tile: tuple[int, int], snake: "Snake") -> bool:
        """Put `tool` on `tile` if the rules allow it and the budget has one; False otherwise."""
        if self.cooldown > 0 or not self.can_place(tool, tile, snake):
            return False
        if tool == "hedge":
            self.sprouts[tile] = SPROUT
        else:
            ent = TOOL_ENTITIES[tool].at_pos(Vec2(tile[0] * 8, tile[1] * 8 + self.map.header))
            self.placed.append(ent)
            self.map.entities.append(ent)
        self.left[tool] -= 1
        self.cooldown = COOLDOWN
        self.map.game.sm.effect("plant")
        return True

    def liftable(self, tile: tuple[int, int]) -> Entity | tuple[int, int] | None:
        """What the hand could take back at `tile`: a planted hedge or sprout (the tile), or an entity it placed."""
        if tile in self.sprouts or tile in self.planted:
            return tile
        center = Vec2(tile[0] * 8 + 4, tile[1] * 8 + 4 + self.map.header)
        return next((ent for ent in self.placed if ent.alive and ent.covers(center)), None)

    def lift(self, tile: tuple[int, int], snake: "Snake | None" = None) -> bool:
        """Take back what the hand put on `tile` (the level's own walls and entities stay); its tool is refunded."""
        what = self.liftable(tile)
        if what is None:
            return False
        if isinstance(what, tuple):
            if what in self.sprouts:
                del self.sprouts[what]
            else:
                self.uproot(what)
            self.left["hedge"] += 1
        else:
            if isinstance(what, Tree):
                what.lifted()
            else:
                what.alive = False
            tool = next(name for name, cls in TOOL_ENTITIES.items() if isinstance(what, cls))
            self.left[tool] += 1
        self.map.game.sm.effect("lift")
        return True

    def uproot(self, tile: tuple[int, int]) -> None:
        """A planted hedge gone (lifted, or pulled up by the Crow): floor again, the walls around autotiled."""
        self.planted.discard(tile)
        self.map.dig(tile)

    def lure_for(self, hunter: Hunter) -> "Lure | None":
        """The lure a hunter goes for: the nearest within LURE_RANGE px of it, if any."""
        lures = [ent for ent in self.placed if ent.alive and isinstance(ent, Lure)]
        near = [lure for lure in lures if (lure.center - hunter.center).length() < LURE_RANGE]
        return min(near, key=lambda lure: (lure.center - hunter.center).length(), default=None)

    def unused(self) -> int:
        """Tools left in the budgets (worth THRIFT points each when the level is won)."""
        return sum(self.left.values())

    # ---- every frame --------------------------------------------------------------------------------------------

    def update(self, snake: "Snake") -> None:
        """One frame: cool down, grow sprouts into hedges once the snake has left them and is far enough away, and let
        the player act."""
        seconds = self.map.game.dt.total_seconds()
        self.cooldown = max(self.cooldown - seconds, 0.0)
        self.placed = [ent for ent in self.placed if ent.alive]
        for tile in list(self.sprouts):
            self.sprouts[tile] -= seconds
            if self.sprouts[tile] > 0:
                continue
            center = Vec2(tile[0] * 8 + 4, tile[1] * 8 + 4 + self.map.header)
            margin = 4 + snake.size
            if any(abs(seg.pos.x - center.x) < margin and abs(seg.pos.y - center.y) < margin for seg in snake.segs):
                continue  # grows once the snake has left it
            if (snake.head.pos - center).length() < GROW_CLEAR:
                continue
            if any(ent.alive and ent.covers(center) for ent in self.map.entities):
                continue
            del self.sprouts[tile]
            self.planted.add(tile)
            self.map.fill(tile, (0, WALL_VARIANT_ROW))  # autotiled with the walls around
        if self.player is not None:
            self.player.act(self, snake, self.map)

    def draw(self, offset: Vec2) -> None:
        """Sprouts and the flowers on planted hedges (under the entities' layer of the map)."""
        header = self.map.header
        for tile, left in self.sprouts.items():
            frame = SPROUT_TILES[0] if left > SPROUT / 2 else SPROUT_TILES[1]
            pyxel.blt(tile[0] * 8 + offset.x, tile[1] * 8 + header + offset.y, 0, frame[0] * 8, frame[1] * 8, 8, 8, 0)
        mx, my = PLANTED_MARK
        for x, y in self.planted:
            pyxel.blt(x * 8 + offset.x, y * 8 + header + offset.y, 0, mx * 8, my * 8, 8, 8, colkey=0)

    def draw_cursor(self, offset: Vec2, snake: "Snake") -> None:
        """The hand's cursor: the tile (four for a tree) outlined in green where the tool can go, in red where it
        can't, and the tool beside it."""
        if self.player is None:
            return
        x, y = self.cursor
        size = 16 if self.tool == "tree" else 8
        sx, sy = x * 8 + offset.x, y * 8 + self.map.header + offset.y
        ok = self.can_place(self.tool, self.cursor, snake) or self.liftable(self.cursor) is not None
        pyxel.rectb(sx - 1, sy - 1, size + 2, size + 2, COL_OK if ok else COL_NO)
        u, v = ICONS[self.tool]
        pyxel.blt(sx + size + 2, sy - 6, 0, u * 8, v * 8, 8, 8, colkey=0)


class HandInput:
    """The player's hand: the mouse (left click places, right click lifts, the wheel chooses the tool), or the cursor on
    the arrow keys / d-pad (space / A places, X / B lifts, Tab / shoulder buttons choose), keys 1-4 choose a tool, and a
    click on the toolbar in the footer too. A hedge can be drawn by holding the left button."""

    KEYS = ((pyxel.KEY_1, 0), (pyxel.KEY_2, 1), (pyxel.KEY_3, 2), (pyxel.KEY_4, 3))
    MOVES = (
        ((pyxel.KEY_LEFT, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT), (-1, 0)),
        ((pyxel.KEY_RIGHT, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT), (1, 0)),
        ((pyxel.KEY_UP, pyxel.GAMEPAD1_BUTTON_DPAD_UP), (0, -1)),
        ((pyxel.KEY_DOWN, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN), (0, 1)),
    )

    def __init__(self):
        self.mouse = (pyxel.mouse_x, pyxel.mouse_y)

    @staticmethod
    def pressed(*keys: int, hold: int = 0, repeat: int = 0) -> bool:
        """Whether any of `keys` was pressed this frame (`hold` / `repeat` as for pyxel.btnp)."""
        return any(pyxel.btnp(key, hold=hold, repeat=repeat) for key in keys)

    def act(self, hand: Hand, snake: "Snake", map: "Map") -> None:
        """Read the mouse, keyboard and gamepad: move the cursor, choose a tool, place or lift."""
        cfg = map.game.cfg
        top, footer = cfg.header.h, cfg.header.h + cfg.area.h
        mouse = (pyxel.mouse_x, pyxel.mouse_y)
        in_area = top <= mouse[1] < footer
        if mouse != self.mouse:  # the mouse moved: it takes the cursor over from the keys
            self.mouse = mouse
            if in_area:
                tile = map.tile_xy(Vec2(*mouse) - hand.offset)
                hand.cursor = (min(max(tile[0], 0), hand.width - 1), min(max(tile[1], 0), hand.height - 1))
        for keys, (dx, dy) in self.MOVES:
            if self.pressed(*keys, hold=8, repeat=2):
                x, y = hand.cursor
                hand.cursor = (min(max(x + dx, 0), hand.width - 1), min(max(y + dy, 0), hand.height - 1))
        # choosing the tool
        for key, index in self.KEYS:
            if pyxel.btnp(key) and index < len(hand.tools):
                hand.tool = hand.tools[index]
        step = 0
        if pyxel.mouse_wheel:
            step = -1 if pyxel.mouse_wheel > 0 else 1
        if self.pressed(pyxel.KEY_TAB, pyxel.GAMEPAD1_BUTTON_RIGHTSHOULDER):
            step = 1
        if self.pressed(pyxel.GAMEPAD1_BUTTON_LEFTSHOULDER):
            step = -1
        if step:
            hand.tool = hand.tools[(hand.tools.index(hand.tool) + step) % len(hand.tools)]
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and mouse[1] >= footer:  # the toolbar: the left half of the footer
            index = mouse[0] * len(hand.tools) // max(cfg.width // 2, 1)
            if index < len(hand.tools):
                hand.tool = hand.tools[index]
            return
        # placing and lifting
        held = hand.tool == "hedge" and pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
        if (
            in_area
            and (pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or held)
            or self.pressed(pyxel.KEY_SPACE, pyxel.GAMEPAD1_BUTTON_A)
        ):
            hand.place(hand.tool, hand.cursor, snake)
        if in_area and pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) or self.pressed(pyxel.KEY_X, pyxel.GAMEPAD1_BUTTON_B):
            hand.lift(hand.cursor, snake)


FOOD = (Apple, GoldenApple, Critter)


class PetController(PathController):
    """The Keeper's snake: a PathController with rules a player can read. It eats the nearest food it sees by walking
    distance (golden apples count as GOLDEN as far), and keeps its choice until another is SWITCH times as near. It
    doesn't know thorns. It keeps away only from awake hostile entities within SIGHT px. In the dark it sees only what
    some light falls on, and without food in sight walks to the nearest lantern (not back to the one it has just
    reached); else it wanders. It leaves food an awake hostile entity guards (within WARY px of what it keeps
    away from) while there is other. A boss within its reach that it can bite (the Crow on the ground) comes
    first."""

    THORNS = False
    SIGHT = 64  # px
    SWITCH = 2 / 3
    GOLDEN = 0.5
    BOSS_REACH = 40  # tiles of walking
    WARY = 12  # px
    VISIT = 12  # px: a lantern this close is reached
    WANDER = (8, 30)  # tiles away a wandering walk heads for
    WANDER_SECONDS = 6.0

    def __init__(self):
        super().__init__(self.choose)
        self.choice: Entity | None = None
        self.mood = "wander"  # eat, bite, run, light or wander: shown over its head
        self.visited: Entity | None = None  # the lantern it reached last
        self._wander: Vec2 | None = None
        self._wander_left = 0.0
        self.goal: Vec2 | None = None

    def threats(self, snake, map):
        """Awake hostile entities within SIGHT px (it walks past sleeping ones), and what the boss warns of."""
        head, threats = snake.head.pos, []
        for ent in map.entities:
            if not (ent.alive and ent.hostile and ent.avoid) or getattr(ent, "asleep", False):
                continue
            center = ent.pos + Vec2(ent.w / 2, ent.h / 2)
            if (center - head).length() < self.SIGHT:
                threats.append((center, self.THREAT + max(ent.w, ent.h) - 8))
        boss = getattr(map, "boss", None)
        danger = boss.danger() if boss is not None else None
        if isinstance(danger, list):
            threats += danger
        elif danger is not None:
            threats.append(danger)
        return threats

    def _wall(self, map, cell):
        """A sprouting hedge is a wall to the pet's way at once, before it has grown."""
        hand = map.hand
        if (
            hand is not None
            and hand.sprouts
            and map.tile_xy(Vec2(cell[0] * self.CELL, cell[1] * self.CELL)) in hand.sprouts
        ):
            return True
        return super()._wall(map, cell)

    def sees(self, ent: Entity, lights: list | None) -> bool:
        """Whether the pet can see `ent`: always in a lit level, else only inside one of `lights`."""
        if lights is None:
            return True
        center = ent.pos + Vec2(ent.w / 2, ent.h / 2)
        return any((center - pos).length() < radius for pos, radius in lights)

    def choose(self, snake: "Snake", map: "Map") -> Vec2:
        """The point the pet goes for now (also kept in `goal` for drawing)."""
        self.goal = self._choose(snake, map)
        return self.goal

    def _choose(self, snake: "Snake", map: "Map") -> Vec2:
        """What the pet goes for: a grounded boss in reach, else the food it sees that is nearest by walking distance
        (golden apples count further, guarded food last), else the nearest lantern in the dark, else a wander."""
        distance = map.flight(snake)
        boss = map.boss
        body = boss.target() if boss is not None else None
        if body is not None and distance.get(map.tile_xy(body), self.BOSS_REACH + 1) <= self.BOSS_REACH:
            self.mood = "bite"
            return body
        dark = map.darkness is not None and not map.game.cfg.debug
        lights = None  # in the dark: its own light and the lanterns' (the glow of food itself shows it nothing)
        if dark:
            lanterns = [(ent.center, ent.light) for ent in map.entities if ent.alive and isinstance(ent, Lantern)]
            lights = [(snake.head.pos, map.darkness.light), *lanterns]

        def cost(ent: Entity) -> float:
            steps = distance.get(map.tile_xy(ent.pos + Vec2(ent.w / 2, ent.h / 2)))
            if steps is None:
                return math.inf
            return steps * (self.GOLDEN if isinstance(ent, GoldenApple) else 1)

        foods = [ent for ent in map.entities if ent.alive and isinstance(ent, FOOD) and self.sees(ent, lights)]
        costs = {ent: cost(ent) for ent in foods}
        foods = [ent for ent in foods if costs[ent] < math.inf]
        # food a beetle it sees sits by is left alone while there is other (else it circles it until it bites itself)
        guarded = {
            ent
            for ent in foods
            for pos, radius in self._threats
            if (ent.pos + Vec2(ent.w / 2, ent.h / 2) - pos).length() < radius + self.WARY
        }
        foods = [ent for ent in foods if ent not in guarded] or foods
        running = bool(self._threats)
        if foods:
            best = min(foods, key=costs.get)
            if self.choice not in foods or costs[best] < costs[self.choice] * self.SWITCH:
                self.choice = best
            self.mood = "run" if running else "eat"
            return self.choice.pos + Vec2(self.choice.w / 2, self.choice.h / 2)
        self.choice = None
        if dark:
            lanterns = [
                ent for ent in map.entities if ent.alive and isinstance(ent, Lantern) and ent is not self.visited
            ]
            lanterns = [ent for ent in lanterns if map.tile_xy(ent.center) in distance]
            if lanterns:
                lantern = min(lanterns, key=lambda ent: distance[map.tile_xy(ent.center)])
                if (lantern.center - snake.head.pos).length() < self.VISIT:
                    self.visited = lantern
                self.mood = "run" if running else "light"
                return lantern.center
        self.mood = "run" if running else "wander"
        return self._wander_to(snake, map, distance)

    def _wander_to(self, snake: "Snake", map: "Map", distance: dict) -> Vec2:
        """A spot WANDER tiles away along the ways, chosen anew when reached or after WANDER_SECONDS."""
        self._wander_left -= map.game.dt.total_seconds()
        reached = self._wander is not None and (self._wander - snake.head.pos).length() < 12
        if self._wander is None or reached or self._wander_left <= 0:
            low, high = self.WANDER
            spots = [tile for tile, steps in distance.items() if low <= steps <= high and self._open(map, tile)]
            if spots:
                self._wander = map.tile_center(spots[pyxel.rndi(0, len(spots) - 1)])
            else:
                self._wander = snake.segs[-1].pos
            self._wander_left = self.WANDER_SECONDS
        return self._wander

    @staticmethod
    def _open(map: "Map", tile: tuple[int, int]) -> bool:
        """Whether the eight tiles around `tile` and `tile` itself are free of walls."""
        x, y = tile
        tilemap = pyxel.tilemaps[map.tm]
        return all(tilemap.pget(x + dx, y + dy) not in WALL_TILES for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    def intent(self, snake: "Snake") -> list[Vec2]:
        """Points along its way to the target (every second cell of its distance field, from the head on)."""
        x, y = self._cell(snake.head.pos)
        distance = self._distance
        # the head's own cell is the body's (not in the field): start from the best cell around it
        near = [(x + dx, y + dy) for dx in range(-2, 3) for dy in range(-2, 3) if (x + dx, y + dy) in distance]
        if not near:
            return []
        cell = min(near, key=distance.get)
        points = []
        for step in range(400):
            if step % 2 == 0:
                points.append(Vec2(cell[0] * self.CELL + self.CELL / 2, cell[1] * self.CELL + self.CELL / 2))
            x, y = cell
            nexts = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            best = min((n for n in nexts if n in distance), key=distance.get, default=None)
            if best is None or distance[best] >= distance[cell]:
                break
            cell = best
        return points

    def draw(self, snake: "Snake", offset: Vec2) -> None:
        """Its way as faint dots, a ring round the target and the mood over its head."""
        for point in self.intent(snake)[2:]:
            pyxel.pset(point.x + offset.x, point.y + offset.y, COL_INTENT)
        if self.goal is not None:
            pyxel.circb(self.goal.x + offset.x, self.goal.y + offset.y, 6, COL_TARGET)
        u, v = MOODS[self.mood]
        head = snake.head.pos + offset
        pyxel.blt(head.x - 4, head.y - 14, 0, u * 8, v * 8, 8, 8, colkey=0)


class HandBot:
    """Plays the hand in tests: the level's `keeper` plan, one action at a time and at most one every REACTION seconds
    (plus the cursor's way at CURSOR_SPEED px a second), and a few rules for what can't be planned: a lure in the way
    of a hunter near the snake, a hedge across the Crow's swoop. Plan steps:

        - hedge: [[x, y], ...]   (also tree, lure, lantern: tiles, a tree's top left)
        - lift: [[x, y], ...]
        - after: {seconds: s} | {length: n} | {score: n} | {phase: n}   (wait until)
        - reach: [x, y]          (wait until the head is at that tile, NEAR px)
    """

    REACTION = 0.35  # seconds between actions
    CURSOR_SPEED = 400  # px per second
    LURE_AT = 48  # px from the snake: a hunter this close gets a lure
    LURE_OFF = 40  # px past the hunter, away from the head
    GIVE_UP = 20.0  # seconds a step that can't be done is tried before it is skipped
    NEAR = 12  # px: the head this close to a `reach` step's tile has reached it

    def __init__(self, plan: list | None):
        self.steps: list[tuple[str, object]] = []
        for step in plan or []:
            ((kind, value),) = dict(step).items()
            if kind in TOOLS or kind == "lift":
                self.steps += [(kind, tuple(tile)) for tile in value]
            else:
                self.steps.append((kind, value))
        self.busy = 0.0
        self.trying = 0.0
        self.elapsed = 0.0
        self.score_at_start: int | None = None

    def act(self, hand: Hand, snake: "Snake", map: "Map") -> None:
        """At most one action per REACTION s (plus the cursor's travel): first what the moment needs (`react`), else the
        plan's next step."""
        seconds = map.game.dt.total_seconds()
        self.elapsed += seconds
        if self.score_at_start is None:
            self.score_at_start = map.game.score
        self.busy -= seconds
        if self.busy > 0:
            return
        action = self.react(hand, snake, map)
        if action is None:
            action = self.planned(hand, snake, map, seconds)
        if action is None:
            return
        kind, tile = action
        travel = math.dist(hand.cursor, tile) * 8 / self.CURSOR_SPEED
        hand.cursor = tile
        if kind == "lift":
            done = hand.lift(tile, snake)
        else:
            hand.tool = kind
            done = hand.place(kind, tile, snake)
        if done:
            self.busy = self.REACTION + travel

    def planned(self, hand: Hand, snake: "Snake", map: "Map", seconds: float) -> tuple[str, tuple] | None:
        """The plan's next action, once its `after` and `reach` conditions hold; None while waiting. A step that stays
        impossible for GIVE_UP s is skipped."""
        while self.steps:
            kind, value = self.steps[0]
            if kind == "after":
                if not self._after(value, snake, map):
                    return None
                self.steps.pop(0)
                continue
            if kind == "reach":
                if (map.tile_center(tuple(value)) - snake.head.pos).length() > self.NEAR:
                    return None
                self.steps.pop(0)
                continue
            possible = hand.liftable(value) is not None if kind == "lift" else hand.can_place(kind, value, snake)
            if possible:
                self.steps.pop(0)
                self.trying = 0.0
                return kind, value
            self.trying += seconds
            if self.trying < self.GIVE_UP:
                return None
            self.steps.pop(0)  # it won't come right: on with the plan
            self.trying = 0.0
        return None

    def _after(self, value, snake: "Snake", map: "Map") -> bool:
        """Whether the plan's `after` conditions all hold: seconds played, length, score made, the boss's phase."""
        checks = {
            "seconds": lambda n: self.elapsed >= n,
            "length": lambda n: len(snake) >= n,
            "score": lambda n: map.game.score - self.score_at_start >= n,
            "phase": lambda n: map.boss is not None and map.boss.phase >= n,
        }
        return all(checks[key](n) for key, n in dict(value).items())

    def react(self, hand: Hand, snake: "Snake", map: "Map") -> tuple[str, tuple] | None:
        """An action the moment asks for, or None: a hedge across the Crow's swoop line (lifting the oldest one when
        none are left), a lure for a hunter close to the snake."""
        boss = map.boss
        swoop = getattr(boss, "swoop_line", None)
        line = swoop() if swoop is not None else None
        if line is not None and "hedge" in hand.left:
            start, end = line
            if not any(self._on_line(tile, start, end, map) for tile in list(hand.sprouts) + list(hand.planted)):
                if hand.left["hedge"] <= 0:
                    oldest = next(iter(hand.planted), None)
                    return ("lift", oldest) if oldest is not None else None
                for share in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2):
                    tile = map.tile_xy(start + (end - start) * share)
                    if hand.can_place("hedge", tile, snake):
                        return "hedge", tile
        if hand.left.get("lure", 0) > 0:
            head, tail = snake.head.pos, snake.segs[-1].pos
            for ent in map.entities:
                if not (ent.alive and isinstance(ent, Hunter) and ent.state == "hunt") or hand.lure_for(ent):
                    continue
                if min((ent.center - head).length(), (ent.center - tail).length()) > self.LURE_AT:
                    continue
                away = ent.center - head
                if away.length() == 0:
                    continue
                spot = ent.center + away * (self.LURE_OFF / away.length())
                tile = self._near_free(hand, "lure", map.tile_xy(spot), snake)
                if tile is not None:
                    return "lure", tile
        return None

    @staticmethod
    def _on_line(tile: tuple[int, int], start: Vec2, end: Vec2, map: "Map") -> bool:
        """Whether `tile`'s centre lies within 6 px of the line from `start` to `end`."""
        center = map.tile_center(tile)
        line = end - start
        length = line.length()
        if length == 0:
            return False
        t = max(0.0, min(1.0, ((center.x - start.x) * line.x + (center.y - start.y) * line.y) / length**2))
        return (start + line * t - center).length() < 6

    @staticmethod
    def _near_free(hand: Hand, tool: str, tile: tuple[int, int], snake: "Snake") -> tuple[int, int] | None:
        """The tile nearest `tile` (in rings up to 3 tiles out) where `tool` can be placed, or None."""
        x, y = tile
        for reach in range(4):
            for dx in range(-reach, reach + 1):
                for dy in range(-reach, reach + 1):
                    if max(abs(dx), abs(dy)) == reach and hand.can_place(tool, (x + dx, y + dy), snake):
                        return x + dx, y + dy
        return None
