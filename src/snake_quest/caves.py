"""The entities of arc 4, The Caves (registered like those in entity.py, which imports this module at its end)."""

from typing import TYPE_CHECKING

import pyxel

from snake_quest.entity import Entity, Hunter, Nest, WeaponPickup, register
from snake_quest.tiles import FLOOR_TILES, WALL_TILES, WEB_TILE
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


@register("crystal")
class Crystal(Entity):
    """A glowing crystal of the caves: POINTS points and LENGTH segments, gone for good once eaten (`collect_all`)."""

    _img_x = 2
    _img_y = 15
    light = 20
    pullable = True
    POINTS = 3
    LENGTH = 2

    def on_intersect(self, snake: "Snake", map: "Map"):
        snake.grow += self.LENGTH
        map.game.score += self.POINTS
        map.game.sm.effect("golden")
        self.alive = False


@register("mushroom")
class Mushroom(Entity):
    """A glowing mushroom: only a light in the dark (eaten or shot it is not; bots ignore it)."""

    _img_x = 10
    _img_y = 15
    light = 16
    tally = False


@register("spider")
class Spider(Entity):
    """A cave spider. It crawls along the walls (from tile to tile on floor next to rock, keeping its way, at random
    where the ways fork) and every SPIN seconds (fewer on harder difficulties: `hostile` factor) spins a web on the
    tile it is on; at most WEBS of its own at a time, the oldest goes first. It doesn't hunt, but crawling into the
    snake's body it bites BITE segments off the tail (the end for a snake that short) and scuttles off, harmless for
    RETREAT seconds; running into it head first is the end, as with a beetle. One shot kills it."""

    _img_x = 0
    _img_y = 15
    hostile = True
    STEP_IMG_X = 1  # sprite tile next to it: legs the other way
    SPEED = 0.7  # px per frame, scaled with the difficulty's speed
    SPIN = 3.0  # seconds
    WEBS = 6
    BITE = 4
    REACH = 4  # px from its centre to a segment
    RETREAT = 2.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health = 1
        self.state = "crawl"  # crawl or retreat (bots: it is always moving)
        self.left = pyxel.rndf(1.0, self.SPIN)  # seconds until the next web
        self.retreat = 0.0
        self.webs: list[tuple[int, int]] = []
        self.heading: tuple[int, int] = (1, 0)
        self.goal: tuple[int, int] | None = None  # the tile it is crawling to

    def _ledge(self, map: "Map", tile: tuple[int, int]) -> bool:
        """Floor next to rock: where spiders crawl."""
        tilemap = pyxel.tilemaps[map.tm]
        x, y = tile
        if not (0 <= x < map.cfg.width // 8 and 0 <= y < map.cfg.height // 8) or tilemap.pget(x, y) in WALL_TILES:
            return False
        return any(tilemap.pget(x + dx, y + dy) in WALL_TILES for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    def _next(self, map: "Map", here: tuple[int, int]) -> tuple[int, int]:
        """The next tile along the wall: ahead if it can, else a turn (at random), else back."""
        x, y = here
        dx, dy = self.heading
        ways = [(dx, dy), (dy, dx), (-dy, -dx)]
        open_ways = [way for way in ways[1:] if self._ledge(map, (x + way[0], y + way[1]))]
        if self._ledge(map, (x + dx, y + dy)) and (not open_ways or pyxel.rndf(0, 1) < 0.7):
            way = (dx, dy)
        elif open_ways:
            way = open_ways[pyxel.rndi(0, len(open_ways) - 1)]
        elif self._ledge(map, (x - dx, y - dy)):
            way = (-dx, -dy)
        else:  # in the open (spawned there): head for the nearest wall
            way = (dx, dy) if map.tile_xy(self.center) != here else ways[pyxel.rndi(0, 2)]
            if pyxel.tilemaps[map.tm].pget(x + way[0], y + way[1]) in WALL_TILES:
                return here
        self.heading = way
        return x + way[0], y + way[1]

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        self.retreat = max(self.retreat - seconds, 0.0)
        self.state = "retreat" if self.retreat > 0 else "crawl"
        here = map.tile_xy(self.center)
        if self.goal is None or (map.tile_center(self.goal) - self.center).length() < 0.5:
            self.goal = self._next(map, here)
        direction = map.tile_center(self.goal) - self.center
        length = direction.length()
        if length > 0:
            speed = self.SPEED * map.game.difficulty.speed * (1.6 if self.retreat else 1.0)
            self.pos = self.pos + direction * (min(speed, length) / length)
        self.left -= seconds
        if self.left <= 0:
            self.left = self.SPIN * map.game.difficulty.hostile
            self.spin(map, here, snake)
        if not self.retreat and snake.segment_at(self.center, self.REACH) not in (None, 0):
            self.bite(snake, map)

    def spin(self, map: "Map", tile: tuple[int, int], snake: "Snake") -> None:
        """A web where it is (not under the snake), its oldest gone when it has WEBS."""
        under_snake = any(map.tile_xy(seg.pos) == tile for seg in snake.segs)
        if under_snake or pyxel.tilemaps[map.tm].pget(*tile) not in FLOOR_TILES:
            return
        if map.spin_web(tile):
            self.webs.append(tile)
            if len(self.webs) > self.WEBS:
                map.clear_web(self.webs.pop(0))

    def bite(self, snake: "Snake", map: "Map") -> None:
        """Bite the body: BITE segments off the tail (the end when the snake is too short), then retreat for RETREAT
        s."""
        map.game.sm.effect("hurt")
        self.retreat, self.state = self.RETREAT, "retreat"
        if not snake.cut(self.BITE):
            map.snake_killed = True

    def on_intersect(self, snake: "Snake", map: "Map"):
        """The snake runs into it head first."""
        if self.retreat <= 0:
            map.snake_killed = True

    def draw(self, offset: "Vec2"):
        if self.retreat > 0 and pyxel.frame_count % 6 < 3:  # blinks while scuttling off
            return
        moving = pyxel.frame_count // 4 % 2
        self.img_x = 8 * (self.STEP_IMG_X if moving else self._img_x)
        super().draw(offset)


@register("mole")
class Mole(Entity):
    """A mole of the caves. Underground (a mound of earth moving along) it heads for a random spot about REACH tiles
    away, through floor and rock alike, and digs away the rock it passes, a tunnel five tiles wide (`map.dig`: the
    tunnels stay, and hunters use them), at most DIG_LIMIT tiles in its life; shots fly over it, and the snake passes
    over it. Every SURFACE seconds, if it is on floor away from the snake, it comes up for UP seconds (fewer on harder
    difficulties: `hostile` factor): then one shot kills it, and running into it costs BITE segments (it dives at
    once)."""

    _img_x = 3  # the mound; the mole itself is the sprite tile next to it
    _img_y = 15
    hostile = True
    UP_IMG_X = 4
    SPEED = 0.8  # px per frame underground, scaled with the difficulty's speed
    REACH = (5, 14)  # tiles to the next spot
    SURFACE = (4.0, 6.0)  # seconds underground
    UP = 1.5  # seconds above
    DIG_LIMIT = 300  # tiles
    SPADE = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if dx * dx + dy * dy <= 5]  # dug around it
    BITE = 4
    CLEAR = 24  # px from the snake's head it keeps when coming up
    DUST = (4, 9, 15)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health = 1
        self.state = "under"  # under or up (bots: it is always moving)
        self.left = pyxel.rndf(*self.SURFACE)
        self.goal: Vec2 | None = None
        self.dug = 0

    @property
    def exposed(self) -> bool:
        """Only while it is up can it be shot or aimed at."""
        return self.state == "up"

    @property
    def avoid(self) -> bool:
        """Bots steer around it only while it is up."""
        return self.state == "up"

    def covers(self, point: "Vec2") -> bool:
        return self.state == "up" and super().covers(point)

    def _new_goal(self, map: "Map") -> Vec2:
        """A spot REACH tiles away inside the level (not on its border)."""
        width, height = map.cfg.width // 8, map.cfg.height // 8
        x, y = map.tile_xy(self.center)
        angle, reach = pyxel.rndf(0, 360), pyxel.rndf(*self.REACH)
        tx = min(max(round(x + pyxel.cos(angle) * reach), 1), width - 2)
        ty = min(max(round(y + pyxel.sin(angle) * reach), 1), height - 2)
        return map.tile_center((tx, ty))

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        self.left -= seconds
        if self.state == "up":
            if self.left <= 0:
                self.dive(map)
            return
        if self.goal is None or (self.goal - self.center).length() < 1:
            self.goal = self._new_goal(map)
        direction = self.goal - self.center
        length = direction.length()
        if length > 0:
            speed = self.SPEED * map.game.difficulty.speed
            self.pos = self.pos + direction * (min(speed, length) / length)
        x, y = map.tile_xy(self.center)
        if self.dug < self.DIG_LIMIT:  # a tunnel five tiles wide: room for the snake to turn round in
            self.dug += sum(map.dig((x + dx, y + dy)) for dx, dy in self.SPADE)
        if self.left <= 0:
            on_floor = not map.check_on_wall(self.center)
            if on_floor and (snake.head.pos - self.center).length() > self.CLEAR and not snake.covers(self.center):
                self.state, self.left = "up", self.UP * map.game.difficulty.hostile**0.5  # harder: a shorter chance
            else:
                self.left = 0.5  # try again in a moment

    def dive(self, map: "Map") -> None:
        """Go underground again until it next surfaces."""
        self.state, self.left = "under", pyxel.rndf(*self.SURFACE)

    def on_intersect(self, snake: "Snake", map: "Map"):
        if self.state != "up":
            return
        map.game.sm.effect("hurt")
        self.dive(map)
        if not snake.cut(self.BITE):
            map.snake_killed = True

    def draw(self, offset: "Vec2"):
        if self.state == "up":
            self.img_x = 8 * self.UP_IMG_X
            super().draw(offset)
            return
        self.img_x = 8 * self._img_x
        super().draw(offset)
        if pyxel.frame_count % 3 == 0:  # dust thrown up while it digs
            x = self.pos.x + offset.x + pyxel.rndi(0, 7)
            y = self.pos.y + offset.y + pyxel.rndi(0, 3)
            pyxel.pset(x, y, self.DUST[pyxel.rndi(0, 2)])


class Burning(Entity):
    """A flare burning on the ground (the Flare weapon's shot, come to rest): a light of LIGHT px for BURN seconds that
    scares bats away (see Bat). It burns webs it lies on. Not in level files: shots make it."""

    _img_x = 7  # the flare pickup's sprite, drawn as a flame instead
    _img_y = 15
    light = 48
    tally = False
    BURN = 6.0  # seconds
    COLS = (10, 9, 8)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.left = self.BURN

    def update(self, snake: "Snake", map: "Map"):
        self.left -= map.game.dt.total_seconds()
        if self.left <= 0:
            self.alive = False
        tile = map.tile_xy(self.center)
        if map.web and pyxel.tilemaps[map.tm].pget(*tile) == WEB_TILE:
            map.tear_web(tile)
        for ent in map.entities:  # egg sacs it lies against burn
            if ent.alive and isinstance(ent, EggSac) and (ent.pos + Vec2(4, 4) - self.center).length() < 10:
                ent.hit(ent.health)

    def draw(self, offset: "Vec2"):
        centre = self.center + offset
        flicker = pyxel.frame_count % 3
        fade = min(1.0, self.left / 1.5)  # it dies down at the end
        for col, radius in zip(self.COLS, (1 + flicker, 2.5, 3.5), strict=True):
            pyxel.circ(centre.x, centre.y - (col == 10), radius * fade, col)


@register("flare")
class FlarePickup(WeaponPickup):
    """Flares: slow shots that come to rest as a burning light and burn webs and egg sacs."""

    _img_x = 7
    _img_y = 15
    AMMO = 4
    WEAPON = "Flare"


@register("bat")
class Bat(Entity):
    """A bat of the deep caves. It hangs asleep from the ceiling until any light falls on it (the snake's, a crystal's,
    a flare's: see `Darkness.lights`), then flutters at the snake's head, faster than the snake and never straight.
    Touching any part of the snake it bites BITE segments off the tail (the end for a snake that short) and flies off
    for RETREAT seconds. It flees from a burning flare within SCARE px, and after ROOST seconds in the dark it goes back
    to its roost to sleep. One shot kills it; it doesn't keep bots from their way (`avoid`)."""

    _img_x = 5  # hanging; flying is the sprite tile next to it
    _img_y = 15
    hostile = True
    avoid = False  # like drones: a bite costs less than swerving around a flock
    FLY_IMG_X = 6
    SPEED = 1.6  # px per frame, scaled with the difficulty's speed
    JITTER = 40  # degrees it may veer off per frame
    TURN = 12  # degrees per frame towards where it is going
    BITE = 2
    REACH = 3  # px from its centre to a segment's edge
    RETREAT = 2.0
    SCARE = 48  # px
    ROOST = 4.0  # seconds

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health = 1
        self.state = "asleep"  # asleep, fly, retreat or roost
        self.roost = Vec2(self.pos.x, self.pos.y)
        self.heading = pyxel.rndf(0, 360)
        self.dark = 0.0  # seconds without light
        self.left = 0.0

    @property
    def asleep(self) -> bool:
        """Whether it hangs asleep at its roost."""
        return self.state == "asleep"

    def lit(self, snake: "Snake", map: "Map") -> bool:
        """Whether any light falls on it: the head's or a glowing entity's."""
        lights = [(snake.head.pos, map.darkness.light if map.darkness else 56)]
        lights += [(ent.pos + Vec2(ent.w / 2, ent.h / 2), ent.light) for ent in map.entities if ent.alive and ent.light]
        return any((pos - self.center).length() < radius for pos, radius in lights)

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        if self.state == "asleep":
            if self.lit(snake, map):
                self.state = "fly"
            return
        self.left -= seconds
        self.dark = 0.0 if self.lit(snake, map) else self.dark + seconds
        flares = [ent for ent in map.entities if ent.alive and isinstance(ent, Burning)]
        scare = next((f for f in flares if (f.center - self.center).length() < self.SCARE), None)
        if self.state == "retreat" and self.left <= 0:
            self.state = "fly"
        if self.state == "fly" and self.dark >= self.ROOST:
            self.state = "roost"
        if scare is not None:
            goal = self.center + (self.center - scare.center)
        elif self.state == "retreat":
            goal = self.center + (self.center - snake.head.pos)
        elif self.state == "roost":
            if (self.roost - self.pos).length() < 2:
                self.pos, self.state = Vec2(self.roost.x, self.roost.y), "asleep"
                return
            goal = self.roost + Vec2(4, 4)
            if self.lit(snake, map):
                self.state = "fly"
        else:
            goal = snake.head.pos
        self._fly(map, goal)
        if self.state == "fly" and snake.segment_at(self.center, self.REACH) is not None:
            self.bite(snake, map)

    def _fly(self, map: "Map", goal: Vec2) -> None:
        """Flutter towards `goal`: turn at most TURN degrees with some jitter, and turn round at rock."""
        to_goal = goal - self.center
        turn = (pyxel.atan2(to_goal.y, to_goal.x) - self.heading + 180) % 360 - 180
        self.heading += max(-self.TURN, min(self.TURN, turn)) + pyxel.rndf(-self.JITTER, self.JITTER) / 4
        speed = self.SPEED * map.game.difficulty.speed
        step = Vec2(pyxel.cos(self.heading), pyxel.sin(self.heading)) * speed
        if map.check_on_wall(self.center + step * 3):  # bounce off the rock
            self.heading += 180 + pyxel.rndf(-60, 60)
            return
        self.pos = self.pos + step

    def bite(self, snake: "Snake", map: "Map") -> None:
        """Bite the body: BITE segments off the tail (the end when the snake is too short), then flutter off for RETREAT
        s."""
        map.game.sm.effect("hurt")
        self.state, self.left = "retreat", self.RETREAT
        if not snake.cut(self.BITE):
            map.snake_killed = True

    def on_intersect(self, snake: "Snake", map: "Map"):
        if self.state == "fly":
            self.bite(snake, map)

    def draw(self, offset: "Vec2"):
        flying = self.state != "asleep"
        flap = pyxel.frame_count // 2 % 2
        self.img_x = 8 * (self.FLY_IMG_X if flying and flap else self._img_x)
        super().draw(offset)


@register("spiderling")
class Spiderling(Hunter):
    """A young spider of the Brood Mother's: it hunts the snake's tail at once, without the beetles' breaks, a little
    slower than the snake, and bites smaller chunks. One shot kills it."""

    _img_x = 8
    _img_y = 15
    ASLEEP_IMG_X = 8  # always awake
    SPEED = 1.2
    HUNT = (30.0, 60.0)
    PAUSE = (0.5, 1.0)
    DETOUR_CHANCE = 0.0
    CHUNK = 3

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.asleep = False


@register("eggsac")
class EggSac(Nest):
    """An egg sac of the Brood Mother's: like a nest it sends out spiderlings while the snake is near, glowing faintly.
    Shots or a burning flare destroy it (each one hurts the Brood Mother, see BroodMotherBoss)."""

    _img_x = 9
    _img_y = 15
    light = 10
    BROOD_CLS = Spiderling
    HEALTH = 2
    SPAWN = 7.0
    BROOD = 2
    ALERT = 120


@register("brood")
class BroodMother(Entity):
    """The Brood Mother (level 20, put in and steered by the `brood` boss): a 16x16 spider. In her lair (`hang`) she
    hangs high above the floor, and up on the ceiling (`ceiling`) only her eyes show: nothing reaches her there (shots
    fly underneath). Dropping (`shadow`), her shadow grows where she will land; landed (`rest`) she lies stunned, and
    shots hurt her; dazed, she can't bite."""

    _img_x = 12  # 2x2 sprite tiles from here
    _img_y = 15
    hostile = True
    tally = False  # her health is the boss's business
    FLASH = 0.15
    COL_SHADOW, COL_EYES = 1, 8

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.h = 16
        self.health = 12
        self.state = "hang"  # hang, ceiling, shadow or rest (stunned: bots aim at her from behind too)
        self.flash = 0.0
        self.shadow = 0.0  # 0..1: how far the drop has come

    @property
    def exposed(self) -> bool:
        """Shots hurt her only while she lies dazed after a landing."""
        return self.state == "rest"

    avoid = False  # out of reach above, harmless when down: bots may turn to face her

    def covers(self, point: "Vec2") -> bool:
        return self.exposed and super().covers(point)

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        self.flash = max(self.flash - seconds, 0.0)

    def hit(self, dmg: int):
        if self.state == "rest":
            super().hit(dmg)
            self.flash = self.FLASH

    def draw(self, offset: "Vec2"):
        centre = self.center + offset
        if self.state == "ceiling":  # only her eyes, high up in the dark
            if pyxel.frame_count % 40 < 36:
                pyxel.pset(centre.x - 2, centre.y, self.COL_EYES)
                pyxel.pset(centre.x + 2, centre.y, self.COL_EYES)
            return
        if self.state == "shadow":
            pyxel.dither(0.5)
            pyxel.circ(centre.x, centre.y, 3 + 7 * self.shadow, self.COL_SHADOW)
            pyxel.dither(1.0)
            pyxel.circb(centre.x, centre.y, 3 + 7 * self.shadow, self.COL_EYES if pyxel.frame_count % 4 < 2 else 0)
            return
        if not (self.flash > 0 and pyxel.frame_count % 2):
            super().draw(offset)
        if self.state == "rest" and pyxel.frame_count % 8 < 4:  # dazed: stars
            pyxel.pset(centre.x - 6, centre.y - 9, 10)
            pyxel.pset(centre.x + 6, centre.y - 9, 10)
