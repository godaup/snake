import datetime
from typing import TYPE_CHECKING

import pyxel

from snake_quest.utils import Vec2
from snake_quest.widget import WIDGET_MARGIN, Widget

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


class Entity:
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


class Apple(Entity):
    _img_x = 2
    _img_y = 0

    def on_intersect(self, snake: "Snake", map: "Map"):
        # update stats
        snake.grow += 5
        map.game.score += 1
        # generate next apple
        new_pos: Vec2 = map.new_pos(snake=snake)
        map.entities.append(Apple.at_pos(new_pos))
        # destroy self
        self.alive = False


class GoldenApple(Entity):
    _img_x = 2
    _img_y = 1

    def on_intersect(self, snake: "Snake", map: "Map"):
        # update stats
        snake.grow += 20
        map.game.score += 5
        # destroy self
        self.alive = False


class SpeedApple(Entity):
    """No length, but a temporary speed boost. A second one restarts the boost instead of stacking it."""

    _img_x = 4
    _img_y = 0
    BOOST = 1.5  # speed factor
    SECONDS = 5.0

    def on_intersect(self, snake: "Snake", map: "Map"):
        snake.boost(self.BOOST, self.SECONDS)
        map.game.score += 1
        self.alive = False


class Firefly(Entity):
    """Lights the breadcrumbs: the level's hidden path appears tile by tile, starting where the snake is."""

    _img_x = 5
    _img_y = 0
    NOTICE = 48  # px: closer than this, the firefly drifts towards the snake's head
    SPEED = 1.5  # px per frame

    def update(self, snake: "Snake", map: "Map"):
        """Fly towards a snake passing nearby, so crossing its corridor is enough to catch it."""
        to_head = snake.head.pos - (self.pos + Vec2(self.w / 2, self.h / 2))
        distance = to_head.length()
        if 0 < distance < self.NOTICE:
            self.pos = self.pos + to_head * (min(self.SPEED, distance) / distance)

    def on_intersect(self, snake: "Snake", map: "Map"):
        map.reveal_path(origin=snake.head.pos)
        self.alive = False


class Enemy(Entity):
    _img_x = 3
    _img_y = 1

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
        # destroy self
        self.alive = False

    def draw(self, offset: "Vec2"):
        super().draw(offset=offset)
        if self.alive:
            self.wdg.x = self.pos.x + (self.w / 2) - (self.wdg.w / 2) + offset.x
            self.wdg.y = self.pos.y - self.wdg.h - WIDGET_MARGIN + offset.y
            self.wdg.draw()


ALL_ENTITIES = [Enemy, Apple, GoldenApple, SpeedApple, Firefly]
# names used in level files (timers, goals)
ENTITY_NAMES = {"enemy": Enemy, "apple": Apple, "golden": GoldenApple, "speed": SpeedApple, "firefly": Firefly}
