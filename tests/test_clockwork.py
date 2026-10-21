"""Boss: The Clockwork (level 35): a fixed block whose face opens when it is jammed (crates on the red plates), held
(the body on blue plates) or unlocked (keys brought), and whose hands cut what they sweep over."""

import datetime

import pytest

from snake_quest.bosses import ClockworkBoss
from snake_quest.campaign import load_campaign
from snake_quest.controls import Controller
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2
from snake_quest.workshop import CELL, Clockwork, Crate, Mouse, RedKey

CAMPAIGN = load_campaign()
FRAME = datetime.timedelta(seconds=1 / 24)
HEADER = 20


@pytest.fixture
def arena(assets, game):
    game.level_counter = CAMPAIGN.resolve("clockwork")
    game.dt = FRAME
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.timers.clear()
    return level_map


def cell(cx, cy) -> Vec2:
    return Vec2(cx * CELL, cy * CELL + HEADER)


def snake_at(pos: Vec2, length=20, orient=0) -> Snake:
    snake = Snake(pos=pos, orient=orient, size=2)
    snake.grow = 0
    back = Vec2(-snake_dir(orient).x * 1.3, -snake_dir(orient).y * 1.3)
    snake.segs += [SnakeSeg(pos + back * i, 2, 0) for i in range(1, length)]
    return snake


def snake_dir(orient) -> Vec2:
    return {0: Vec2(1, 0), 90: Vec2(0, 1), 180: Vec2(-1, 0), 270: Vec2(0, -1)}[orient]


def run(arena, snake, seconds, move=False):
    for _ in range(round(seconds * 24)):
        if move:
            snake.update(FRAME, arena)
        arena.update(snake)


def boss_of(arena) -> ClockworkBoss:
    assert isinstance(arena.boss, ClockworkBoss)
    return arena.boss


def crates(arena) -> list[Crate]:
    return [crate for crate in arena.works.crates if not crate.fixed]


def test_the_clockwork_stands_in_the_middle_and_stops_the_snake(arena):
    clock = boss_of(arena).clock
    assert isinstance(clock, Clockwork) and clock in arena.works.crates and clock.fixed
    snake = snake_at(clock.center + Vec2(-40, 0))
    snake.controller = Controller()
    run(arena, snake, 2, move=True)
    assert snake.stalled and clock.pos == Vec2(192, 164)  # it doesn't budge
    assert not arena.snake_killed


def test_its_shut_face_glints_off_shots_and_its_open_face_takes_them(arena):
    clock = boss_of(arena).clock
    clock.hit(1)
    assert clock.health == 9 and clock.glint > 0
    clock.open = True
    clock.hit(1)
    assert clock.health == 8


def test_crates_on_all_red_plates_jam_it_open_and_then_it_throws_them_back(arena):
    boss = boss_of(arena)
    snake = snake_at(cell(2, 17))
    plates = {(12, 8), (14, 9), (13, 11), (11, 10)}
    starts = {crate: Vec2(crate.pos.x, crate.pos.y) for crate in crates(arena)}
    for crate, plate in zip(
        sorted(crates(arena), key=lambda c: (c.pos.y, c.pos.x)), sorted(plates, key=lambda p: (p[1], p[0])), strict=True
    ):
        crate.pos = cell(*plate)
    run(arena, snake, 0.1)
    assert boss.clock.open
    angles = list(boss.angles)
    run(arena, snake, 3)
    assert boss.angles == angles  # jammed: the hands stand still
    run(arena, snake, 4)
    assert not boss.clock.open
    assert all(crate.pos == start for crate, start in starts.items())


def test_a_hand_sweeping_over_the_body_cuts_it(arena):
    boss = boss_of(arena)
    center = boss.clock.center
    snake = snake_at(center + Vec2(60, -40), length=40, orient=90)  # lying across the long hand's way, down
    boss.angles = [300.0, 90.0]
    before = len(snake)
    run(arena, snake, 3)
    assert len(snake) < before and not arena.snake_killed


def test_the_head_touching_a_hand_costs_half_the_body(arena):
    boss = boss_of(arena)
    center = boss.clock.center
    boss.angles = [0.0, 180.0]
    snake = snake_at(center + Vec2(50, 0), length=40)
    run(arena, snake, 1 / 24)
    assert len(snake) == 20 and not arena.snake_killed
    run(arena, snake, 0.5)
    assert len(snake) == 20  # spared for a moment


def test_the_body_on_two_blue_plates_opens_it_in_the_second_phase(arena):
    boss = boss_of(arena)
    boss.clock.health = 6
    snake = snake_at(cell(2, 17))
    run(arena, snake, 0.1)
    assert boss.phase == 1 and not crates(arena)  # the crates are swept away
    snake = snake_at(cell(11, 6) + Vec2(14, 8), length=30, orient=0)  # over both plates of the top left pair
    run(arena, snake, 0.1)
    assert boss.clock.open


def test_keys_brought_to_it_open_its_locks_and_then_it_stays_open(arena):
    boss = boss_of(arena)
    boss.clock.health = 3
    snake = snake_at(cell(2, 17))
    run(arena, snake, 0.1)
    assert boss.phase == 2 and boss.locks == [0, 1] and not boss.clock.open
    run(arena, snake, boss.setting("call") + 0.1)
    assert any(isinstance(ent, RedKey) for ent in arena.entities)  # the key the first lock needs
    assert any(isinstance(ent, Mouse) for ent in arena.entities)
    for colour in (0, 1):
        snake = snake_at(boss.clock.center + Vec2(-18, 0), length=20)
        snake.segs[-1].key = colour
        run(arena, snake, 0.1)
    assert boss.locks == [] and boss.clock.open
    run(arena, snake, 20)
    assert boss.clock.open


def test_bots_get_a_plan_for_each_phase(arena):
    boss = boss_of(arena)
    snake = snake_at(cell(3, 3))
    snake.weapon = type("Armed", (), {"ammo": 30})()
    plan = boss._plan(arena, snake)
    pushes = [step["push"] for step in plan.rooms[0][1]]
    assert len(pushes) == 4 and all(direction in ("down", "left", "up", "right") for _, direction, _ in pushes)
    boss.clock.health = 6
    run(arena, snake, 0.1)
    kinds = [next(iter(step)) for step in boss._plan(arena, snake).rooms[0][1]]
    assert kinds[-2:] == ["visit", "visit"]
    boss.clock.health = 3
    run(arena, snake, 0.1)
    kinds = [next(iter(step)) for step in boss._plan(arena, snake).rooms[0][1]]
    assert kinds == ["key", "grow", "bring"]
