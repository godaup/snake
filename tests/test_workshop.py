"""Arc 7, the Workshop: crates, plates and gates, reset levers (Crates), the body on plates (Pressure Plates), keys and
mice (Keys), belts and levers (Conveyors), and the plans bots follow. The Clockwork has its own file."""

import datetime
import sys
from pathlib import Path

import omegaconf
import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.controls import Controller, PathController, ScriptedController
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.tiles import (
    BELT_TILES,
    EMPTY_TILE,
    GATE_OPEN_TILES,
    GATE_TILES,
    LEVER_TILES,
    LOCK_TILES,
    PLATE_TILES,
    RESET_TILE,
    WALL_TILES,
    WALL_VARIANT_ROW,
)
from snake_quest.utils import Vec2
from snake_quest.workshop import CELL, BlueKey, Crate, Mouse, RedKey, Works

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import solve_workshop  # noqa: E402

CAMPAIGN = load_campaign()
DT = datetime.timedelta(seconds=1 / 24)
HEADER = 20
# the Workshop's levels with a plan and their puzzle texts, and all of them (the boss has no plan)
PUZZLES = {"crates": "crates.txt", "plates": "plates.txt", "keys": "keys.txt", "conveyors": "conveyors.txt"}
LAYOUTS = {**PUZZLES, "clockwork": "clockwork.txt"}


def level(game, name) -> Map:
    game.level_counter = CAMPAIGN.resolve(name)
    game.dt = DT
    return Map(level=CAMPAIGN.level(game.level_counter), game=game)


def room(level_map, w=40, h=24, tiles=None):
    """An open room, walled in, at the level's top left, with `tiles` ({(x, y): sprite}) painted in; no entities or
    timers, and the machinery built anew."""
    level_map.entities.clear()
    level_map.timers.clear()
    tilemap = pyxel.tilemaps[level_map.tm]
    for ty in range(h):
        for tx in range(w):
            wall = tx in (0, w - 1) or ty in (0, h - 1)
            tilemap.pset(tx, ty, (15, WALL_VARIANT_ROW) if wall else EMPTY_TILE)
    for tile, sprite in (tiles or {}).items():
        tilemap.pset(*tile, sprite)
    level_map.cfg.plan = None
    del level_map.cfg["plan"]
    level_map.works = Works(level_map)
    return level_map


def cell(cx, cy) -> Vec2:
    """The top left corner of a bench grid cell, in world px."""
    return Vec2(cx * CELL, cy * CELL + HEADER)


def crate_at(level_map, cx, cy) -> Crate:
    crate = Crate.at_pos(cell(cx, cy))
    level_map.entities.append(crate)
    level_map.works.crates.append(crate)
    return crate


def snake_at(pos: Vec2, length=10, orient=0) -> Snake:
    snake = Snake(pos=pos, orient=orient, size=2)
    snake.grow = 0
    back = Vec2(-pyxel.cos(orient) * 1.3, -pyxel.sin(orient) * 1.3)
    snake.segs += [SnakeSeg(pos + back * i, 2, 0) for i in range(1, length)]
    return snake


def run(level_map, snake, frames, controller=None):
    snake.controller = controller or Controller()
    for _ in range(frames):
        snake.update(DT, level_map)
        level_map.update(snake)


def plate(cx, cy, colour=0) -> dict:
    return {(cx * 2 + dx, cy * 2 + dy): PLATE_TILES[colour] for dx in (0, 1) for dy in (0, 1)}


def gate(cx, cy, colour=0) -> dict:
    return {(cx * 2 + dx, cy * 2 + dy): GATE_TILES[colour] for dx in (0, 1) for dy in (0, 1)}


@pytest.fixture
def crates(assets, game):
    return level(game, "crates")


# ---- Crates ---------------------------------------------------------------------------------------------------------


def test_the_workshop_is_built_for_its_levels_only(assets, game, crates):
    assert crates.works is not None and crates.works.plan is not None
    assert level(game, "classic").works is None


def test_a_crate_pushed_head_on_moves_ahead_of_the_head_and_settles_on_the_grid(crates):
    room(crates)
    crate = crate_at(crates, 6, 5)
    snake = snake_at(cell(3, 5) + Vec2(0, 8))  # heading right, at the crate's middle
    run(crates, snake, 60)
    assert crate.pos.x > cell(6, 5).x + 16  # pushed on
    assert crate.pos.y == cell(6, 5).y  # along its row only
    assert snake.head.pos.x < crate.pos.x  # the head stays behind it
    run(crates, snake, 30, ScriptedController([1.0] * 12))  # turn off it: it glides to the grid
    assert (crate.pos.x - crates.works.origin.x) % CELL == 0


def test_a_crate_that_cant_move_stalls_the_snake_and_turning_frees_it(crates):
    room(crates)
    crate = crate_at(crates, 18, 5)
    crate.pos = Vec2(39 * 8 - CELL, crate.pos.y)  # against the room's right wall
    snake = snake_at(cell(14, 5) + Vec2(0, 8))
    run(crates, snake, 60)
    assert snake.stalled
    still = Vec2(snake.head.pos.x, snake.head.pos.y)
    run(crates, snake, 5)
    assert snake.head.pos == still  # stands
    assert crate.pos.x <= 39 * 8 - CELL + 0.5
    run(crates, snake, 30, ScriptedController([-1.0] * 12))  # turn up along its face
    assert not snake.stalled and snake.head.pos.y < still.y - 10
    p, q = snake.get_collision_points()
    assert not crates.check_on_wall(p) and not crates.check_on_wall(q) and not snake.self_intersect()


def test_a_glancing_head_slides_along_a_crate_without_pushing_it(crates):
    room(crates)
    crate = crate_at(crates, 8, 5)
    snake = snake_at(cell(8, 5) + Vec2(2, -3), orient=10)  # above it, shallow onto its top face
    run(crates, snake, 30)
    assert crate.pos == cell(8, 5)
    assert not snake.stalled


def test_a_plate_under_a_crate_opens_the_gate_of_its_colour(crates):
    room(crates, tiles={**plate(8, 5), **gate(12, 5)})
    tilemap = pyxel.tilemaps[crates.tm]
    snake = snake_at(cell(3, 9))
    run(crates, snake, 1)
    assert tilemap.pget(24, 10) == GATE_TILES[0] and GATE_TILES[0] in WALL_TILES
    crate_at(crates, 8, 5)
    run(crates, snake, 1)
    assert tilemap.pget(24, 10) == GATE_OPEN_TILES[0]


def test_the_body_holds_a_plate_down_and_a_gate_never_shuts_on_the_snake(crates):
    room(crates, tiles={**plate(8, 5), **gate(12, 5)})
    tilemap = pyxel.tilemaps[crates.tm]
    snake = snake_at(cell(8, 5) + Vec2(8, 8), length=30)  # lying on the plate
    run(crates, snake, 1)
    assert tilemap.pget(24, 10) == GATE_OPEN_TILES[0]
    # off the plate, but in the gate: it stays open until the snake is through
    snake = snake_at(cell(12, 5) + Vec2(8, 8), length=8)
    run(crates, snake, 1)
    assert tilemap.pget(24, 10) == GATE_OPEN_TILES[0]
    snake = snake_at(cell(3, 9))
    run(crates, snake, 1)
    assert tilemap.pget(24, 10) == GATE_OPEN_TILES[0] and (24, 10) in crates.closing  # let go of: it blinks
    run(crates, snake, 15)
    assert tilemap.pget(24, 10) == GATE_TILES[0] and not crates.closing


def test_the_reset_lever_puts_its_rooms_crates_back(crates):
    reset = {(2, 18): RESET_TILE, (3, 18): RESET_TILE, (2, 19): RESET_TILE, (3, 19): RESET_TILE}
    room(crates, tiles=reset)
    crate = crate_at(crates, 6, 5)
    crate.pos = cell(9, 5)
    snake = snake_at(cell(1, 9) + Vec2(8, 0), orient=90)  # heading down, onto the lever
    run(crates, snake, 12)
    assert crate.pos == cell(6, 5)


def test_crates_are_walls_to_bots_except_the_one_they_push(crates):
    room(crates)
    crate = crate_at(crates, 8, 5)
    bot = PathController(lambda snake, map: None)
    snake = snake_at(cell(2, 9))
    arcs, field = bot.blocks(snake, crates)
    assert len(arcs) == len(field) == 1
    assert field[0][0] < crate.pos.x and field[0][2] > crate.pos.x + CELL


@pytest.mark.parametrize("name", sorted(PUZZLES))
def test_each_plan_solves_its_puzzle(name):
    """The plan the bot follows works on the puzzle text (every push possible, the exit in reach at the end)."""
    puzzle = solve_workshop.Puzzle(solve_workshop.read(TOOLS / "puzzles" / PUZZLES[name]))
    plan = omegaconf.OmegaConf.to_container(omegaconf.OmegaConf.load(CAMPAIGN.level(CAMPAIGN.resolve(name)).path).plan)
    assert solve_workshop.check(puzzle, plan) == []


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_each_level_is_drawn_from_its_puzzle_text(assets, game, name):
    """The tilemap shows what the puzzle text says (run tools/draft_workshop.py after editing a puzzle)."""
    level_map = level(game, name)
    puzzle = solve_workshop.Puzzle(solve_workshop.read(TOOLS / "puzzles" / LAYOUTS[name]))
    width = max(x for x, _ in puzzle.cells) + 1
    height = max(y for _, y in puzzle.cells) + 1
    assert (level_map.cfg.width, level_map.cfg.height) == (width * CELL, height * CELL)
    crates = {(int(c.pos.x) // CELL, (int(c.pos.y) - HEADER) // CELL) for c in level_map.works.crates if not c.fixed}
    assert crates == set(puzzle.crates)
    start = level_map.start
    assert (int(start.x) // CELL, (int(start.y) - HEADER) // CELL) == puzzle.start


# ---- Keys -----------------------------------------------------------------------------------------------------------


def lock(cx, cy, colour=0) -> dict:
    return {(cx * 2 + dx, cy * 2 + dy): LOCK_TILES[colour] for dx in (0, 1) for dy in (0, 1)}


def test_a_key_rides_at_the_tail_and_growing_buries_it(crates):
    room(crates)
    snake = snake_at(cell(5, 5), length=10)
    RedKey.at_pos(cell(5, 5)).on_intersect(snake, crates)
    assert len(snake) == 11 and snake.segs[-1].key == 0
    snake.grow = 5
    run(crates, snake, 60)
    assert [seg.key for seg in snake.segs].index(0) == 10  # the same place from the head, more body behind it
    assert len(snake) > 11 and crates.works.keys == {0}


def test_a_lock_is_a_wall_until_the_snake_brings_its_key_and_then_opens(crates):
    room(crates, tiles=lock(12, 5))
    tilemap = pyxel.tilemaps[crates.tm]
    door = cell(12, 5) + Vec2(4, 4)
    assert crates.check_on_wall(door)
    snake = snake_at(cell(9, 5) + Vec2(0, 8), length=10)
    RedKey.at_pos(cell(1, 1)).on_intersect(snake, crates)
    run(crates, snake, 1)
    assert not crates.check_on_wall(door)  # the key's colour: the head may touch it
    run(crates, snake, 50)
    assert tilemap.pget(24, 10) == GATE_OPEN_TILES[0]  # open for good
    assert not any(seg.key is not None for seg in snake.segs) and crates.works.keys == set()
    p, q = snake.get_collision_points()
    assert not crates.check_on_wall(p) and not crates.check_on_wall(q)


def test_a_key_cut_off_with_the_tail_falls_to_the_floor(crates):
    room(crates)
    snake = snake_at(cell(5, 5), length=10)
    BlueKey.at_pos(cell(1, 1)).on_intersect(snake, crates)
    run(crates, snake, 1)
    snake.cut(3)
    run(crates, snake, 1)
    dropped = [ent for ent in crates.entities if isinstance(ent, BlueKey)]
    assert len(dropped) == 1 and crates.works.keys == set()


def test_a_mouse_goes_for_the_key_nearest_the_tail_and_bites_the_body_off_behind_it(crates):
    room(crates)
    snake = snake_at(cell(10, 5), length=20)
    RedKey.at_pos(cell(1, 1)).on_intersect(snake, crates)
    snake.grow = 0
    snake.segs += [SnakeSeg(snake.segs[-1].pos - Vec2(1.3 * i, 0), 2, 0) for i in range(1, 6)]
    crates.works.update(snake)  # the body carries a key now
    mouse = Mouse.at_pos(cell(3, 3))
    _, goal = mouse.quarry(snake, crates)
    assert goal == snake.segs[20].pos  # the key's segment
    mouse.pos = snake.segs[12].pos - Vec2(4, 4)
    mouse.bite(snake, crates)
    assert len(snake) == 12  # cut where it bit: the key falls off with the rest
    run(crates, snake, 1)
    assert any(isinstance(ent, RedKey) for ent in crates.entities)


# ---- Conveyors ------------------------------------------------------------------------------------------------------


def belt(cells, sprite) -> dict:
    return {(cx * 2 + dx, cy * 2 + dy): sprite for cx, cy in cells for dx in (0, 1) for dy in (0, 1)}


def test_a_belt_carries_the_head_and_a_crate(crates):
    right = next(tile for tile, d in BELT_TILES.items() if d == (1, 0))
    room(crates, tiles=belt([(x, 8) for x in range(3, 15)], right))
    crate = crate_at(crates, 10, 8)
    snake = snake_at(cell(4, 8) + Vec2(8, 8), orient=270)  # heading up, across the belt
    start = Vec2(snake.head.pos.x, snake.head.pos.y)
    run(crates, snake, 4)
    assert snake.head.pos.x > start.x + 1  # carried along, though it points up
    run(crates, snake, 30)
    assert crate.pos.x > cell(10, 8).x + 10


def test_a_lever_turns_its_rooms_belts_round_once_per_crossing(crates):
    right = next(tile for tile, d in BELT_TILES.items() if d == (1, 0))
    left = next(tile for tile, d in BELT_TILES.items() if d == (-1, 0))
    lever = {(4 + dx, 10 + dy): LEVER_TILES[0] for dx in (0, 1) for dy in (0, 1)}
    room(crates, tiles={**belt([(8, 2), (9, 2)], right), **lever})
    tilemap = pyxel.tilemaps[crates.tm]
    snake = snake_at(cell(2, 5) + Vec2(0, 8))  # heading right, over the whole lever (all four tiles)
    run(crates, snake, 40)
    assert tilemap.pget(16, 4) == left and tilemap.pget(4, 10) == LEVER_TILES[1]


def test_bots_keep_off_levers_the_plan_isnt_heading_for(assets, game):
    level_map = level(game, "conveyors")
    plan = level_map.works.plan
    assert plan.avoid() and not any(tile in plan.avoid() for tile in [(12, 20), (13, 20), (12, 21), (13, 21)])
    plan.index = 1  # past the lever step: the lever is kept off now
    assert (12, 20) in plan.avoid()
