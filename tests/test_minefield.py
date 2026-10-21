import datetime

import pytest
import pyxel

from snake_quest import bot, sound
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import ENTITY_NAMES, Crawler, Hunter, Mine, MinesPickup
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import EMPTY_TILE
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun, Mines

CAMPAIGN = load_campaign()
FRAME = 1 / 24


@pytest.fixture
def minefield(assets, game):
    game.level_counter = CAMPAIGN.resolve("minefield")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    level_map.timers.clear()
    game.dt = datetime.timedelta(seconds=FRAME)
    for ty in range(1, 21):  # an open square in the top left
        for tx in range(1, 21):
            pyxel.tilemaps[level_map.tm].pset(tx, ty, EMPTY_TILE)
    return level_map


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def tick(level_map, snake, seconds=FRAME):
    level_map.game.dt = datetime.timedelta(seconds=seconds)
    for ent in list(level_map.entities):
        ent.update(snake, level_map)


def test_mines_and_crawlers_are_registered():
    assert ENTITY_NAMES["mines"] is MinesPickup and ENTITY_NAMES["mine"] is Mine
    assert ENTITY_NAMES["crawler"] is Crawler and Crawler.hostile
    assert not Mine.hostile and not Mine.tally
    assert sound.EFFECTS["boom"] == 14


def test_mines_drop_behind_the_tail(minefield):
    snake = snake_at(Vec2(120, 100))
    mines = Mines(ammo=2)
    mines.update(snake, minefield, fire=True, seconds=FRAME)
    (mine,) = minefield.entities
    assert isinstance(mine, Mine) and (mine.center - snake.segs[-1].pos).length() < 1
    assert mines.ammo == 1 and not minefield.projectiles


def test_a_mine_arms_then_blasts_hostile_entities_around_it(minefield, game):
    mine = Mine.at_pos(Vec2(80, 80))
    near, far = Crawler.at_pos(Vec2(80, 84)), Hunter.at_pos(Vec2(80 + Mine.BLAST + 6, 80))
    far.asleep = True
    snake = snake_at(Vec2(150, 140))
    minefield.entities += [mine, near, far]
    tick(minefield, snake, Mine.ARM / 2)
    assert mine.boom is None  # not armed yet
    tick(minefield, snake, Mine.ARM)
    assert mine.boom is not None and game.sm.effects_played == ["boom"]
    assert not near.alive and near.killed  # three damage: a crawler's whole armour
    assert far.alive


def test_a_mine_never_hurts_the_snake_and_is_not_counted(minefield):
    snake = snake_at(Vec2(84, 84), length=30)
    mine = Mine.at_pos(Vec2(80, 80))
    minefield.entities.append(mine)
    for _ in range(30):
        tick(minefield, snake)
    assert mine.boom is None and len(snake) == 30
    mine.age = Mine.FUSE
    minefield.update(snake)
    minefield.update(snake)
    assert mine not in minefield.entities and minefield.defeated == 0 and minefield.eaten == 0


def test_crawler_hunts_at_once_and_takes_three_shots(minefield):
    crawler = Crawler.at_pos(Vec2(80, 80))
    assert crawler.state == "hunt"
    crawler.hit(1)
    crawler.hit(1)
    assert crawler.alive
    crawler.hit(1)
    assert not crawler.alive and crawler.killed


def test_crawler_follows_the_trail_to_the_tail(minefield):
    snake = snake_at(Vec2(150, 100), length=30)
    crawler = Crawler.at_pos(Vec2(30, 96))
    start = (crawler.center - snake.segs[-1].pos).length()
    for _ in range(24):
        crawler.update(snake, minefield)
    assert (crawler.center - snake.segs[-1].pos).length() < start - 20


def test_bot_drops_a_mine_for_what_follows_and_never_aims_with_mines(minefield):
    snake = snake_at(Vec2(120, 100))
    snake.weapon = Mines(ammo=3)
    controller = PathController(lambda snake, map: None)
    crawler = Crawler.at_pos(Vec2(120 + 30, 96))  # ahead of the head: not on the trail
    minefield.entities.append(crawler)
    assert controller._aim(snake, minefield) is None
    assert not controller.fire(snake, minefield)
    crawler.pos = snake.segs[-1].pos + Vec2(-20, -4)  # behind the tail
    assert controller.fire(snake, minefield)


def test_bot_with_mines_leads_the_crawlers_instead_of_hunting(minefield):
    snake = snake_at(Vec2(120, 100), length=30)
    snake.weapon = Mines(ammo=3)
    minefield.entities.append(Crawler.at_pos(Vec2(140, 96)))
    assert bot.target(snake, minefield) is None  # no apples here: nothing to lead them to
    snake.weapon = Gun(ammo=3)
    assert bot.target(snake, minefield) is not None  # a gun hunts
