import datetime
from typing import TYPE_CHECKING

import pyxel

from snake_quest.utils import Vec2
from snake_quest.widget import WIDGET_MARGIN, Widget

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


# registry by name (used in level files: timers, goals), filled by @register
ENTITY_NAMES: dict[str, type["Entity"]] = {}
# entity class for each sprite tile (8px-tile coordinates in image bank 0), so tilemaps can place entities
ENTITY_TILES: dict[tuple[int, int], type["Entity"]] = {}


def register(name: str):
    """Class decorator making an entity available to level files by `name` and to tilemaps by its sprite tile."""

    def decorator(cls: type["Entity"]) -> type["Entity"]:
        tile = (cls._img_x, cls._img_y)
        if name in ENTITY_NAMES or tile in ENTITY_TILES:
            raise ValueError(f"entity {name!r} or its sprite tile {tile} is registered twice")
        ENTITY_NAMES[name] = cls
        cls.name = name
        ENTITY_TILES[tile] = cls
        return cls

    return decorator


class Entity:
    name = "entity"  # set by @register
    light = 0  # radius in px it lights up in dark levels (see darkness.py)
    hostile = False  # bad for the snake: harder difficulties spawn it more often (see difficulty.py)
    avoid = True  # bots steer around it when hostile (not around drones: a sting costs less than swerving)
    _img_x = None
    _img_y = None

    def __init__(self, pos: "Vec2", img_x: int, img_y: int, img_b: int = 0, w: int = 8, h: int = 8):
        self.pos: Vec2 = pos
        self.img_b: int = img_b
        self.img_x: int = img_x
        self.img_y: int = img_y
        self.w = w
        self.h = h
        self.alive = True
        self.killed = False  # dead by damage, as opposed to eaten
        self.health = float("inf")

    def draw(self, offset: "Vec2"):
        if self.alive:
            pyxel.blt(
                x=self.pos.x + offset.x,
                y=self.pos.y + offset.y,
                img=self.img_b,
                u=self.img_x,
                v=self.img_y,
                w=self.w,
                h=self.h,
                colkey=0,
            )

    def update(self, snake: "Snake", map: "Map"):
        pass

    def on_intersect(self, snake: "Snake", map: "Map"):
        pass

    def covers(self, point: "Vec2") -> bool:
        return self.pos.x <= point.x <= self.pos.x + self.w and self.pos.y <= point.y <= self.pos.y + self.h

    @classmethod
    def at_pos(cls, pos: "Vec2"):
        return cls(pos=pos, img_x=8 * cls._img_x, img_y=8 * cls._img_y)

    def hit(self, dmg: int):
        self.health -= dmg
        if self.health <= 0:
            self.alive = False
            self.killed = True


@register("apple")
class Apple(Entity):
    _img_x = 2
    _img_y = 0
    light = 10

    def on_intersect(self, snake: "Snake", map: "Map"):
        # update stats
        snake.grow += 5
        map.game.score += 1
        map.game.sm.effect("eat")
        # generate next apple
        new_pos: Vec2 = map.new_pos(snake=snake)
        map.entities.append(Apple.at_pos(new_pos))
        # destroy self
        self.alive = False


@register("golden")
class GoldenApple(Entity):
    _img_x = 2
    _img_y = 1
    light = 14

    def on_intersect(self, snake: "Snake", map: "Map"):
        # update stats
        snake.grow += 20
        map.game.score += 5
        map.game.sm.effect("golden")
        # destroy self
        self.alive = False


@register("speed")
class SpeedApple(Entity):
    """No length, but a temporary speed boost. A second one restarts the boost instead of stacking it."""

    _img_x = 4
    _img_y = 0
    light = 8
    BOOST = 1.5  # speed factor
    SECONDS = 5.0

    def on_intersect(self, snake: "Snake", map: "Map"):
        snake.boost(self.BOOST, self.SECONDS)
        map.game.score += 1
        map.game.sm.effect("speed")
        self.alive = False


@register("firefly")
class Firefly(Entity):
    """Lights the breadcrumbs: the level's hidden path appears tile by tile, starting where the snake is."""

    _img_x = 5
    _img_y = 0
    light = 20
    NOTICE = 48  # px: closer than this, the firefly drifts towards the snake's head
    SPEED = 1.5  # px per frame
    LIGHT_SECONDS = 20.0  # how long the breadcrumbs shine before fading out

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phase = pyxel.rndf(0, 360)  # so fireflies don't hover in sync

    def draw(self, offset: "Vec2"):
        """Hover gently up and down (drawing only: the position used for catching stays put)."""
        bob = Vec2(0, round(pyxel.sin(pyxel.frame_count * 6 + self.phase) * 2))
        super().draw(offset + bob)

    def update(self, snake: "Snake", map: "Map"):
        """Fly towards a snake passing nearby, so crossing its corridor is enough to catch it."""
        to_head = snake.head.pos - (self.pos + Vec2(self.w / 2, self.h / 2))
        distance = to_head.length()
        if 0 < distance < self.NOTICE:
            self.pos = self.pos + to_head * (min(self.SPEED, distance) / distance)

    def on_intersect(self, snake: "Snake", map: "Map"):
        map.reveal_path(origin=snake.head.pos, seconds=self.LIGHT_SECONDS)
        map.game.sm.effect("firefly")
        self.alive = False


class WeaponPickup(Entity):
    """A weapon lying around: the snake picks it up with AMMO shots, or AMMO more for the same kind of weapon it
    carries. The snake carries one weapon, so another kind is dropped for it."""

    light = 10
    AMMO = 12
    WEAPON = "Gun"  # class name in weapons.py

    def on_intersect(self, snake: "Snake", map: "Map"):
        from snake_quest import weapons  # weapons need nothing from here, but keep entities importable first

        weapon_cls = getattr(weapons, self.WEAPON)
        if type(snake.weapon) is weapon_cls:
            snake.weapon.ammo += self.AMMO
        else:
            snake.weapon = weapon_cls(ammo=self.AMMO)
        map.game.sm.effect("pickup")
        self.alive = False


@register("gun")
class GunPickup(WeaponPickup):
    _img_x = 2
    _img_y = 11


@register("spread")
class SpreadPickup(WeaponPickup):
    _img_x = 2
    _img_y = 13
    AMMO = 12
    WEAPON = "Spread"


@register("ricochet")
class RicochetPickup(WeaponPickup):
    _img_x = 3
    _img_y = 13
    WEAPON = "Ricochet"


@register("critter")
class Critter(Entity):
    """Golden prey of The Wilds. It grazes until the snake's head comes within FLEE px, then runs away from it along the
    paths (to the neighbouring tile farthest from the head, `map.flight`), a little slower than the snake. After a
    random RUN it has to catch its breath for a while; on harder difficulties it runs longer and rests less.
    Eaten: LENGTH more segments, POINTS points."""

    _img_x = 3
    _img_y = 11
    light = 8
    FLEE = 64  # px
    SPEED = 1.1  # px per frame (the snake starts at 1.3), scaled with the difficulty's speed
    RUN = (2.0, 3.5)  # seconds it can run (times the difficulty's `helpful` factor: longer when harder)
    BREATH = (1.0, 2.5)  # seconds it then stands still (divided by that factor)
    LENGTH = 3
    POINTS = 2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = "graze"  # graze, run or breath
        self.left = 0.0

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    def update(self, snake: "Snake", map: "Map"):
        self.left -= map.game.dt.total_seconds()
        near = (snake.head.pos - self.center).length() < self.FLEE
        if self.state == "graze" and near:
            self.state, self.left = "run", pyxel.rndf(*self.RUN) * map.game.difficulty.helpful
        elif self.state == "run" and self.left <= 0:
            self.state, self.left = "breath", pyxel.rndf(*self.BREATH) / map.game.difficulty.helpful
        elif self.state == "breath" and self.left <= 0:
            self.state = "graze"
        if self.state != "run":
            return
        distance = map.flight(snake)
        x, y = here = map.tile_xy(self.center)
        if here not in distance:
            return
        steps = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy)]
        steps = [s for s in steps if s in distance and (s[0], y) in distance and (x, s[1]) in distance]
        best = max(steps, key=distance.get, default=here)
        if distance.get(best, 0) <= distance[here]:  # cornered
            return
        direction = map.tile_center(best) - self.center
        length = direction.length()
        if length > 0:
            speed = self.SPEED * map.game.difficulty.speed
            self.pos = self.pos + direction * (min(speed, length) / length)

    def on_intersect(self, snake: "Snake", map: "Map"):
        snake.grow += self.LENGTH
        map.game.score += self.POINTS
        map.game.sm.effect("golden")
        self.alive = False


@register("hunter")
class Hunter(Entity):
    """A beetle of The Wilds. It sleeps until the snake comes within WAKE px or its nap is over. Then it hunts the tail,
    faster than the snake: it follows the shortest way through the level to the snake's last segment (`map.chase`).
    After a random HUNT time it either rests (eyes closed, a chance to get away or turn and shoot) or takes a detour to
    a nearby spot, then hunts again. A bite on the body takes CHUNK segments off the tail and makes it retreat; a bite
    the snake is too short for, or running into an awake beetle head first, is the end. Rest and detour times scale
    with the difficulty's `hostile` factor, speeds with its `speed`. Portals don't carry it."""

    _img_x = 0
    _img_y = 11
    hostile = True
    ASLEEP_IMG_X = 1  # sprite tile next to it: eyes closed (asleep and resting)
    WAKE = 56  # px
    NAP = (4.0, 12.0)  # seconds asleep at most, chosen at random
    SPEED = 1.4  # px per frame while hunting (the snake starts at 1.3)
    DETOUR_SPEED = 0.8  # px per frame on a detour
    HUNT = (2.0, 4.0)  # seconds of hunting before it rests or takes a detour
    PAUSE = (1.5, 2.5)  # seconds of rest
    DETOUR = (1.0, 3.0)  # seconds of detour at most
    DETOUR_CHANCE = 0.5  # of a break being a detour rather than a rest
    DETOUR_REACH = (3, 10)  # tiles away (along the way) a detour heads for
    BITE = 5  # px from its centre to a segment
    RETREAT = 2.5  # seconds it backs off after a bite
    CHUNK = 6  # segments a bite takes off the tail

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = "asleep"  # asleep, hunt, rest, detour or retreat
        self.left = pyxel.rndf(*self.NAP)  # seconds until the state ends
        self.health = 1  # one shot
        self._detour: dict[tuple[int, int], int] = {}  # walking distances to the detour's spot

    @property
    def asleep(self) -> bool:
        return self.state == "asleep"

    @asleep.setter
    def asleep(self, value: bool) -> None:
        self._begin("asleep", pyxel.rndf(*self.NAP)) if value else self._begin("hunt", pyxel.rndf(*self.HUNT))

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    def _begin(self, state: str, seconds: float) -> None:
        self.state, self.left = state, seconds

    def _break(self, map: "Map") -> None:
        """End of a hunt: a rest or a detour, shorter on harder difficulties."""
        factor = map.game.difficulty.hostile
        if pyxel.rndf(0, 1) < self.DETOUR_CHANCE:
            near = [
                tile
                for tile, steps in map.walking_distances(self.center).items()
                if self.DETOUR_REACH[0] <= steps <= self.DETOUR_REACH[1]
            ]
            if near:
                self._detour = map.walking_distances(map.tile_center(near[pyxel.rndi(0, len(near) - 1)]))
                self._begin("detour", pyxel.rndf(*self.DETOUR) * factor)
                return
        self._begin("rest", pyxel.rndf(*self.PAUSE) * factor)

    def update(self, snake: "Snake", map: "Map"):
        self.left -= map.game.dt.total_seconds()
        speed = map.game.difficulty.speed
        if self.state == "asleep":
            if self.left <= 0 or (snake.head.pos - self.center).length() < self.WAKE:
                self._begin("hunt", pyxel.rndf(*self.HUNT))
            return
        if self.left <= 0:
            if self.state == "hunt":
                self._break(map)
            else:
                self._begin("hunt", pyxel.rndf(*self.HUNT))
        if self.state == "rest":
            return
        if self.state == "retreat":
            self._move(self.center - snake.head.pos, self.DETOUR_SPEED * speed)
            return
        if self.state == "detour":
            self._move(self._next_step(self._detour, None, map) - self.center, self.DETOUR_SPEED * speed)
            return
        self._move(self._next_step(map.chase(snake), snake.segs[-1].pos, map) - self.center, self.SPEED * speed)
        if any((seg.pos - self.center).length() < self.BITE for seg in snake.segs[1:]):
            self.bite(snake, map)

    def _next_step(self, distance: dict[tuple[int, int], int], goal: Vec2 | None, map: "Map") -> Vec2:
        """Where to head for along `distance` (walking distances to where it is going): the centre of the neighbouring
        tile closest to it (diagonal only where both tiles beside the corner are free), or `goal` once in its tile."""
        x, y = here = map.tile_xy(self.center)
        if here not in distance or (goal is not None and here == map.tile_xy(goal)):
            return goal if goal is not None else self.center
        steps = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        steps += [
            (x + dx, y + dy) for dx in (-1, 1) for dy in (-1, 1) if (x + dx, y) in distance and (x, y + dy) in distance
        ]
        best = min((step for step in steps if step in distance), key=distance.get, default=here)
        if distance.get(best, 0) >= distance[here]:  # arrived (a detour's spot): stay
            return map.tile_center(here)
        return map.tile_center(best)

    def _move(self, direction: Vec2, speed: float) -> None:
        length = direction.length()
        if length > 0:
            self.pos = self.pos + direction * (min(speed, length) / length)

    def bite(self, snake: "Snake", map: "Map") -> None:
        """Take CHUNK segments off the tail; the end when the snake isn't longer than that."""
        map.game.sm.effect("hurt")
        self._begin("retreat", self.RETREAT)
        if not snake.cut(self.CHUNK):
            map.snake_killed = True

    def on_intersect(self, snake: "Snake", map: "Map"):
        """The snake runs into it head first."""
        if not self.asleep:
            map.snake_killed = True

    def draw(self, offset: "Vec2"):
        closed = self.state in ("asleep", "rest")
        self.img_x = 8 * (self.ASLEEP_IMG_X if closed else self._img_x)
        if self.state == "retreat" and pyxel.frame_count % 6 < 3:  # blinks while backing off
            return
        super().draw(offset)


@register("alpha")
class Alpha(Hunter):
    """The pack leader of The Wilds (level 10, put in by the `alpha` boss): a hunter twice the size. It waits in its
    lair until the snake comes within WAKE px or LAIR seconds are over, then hunts in long bursts with short rests,
    bites harder from farther away and takes many shots (`health`, set by the boss). It flashes when hit."""

    _img_x = 6  # 2x2 sprite tiles from here
    _img_y = 11
    SPEED = 1.3
    HUNT = (2.5, 4.0)
    PAUSE = (1.5, 2.5)
    DETOUR_CHANCE = 0.3
    BITE = 7
    CHUNK = 6
    FLASH = 0.15
    WAKE = 100
    LAIR = 20.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.h = 16
        self.health = 12
        self.flash = 0.0
        self.left = self.LAIR  # asleep in its lair: time to get ready

    def update(self, snake: "Snake", map: "Map"):
        self.flash = max(self.flash - map.game.dt.total_seconds(), 0.0)
        super().update(snake, map)

    def hit(self, dmg: int):
        super().hit(dmg)
        self.flash = self.FLASH

    def draw(self, offset: "Vec2"):
        if (self.flash > 0 and pyxel.frame_count % 2) or (self.state == "retreat" and pyxel.frame_count % 6 < 3):
            return
        Entity.draw(self, offset)


@register("nest")
class Nest(Entity):
    """A beetle burrow: while the snake's head is within ALERT px, every SPAWN seconds (fewer on harder difficulties:
    `hostile` factor) a hunting beetle crawls out, as long as fewer than BROOD of its own are alive. HEALTH shots
    destroy it (counted as defeated); it flashes when hit. Running into it is the end."""

    _img_x = 4
    _img_y = 11
    hostile = True
    HEALTH = 2
    SPAWN = 9.0  # seconds
    BROOD = 2
    ALERT = 160  # px
    FLASH = 0.2  # seconds it flashes after a hit

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health = self.HEALTH
        self.left = pyxel.rndf(1.0, self.SPAWN)  # not all nests at once
        self.brood: list[Hunter] = []
        self.flash = 0.0

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        self.flash = max(self.flash - seconds, 0.0)
        if (snake.head.pos - (self.pos + Vec2(self.w / 2, self.h / 2))).length() > self.ALERT:
            return
        self.left -= seconds
        if self.left > 0:
            return
        self.left = self.SPAWN * map.game.difficulty.hostile
        self.brood = [beetle for beetle in self.brood if beetle.alive]
        if len(self.brood) < self.BROOD:
            beetle = Hunter.at_pos(Vec2(self.pos.x, self.pos.y))
            beetle.asleep = False  # out to hunt
            self.brood.append(beetle)
            map.entities.append(beetle)

    def hit(self, dmg: int):
        super().hit(dmg)
        self.flash = self.FLASH

    def on_intersect(self, snake: "Snake", map: "Map"):
        map.snake_killed = True

    def draw(self, offset: "Vec2"):
        if self.flash > 0 and pyxel.frame_count % 2:
            return
        super().draw(offset)


@register("turret")
class Turret(Entity):
    """A gun emplacement of The Fortress. While the snake's head is within RANGE px with no wall in between, it turns
    towards it and every RELOAD seconds (fewer on harder difficulties: `hostile` factor) fires a slow shot where the
    head is heading, its eye glowing for WARN seconds before. A shot cuts the snake where it strikes (on the head: half
    of it, see `Snake.wound`). HEALTH shots destroy it (counted as defeated); it flashes when hit. Running into it is
    the end."""

    _img_x = 0
    _img_y = 13
    hostile = True
    HOT_IMG_X = 1  # sprite tile next to it: the eye glowing before a shot
    HEALTH = 3
    RANGE = 120  # px
    RELOAD = 2.5  # seconds between shots
    WARN = 0.6  # seconds the eye glows before a shot
    SHOT_SPEED = 2.0  # px per frame, scaled with the difficulty's speed
    SHOT_RANGE = 160  # px a shot flies
    FLASH = 0.2
    COL_SHOT = 8
    COL_BARREL = 5

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health = self.HEALTH
        self.left = pyxel.rndf(self.WARN, self.RELOAD)  # not all turrets at once
        self.flash = 0.0
        self.aim = 90.0  # degrees, where the barrel points
        self.sees = False  # the snake's head is in range and in sight

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    def update(self, snake: "Snake", map: "Map"):
        from snake_quest.weapons import Projectile  # weapons need nothing from here, see GunPickup

        seconds = map.game.dt.total_seconds()
        self.flash = max(self.flash - seconds, 0.0)
        to_head = snake.head.pos - self.center
        self.sees = to_head.length() <= self.RANGE and map.clear_line(self.center, snake.head.pos)
        if not self.sees:
            self.left = max(self.left, self.WARN)  # always a warning before a shot
            return
        speed = self.SHOT_SPEED * map.game.difficulty.speed
        aim = self.intercept(snake, speed)
        self.aim = pyxel.atan2(aim.y, aim.x)
        self.left -= seconds
        if self.left > 0:
            return
        self.left = self.RELOAD * map.game.difficulty.hostile
        start = self.center + Vec2(pyxel.cos(self.aim), pyxel.sin(self.aim)) * 6
        lifetime = self.SHOT_RANGE / speed / map.game.cfg.fps
        map.projectiles.append(
            Projectile(start, self.aim, speed, size=1, col=self.COL_SHOT, hostile=True, lifetime=lifetime)
        )
        map.game.sm.effect("shoot")

    def intercept(self, snake: "Snake", speed: float) -> Vec2:
        """Direction to shoot in to meet the head if it keeps its course (so turning dodges the shot, and the body,
        following the head's actual way, isn't hit instead)."""
        velocity = Vec2(pyxel.cos(snake.heading), pyxel.sin(snake.heading)) * snake.effective_speed
        aim = snake.head.pos - self.center
        for _ in range(3):  # the head moves while the shot flies: refine the meeting point
            aim = snake.head.pos + velocity * (aim.length() / speed) - self.center
        return aim

    def hit(self, dmg: int):
        super().hit(dmg)
        self.flash = self.FLASH

    def on_intersect(self, snake: "Snake", map: "Map"):
        map.snake_killed = True

    def draw(self, offset: "Vec2"):
        if self.flash > 0 and pyxel.frame_count % 2:
            return
        hot = self.sees and self.left <= self.WARN and pyxel.frame_count % 4 < 2
        self.img_x = 8 * (self.HOT_IMG_X if hot else self._img_x)
        center = self.center + offset  # the barrel sticks out of the dome
        tip = center + Vec2(pyxel.cos(self.aim), pyxel.sin(self.aim)) * 7
        pyxel.line(center.x, center.y, tip.x, tip.y, self.COL_BARREL)
        super().draw(offset)


@register("drone")
class Drone(Entity):
    """A small flying machine of The Fortress, one of a swarm. It flies over walls straight for the snake's head, but
    turns only TURN degrees per frame, so it overshoots and loops back. Touching any part of the snake, it stings: STING
    segments off the tail, and the drone is gone (only shot drones count as defeated). A sting the snake is too short
    for is the end. One shot destroys it; its speed scales with the difficulty."""

    _img_x = 6
    _img_y = 13
    hostile = True
    avoid = False
    SPEED = 1.5  # px per frame (the snake starts at 1.3)
    TURN = 5  # degrees per frame
    STING = 2  # segments
    REACH = 3  # px from its centre to a segment's edge

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health = 1
        self.state = "fly"  # always moving (bots don't aim at it from behind)
        self.heading = pyxel.rndf(0, 360)
        self.phase = pyxel.rndf(0, 360)  # wing beat, so a swarm doesn't flap in sync

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    def update(self, snake: "Snake", map: "Map"):
        to_head = snake.head.pos - self.center
        turn = (pyxel.atan2(to_head.y, to_head.x) - self.heading + 180) % 360 - 180
        self.heading = (self.heading + max(-self.TURN, min(self.TURN, turn))) % 360
        speed = self.SPEED * map.game.difficulty.speed
        pos = self.pos + Vec2(pyxel.cos(self.heading), pyxel.sin(self.heading)) * speed
        # over the walls, but never out of the level
        self.pos = Vec2(
            min(max(pos.x, 0), map.cfg.width - self.w),
            min(max(pos.y, map.header), map.header + map.cfg.height - self.h),
        )
        if snake.segment_at(self.center, self.REACH) is not None:
            self.sting(snake, map)

    def sting(self, snake: "Snake", map: "Map") -> None:
        map.game.sm.effect("hurt")
        self.alive = False
        if not snake.cut(self.STING):
            map.snake_killed = True

    def on_intersect(self, snake: "Snake", map: "Map"):
        if self.alive:
            self.sting(snake, map)

    def draw(self, offset: "Vec2"):
        """Hover up and down with the wing beat."""
        bob = Vec2(0, round(pyxel.sin(pyxel.frame_count * 30 + self.phase)))
        super().draw(offset + bob)


@register("enemy")
class Enemy(Entity):
    _img_x = 3
    _img_y = 1
    hostile = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = "idle"
        self._target = None
        self._ref_time: datetime.datetime = datetime.datetime.now()
        self.speed = 1.0
        self.wdg = Widget(
            x=0, y=0, w=3 * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN, bg=6, border=14, text=["Zzz"], text_col=2
        )
        self.dir = Vec2(1, 1)
        self.health = 1

    def update(self, snake: "Snake", map: "Map"):
        _time = datetime.datetime.now()
        if _time - self._ref_time > datetime.timedelta(seconds=4):
            self.state = ["idle", "random", "attack"][pyxel.rndi(0, 2)]
            self.wdg.text = [{"idle": "Zzz", "random": "???", "attack": "!!!"}[self.state]]
            self._ref_time = _time
            if self.state == "random":
                self._target = map.new_pos()
        if self.state == "idle":
            return

        if self.state == "attack":
            self._target = snake.head.pos
        if self.state in ["attack", "random"]:
            # recalc dir
            self.dir = self._target - self.pos
            if self.state == "random" and self.dir.length() < 10:
                self.state = "idle"
                return
            self.dir = self.dir * (1 / self.dir.length())
        # move
        self.pos += self.dir * self.speed

    def on_intersect(self, snake: "Snake", map: "Map"):
        # update stats
        snake._speed *= 1.15
        map.game.score -= 10
        map.game.sm.effect("hurt")
        # destroy self
        self.alive = False

    def draw(self, offset: "Vec2"):
        super().draw(offset=offset)
        if self.alive:
            self.wdg.x = self.pos.x + (self.w / 2) - (self.wdg.w / 2) + offset.x
            self.wdg.y = self.pos.y - self.wdg.h - WIDGET_MARGIN + offset.y
            self.wdg.draw()
