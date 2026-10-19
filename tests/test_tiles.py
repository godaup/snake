import pytest
import pyxel

from snake_quest.campaign import Level, load_campaign
from snake_quest.entity import ENTITY_TILES
from snake_quest.goals import load_goals
from snake_quest.map import Map
from snake_quest.snake import Snake
from snake_quest.tiles import (
    EXIT_TILE,
    FLOOR_TILES,
    HAZARD_CUT,
    HAZARD_TILE,
    PORTAL_TILES,
    TILE_KINDS,
    WALL_TILE,
    TileKind,
    tile_kind,
)
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()


@pytest.fixture
def maneuver(assets, game):
    return Map(level=CAMPAIGN.level(CAMPAIGN.resolve("maneuver")), game=game)


def world(level_map, tile) -> Vec2:
    """World position of a tile's centre."""
    return Vec2(tile[0] * 8 + 4, tile[1] * 8 + 4 + level_map.game.cfg.header.h)


def snake_at(level_map, tile, length=1) -> Snake:
    snake = Snake(pos=world(level_map, tile), orient=0, size=2)
    snake.grow = 0
    snake.segs += [type(snake.head)(world(level_map, tile), 2, 0) for _ in range(length - 1)]
    return snake


def free_tile(level_map, near=(10, 10)) -> tuple[int, int]:
    """A floor tile surrounded by floor."""
    tilemap = pyxel.tilemaps[level_map.cfg.tm]
    for x in range(near[0], level_map.cfg.width // 8 - 2):
        for y in range(near[1], level_map.cfg.height // 8 - 2):
            area = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
            if all(tilemap.pget(*t) in FLOOR_TILES for t in area) and (x, y) not in level_map.portals:
                return x, y
    raise AssertionError("no free tile")


def test_every_special_tile_has_a_kind():
    assert tile_kind(WALL_TILE) == TileKind.WALL
    assert tile_kind(EXIT_TILE) == TileKind.EXIT
    assert tile_kind(HAZARD_TILE) == TileKind.HAZARD
    assert {tile_kind(tile) for tile in PORTAL_TILES} == {TileKind.PORTAL}
    assert tile_kind(next(iter(ENTITY_TILES))) is None


def test_new_tiles_have_sprites(assets):
    for tile in [*PORTAL_TILES, EXIT_TILE, HAZARD_TILE]:
        pixels = [pyxel.images[0].pget(tile[0] * 8 + x, tile[1] * 8 + y) for x in range(8) for y in range(8)]
        assert any(pixels), tile


def test_tiles_are_unique():
    tiles = [*TILE_KINDS]
    assert len(tiles) == len(set(tiles))


def test_maneuver_has_two_portal_pairs(maneuver):
    assert len(maneuver.portals) == 4
    for tile, partner in maneuver.portals.items():
        assert maneuver.portals[partner] == tile
        assert maneuver.tile_at(world(maneuver, tile)) == maneuver.tile_at(world(maneuver, partner))


def test_portal_moves_the_head_to_its_partner_once(maneuver):
    tile, partner = next(iter(maneuver.portals.items()))
    snake = snake_at(maneuver, tile)
    maneuver.update(snake)
    assert snake.head.pos == world(maneuver, partner)
    # standing on the arrival portal doesn't send it back
    maneuver.update(snake)
    assert snake.head.pos == world(maneuver, partner)
    # leave and come back: the portal works again
    snake.head.pos = world(maneuver, (partner[0] + 2, partner[1]))
    maneuver.update(snake)
    snake.head.pos = world(maneuver, partner)
    maneuver.update(snake)
    assert snake.head.pos == world(maneuver, tile)


def test_unpaired_portal_fails_to_load(assets, game, monkeypatch):
    original = Level.load_tilemaps

    def load_with_lonely_portal(level):
        original(level)
        pyxel.tilemaps[4].pset(20, 20, PORTAL_TILES[3])

    monkeypatch.setattr(Level, "load_tilemaps", load_with_lonely_portal)
    with pytest.raises(ValueError, match="pair"):
        Map(level=CAMPAIGN.level(CAMPAIGN.resolve("maneuver")), game=game)


def test_walking_distance_goes_through_portals(maneuver):
    tile, partner = next(iter(maneuver.portals.items()))
    assert maneuver.walking_distances(world(maneuver, tile))[partner] == 1


def test_hazard_cuts_once_per_tile_entered(maneuver):
    tile = free_tile(maneuver)
    pyxel.tilemaps[maneuver.cfg.tm].pset(*tile, HAZARD_TILE)
    snake = snake_at(maneuver, tile, length=HAZARD_CUT * 2 + 1)
    maneuver.update(snake)
    assert len(snake) == HAZARD_CUT + 1
    maneuver.update(snake)  # still on the same thorns
    assert len(snake) == HAZARD_CUT + 1
    assert not maneuver.snake_killed


def test_hazard_kills_a_short_snake(maneuver):
    tile = free_tile(maneuver)
    pyxel.tilemaps[maneuver.cfg.tm].pset(*tile, HAZARD_TILE)
    snake = snake_at(maneuver, tile, length=HAZARD_CUT)
    maneuver.update(snake)
    assert maneuver.snake_killed
    assert len(snake) == HAZARD_CUT


def test_exit_tile_goal(maneuver):
    (goal,) = load_goals({"exit": True}, map=maneuver)
    tile = free_tile(maneuver)
    snake = snake_at(maneuver, tile)
    assert not goal.done(maneuver, snake)
    pyxel.tilemaps[maneuver.cfg.tm].pset(*tile, EXIT_TILE)
    assert goal.done(maneuver, snake)


def test_cut_keeps_at_least_one_segment():
    snake = Snake(pos=Vec2(0, 0), orient=0, size=2)
    snake.segs *= 3
    assert snake.cut(2)
    assert len(snake) == 1
    assert not snake.cut(1)
    assert len(snake) == 1
