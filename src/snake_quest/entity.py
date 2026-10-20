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


@register("hunter")
class Hunter(Entity):
    """A beetle of The Wilds. It sleeps until the snake comes within WAKE px or its nap is over, then hunts the tail: it
    follows the shortest way through the level to the snake's last segment (`map.chase`), a little slower than the
    snake. A bite on the body takes CHUNK segments off the tail and sends it back to REST; a bite the snake is too
    short for, or running into an awake beetle head first, is the end. Portals don't carry it."""

    _img_x = 0
    _img_y = 11
    hostile = True
    ASLEEP_IMG_X = 1  # sprite tile next to it: eyes closed
    WAKE = 56  # px
    NAP = (4.0, 12.0)  # seconds asleep at most, chosen at random
    SPEED = 1.3  # px per frame, as fast as the snake starts; both scale with the difficulty's speed
    BITE = 5  # px from its centre to a segment
    REST = 2.5  # seconds it keeps away after a bite
    CHUNK = 10  # segments a bite takes off the tail

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.asleep = True
        self.nap = pyxel.rndf(*self.NAP)
        self.rest = 0.0

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        if self.asleep:
            self.nap -= seconds
            if self.nap <= 0 or (snake.head.pos - self.center).length() < self.WAKE:
                self.asleep = False
            return
        if self.rest > 0:
            self.rest -= seconds
            self._move(self.center - snake.head.pos, self.SPEED / 2)  # back off
            return
        self._move(self._next_step(snake, map) - self.center, self.SPEED * map.game.difficulty.speed)
        if any((seg.pos - self.center).length() < self.BITE for seg in snake.segs[1:]):
            self.bite(snake, map)

    def _next_step(self, snake: "Snake", map: "Map") -> Vec2:
        """Where to head for: the centre of the neighbouring tile closest to the snake's tail along the way (diagonal
        only where both tiles beside the corner are free), or the tail itself once in its tile."""
        distance = map.chase(snake)
        tail = snake.segs[-1].pos
        x, y = here = map.tile_xy(self.center)
        if here not in distance or here == map.tile_xy(tail):
            return tail
        steps = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        steps += [
            (x + dx, y + dy) for dx in (-1, 1) for dy in (-1, 1) if (x + dx, y) in distance and (x, y + dy) in distance
        ]
        best = min((step for step in steps if step in distance), key=distance.get, default=here)
        return map.tile_center(best)

    def _move(self, direction: Vec2, speed: float) -> None:
        length = direction.length()
        if length > 0:
            self.pos = self.pos + direction * (min(speed, length) / length)

    def bite(self, snake: "Snake", map: "Map") -> None:
        """Take CHUNK segments off the tail; the end when the snake isn't longer than that."""
        map.game.sm.effect("hurt")
        self.rest = self.REST
        if not snake.cut(self.CHUNK):
            map.snake_killed = True

    def on_intersect(self, snake: "Snake", map: "Map"):
        """The snake runs into it head first."""
        if not self.asleep:
            map.snake_killed = True

    def draw(self, offset: "Vec2"):
        self.img_x = 8 * (self.ASLEEP_IMG_X if self.asleep else self._img_x)
        if self.rest > 0 and pyxel.frame_count % 6 < 3:  # blinks while backing off
            return
        super().draw(offset)


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
