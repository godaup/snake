import pytest
import pyxel

from snake_quest import bot
from snake_quest.campaign import load_campaign
from snake_quest.entity import ENTITY_NAMES, Apple, Critter
from snake_quest.goals import load_goals
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import FLOOR_TILES
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()


@pytest.fixture
def prey(assets, game):
    game.level_counter = CAMPAIGN.resolve("prey")
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.entities.clear()
    return level_map


def open_spot(level_map, reach=4) -> Vec2:
    """World position in the middle of open floor `reach` tiles around."""
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(reach + 1, level_map.cfg.height // 8 - reach - 1):
        for tx in range(reach + 1, level_map.cfg.width // 8 - reach - 1):
            area = [(tx + dx, ty + dy) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)]
            if all(tilemap.pget(*t) in FLOOR_TILES for t in area):
                return level_map.tile_center((tx, ty))
    raise AssertionError("no open spot")


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def test_critter_is_registered():
    assert ENTITY_NAMES["critter"] is Critter
    assert not Critter.hostile


def test_grazes_until_the_snake_comes_near_then_runs_away(prey):
    spot = open_spot(prey)
    critter = Critter.at_pos(spot - Vec2(4, 4))
    far = snake_at(spot + Vec2(-Critter.FLEE - 30, 0))
    critter.update(far, prey)
    assert critter.state == "graze" and critter.center == spot
    near = snake_at(spot + Vec2(-30, 0))
    before = (critter.center - near.head.pos).length()
    for _ in range(10):
        critter.update(near, prey)
    assert critter.state == "run"
    assert (critter.center - near.head.pos).length() > before


def test_tires_after_a_run(prey, monkeypatch):
    spot = open_spot(prey)
    critter = Critter.at_pos(spot - Vec2(4, 4))
    critter.state, critter.left = "run", 0.01
    start = critter.center
    critter.update(snake_at(spot + Vec2(-30, 0)), prey)
    assert critter.state == "breath" and critter.center == start


def test_eaten_it_feeds_and_counts_for_the_goal(prey, game):
    snake = snake_at(open_spot(prey))
    critters = [Critter.at_pos(Vec2(0, 0)), Critter.at_pos(Vec2(8, 0))]
    prey.entities += critters
    (goal,) = load_goals({"collect_all": "critter"}, map=prey)
    critters[0].on_intersect(snake, prey)
    assert snake.grow == Critter.LENGTH and game.score == Critter.POINTS
    assert goal.status(prey, snake) == "CRITTER 1/2"


def test_harder_critters_run_longer(prey, game, monkeypatch):
    monkeypatch.setattr(pyxel, "rndf", lambda low, high: low)
    spot = open_spot(prey)
    game.profile.difficulty = "nightmare"
    critter = Critter.at_pos(spot - Vec2(4, 4))
    critter.update(snake_at(spot + Vec2(-30, 0)), prey)
    assert critter.left == pytest.approx(Critter.RUN[0] * game.difficulty.helpful - 1 / 24, abs=0.05)


def test_flight_field_is_measured_from_the_head(prey):
    snake = snake_at(open_spot(prey))
    distance = prey.flight(snake)
    assert distance[prey.tile_xy(snake.head.pos)] == 0


def test_bot_goes_for_what_the_level_asks_to_collect(prey):
    spot = open_spot(prey)
    snake = snake_at(spot)
    prey.entities += [Apple.at_pos(spot + Vec2(10, 0)), Critter.at_pos(spot + Vec2(40, 0))]
    assert bot.target(snake, prey) == prey.entities[1].center
