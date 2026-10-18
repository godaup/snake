import datetime
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

import omegaconf
import pyxel

from snake_quest.campaign import Level
from snake_quest.entity import ALL_ENTITIES, ENTITY_NAMES, Entity
from snake_quest.goals import Goal, load_goals
from snake_quest.timers import Timer
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.game import Game
    from snake_quest.snake import Projectile, Snake

# sprite tile coordinates (image bank 0) with a fixed meaning in every tilemap
EMPTY_TILE = (0, 0)
WALL_TILE = (0, 3)
# level design helper marking the intended route (e.g. through the maze); hidden until revealed
PATH_TILE = (3, 0)


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
        # iterate over tilemap
        for tile_x in range(self.cfg.width // 8):
            for tile_y in range(self.cfg.height // 8):
                img_x, img_y = pyxel.tilemaps[self.cfg.tm].pget(tile_x, tile_y)
                if (img_x, img_y) in (EMPTY_TILE, WALL_TILE):
                    continue
                if (img_x, img_y) == PATH_TILE:
                    self.path.append(Vec2(x=tile_x * 8, y=tile_y * 8 + self.game.cfg.header.h))
                    pyxel.tilemaps[self.cfg.tm].pset(tile_x, tile_y, EMPTY_TILE)
                    continue
                # print(f'at {tile_x=}, {tile_y=} there is {img_x=}, {img_y=}')
                for e_cls in ALL_ENTITIES:
                    if e_cls._img_x == img_x and e_cls._img_y == img_y:
                        ent = e_cls.at_pos(Vec2(x=tile_x * 8, y=tile_y * 8 + self.game.cfg.header.h))
                        self.entities.append(ent)
                        # remove entity from 'background'
                        pyxel.tilemaps[self.cfg.tm].pset(tile_x, tile_y, EMPTY_TILE)
                        # print(f'found {e_cls.__name__} at {tile_x=}, {tile_y=}')
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
        if self.path_revealed or self.game.cfg.debug:
            for pos in self.path:
                pyxel.blt(pos.x + offset.x, pos.y + offset.y, 0, PATH_TILE[0] * 8, PATH_TILE[1] * 8, 8, 8, colkey=0)
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
                if self.tile_at(pos) != EMPTY_TILE:
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

    def reveal_path(self) -> None:
        """Show the breadcrumbs, e.g. when the snake triggers a mechanism."""
        self.path_revealed = True

    def tile_at(self, pos: Vec2) -> tuple[int, int]:
        """Sprite tile shown at a world position."""
        return pyxel.tilemaps[self.cfg.tm].pget(pos.x // 8, (pos.y - self.game.cfg.header.h) // 8)

    def check_on_wall(self, pos: Vec2) -> bool:
        return self.tile_at(pos) == WALL_TILE

    def create_callback(self, description: dict) -> Callable[["Map", "Snake"], None]:
        if description["type"] == "spawn":

            def callback(map: "Map", snake: "Snake"):
                # generate next entity
                if "pos" in description:
                    new_pos = Vec2(*description["pos"])
                else:
                    new_pos: Vec2 = map.new_pos(snake=snake)
                ent_cls: Entity = ENTITY_NAMES[description["entity"]]
                map.entities.append(ent_cls.at_pos(new_pos))

            return callback
        elif description["type"] == "grow":

            def callback(map: "Map", snake: "Snake"):
                snake.grow += description["value"]

            return callback

    def check_win(self, snake: "Snake") -> bool:
        # all conditions must be met
        return all(goal.done(map=self, snake=snake) for goal in self.goals)
