"""The Keeper (the bonus arc): the pet (a bot whose choices can be read), the hand (placing and lifting, budgets,
sprouts), the tools (trees, lures, lanterns), hunters in the garden (thorns, pens), the bonus arc's place in the
campaign, and the bot that plays the hand. The Crow has its own file."""

import datetime

import pytest
import pyxel

from snake_quest import bot
from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController
from snake_quest.entity import Hunter
from snake_quest.game import Game
from snake_quest.keeper import (
    CLEAR,
    SPROUT,
    FallenApple,
    Hand,
    HandBot,
    HandInput,
    Lantern,
    Lure,
    PetController,
    Tree,
)
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.states import StateID
from snake_quest.states.mission import MissionStateHandler
from snake_quest.states.running import RunningStateHandler
from snake_quest.tiles import HAZARD_TILE, WALL_TILES
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()
FRAME = datetime.timedelta(seconds=1 / 24)
HEADER = 20
KEEPER = ("hedges", "orchard", "lures", "lanterns", "crow")


def garden(game, name="hedges") -> Map:
    """A Keeper level without its timers or entities (and no snake yet)."""
    game.level_counter = CAMPAIGN.resolve(name)
    game.dt = FRAME
    level_map = Map(level=CAMPAIGN.level(game.level_counter), game=game)
    level_map.timers.clear()
    level_map.entities.clear()
    return level_map


def center(tile) -> Vec2:
    return Vec2(tile[0] * 8 + 4, tile[1] * 8 + 4 + HEADER)


def snake_at(tile, length=12, orient=0) -> Snake:
    """A straight snake with its head on `tile`, pointing `orient` (0: right)."""
    pos = center(tile)
    snake = Snake(pos=pos, orient=orient, size=2)
    snake.grow = 0
    back = Vec2(-pyxel.cos(orient) * 1.3, -pyxel.sin(orient) * 1.3)
    snake.segs += [SnakeSeg(pos + back * i, 2, 0) for i in range(1, length)]
    return snake


def step(level_map, snake, frames=1):
    for _ in range(frames):
        snake.update(dt=FRAME, map=level_map)
        level_map.update(snake)


def put(level_map, cls, tile):
    ent = cls.at_pos(Vec2(tile[0] * 8, tile[1] * 8 + HEADER))
    level_map.entities.append(ent)
    return ent


# ---- the bonus arc in the campaign -------------------------------------------------------------------------------


def test_the_keeper_is_a_bonus_arc_after_the_story():
    arc = CAMPAIGN.arcs[-1]
    assert arc.name == "The Keeper"
    assert [CAMPAIGN.level(n).name for n in range(arc.first, arc.last + 1)] == list(KEEPER)
    assert all(CAMPAIGN.level(n).bonus for n in range(arc.first, arc.last + 1))
    assert CAMPAIGN.story_last == arc.first - 1 == CAMPAIGN.resolve("ouroboros")
    assert CAMPAIGN.endings == {CAMPAIGN.story_last, len(CAMPAIGN)}


def test_it_opens_once_the_story_is_done(game):
    assert CAMPAIGN.arcs[-1] not in game.unlocked_arcs()
    game.profile.arcs_done.append("Ouroboros")
    assert CAMPAIGN.arcs[-1] in game.unlocked_arcs()


@pytest.mark.parametrize("name", ["ouroboros", "crow"])
def test_the_victory_screen_shows_after_the_story_and_after_the_bonus_arc(game, name):
    game.level_counter = CAMPAIGN.resolve(name)
    game.start_level = CAMPAIGN.arc_of(game.level_counter).first
    Game.level_up(game)
    assert game.requested_states == [StateID.VICTORY]
    assert CAMPAIGN.arc_of(game.level_counter).name in game.profile.arcs_done
    assert game.start_level == CAMPAIGN.arc_of(game.level_counter).first  # a restart replays that arc


def test_the_mission_counts_bonus_levels_apart(assets, game):
    game.level_counter = CAMPAIGN.resolve("orchard")
    game._running = RunningStateHandler(game)
    assert MissionStateHandler(game).lines()["kicker"].startswith("BONUS LEVEL 2 OF 5  -  THE KEEPER")
    game.level_counter = CAMPAIGN.resolve("classic")
    game._running = RunningStateHandler(game)
    assert MissionStateHandler(game).lines()["kicker"].startswith(f"LEVEL 1 OF {CAMPAIGN.story_last}")


def test_a_keeper_level_gives_the_snake_to_the_pet_and_the_player_the_hand(assets, game):
    game.level_counter = CAMPAIGN.resolve("hedges")
    running = RunningStateHandler(game)
    assert isinstance(running.snake.controller, PetController)
    assert isinstance(running.map.hand.player, HandInput)
    game.level_counter = CAMPAIGN.resolve("classic")
    assert RunningStateHandler(game).map.hand is None


# ---- the pet -----------------------------------------------------------------------------------------------------


def test_the_pet_goes_for_the_nearest_apple_by_walking_not_by_air(assets, game):
    level_map = garden(game)
    snake = snake_at((10, 8))
    across = put(level_map, FallenApple, (10, 14))  # 6 tiles away, but behind the wall across the garden
    along = put(level_map, FallenApple, (2, 6))  # 8 tiles away by air, and that is the way too
    pet = PetController()
    assert pet.choose(snake, level_map) == along.pos + Vec2(4, 4)
    assert across.alive


def test_the_pet_keeps_its_choice_until_another_is_clearly_nearer(assets, game):
    level_map = garden(game)
    snake = snake_at((10, 8))
    first = put(level_map, FallenApple, (16, 8))
    pet = PetController()
    pet.choose(snake, level_map)
    assert pet.choice is first
    put(level_map, FallenApple, (5, 8))  # a little nearer: it keeps going
    pet.choose(snake, level_map)
    assert pet.choice is first
    closer = put(level_map, FallenApple, (11, 6))
    level_map._fields.clear()
    pet.choose(snake, level_map)
    assert pet.choice is closer


def test_the_pet_prefers_golden_apples(assets, game):
    from snake_quest.entity import GoldenApple

    level_map = garden(game)
    snake = snake_at((10, 8))
    put(level_map, FallenApple, (14, 8))
    golden = put(level_map, GoldenApple, (17, 8))
    pet = PetController()
    pet.choose(snake, level_map)
    assert pet.choice is golden


def test_the_pet_doesnt_know_thorns_but_the_other_bot_does(assets, game):
    level_map = garden(game)
    thorns = next(
        (x, y) for y in range(24) for x in range(40) if pyxel.tilemaps[level_map.tm].pget(x, y) == HAZARD_TILE
    )
    cell = (thorns[0] * 2, (thorns[1] * 8 + HEADER) // 4)
    assert PathController(lambda s, m: None)._wall(level_map, cell)
    assert not PetController()._wall(level_map, cell)


def test_the_pet_runs_only_from_what_it_sees_awake(assets, game):
    level_map = garden(game)
    snake = snake_at((10, 8))
    sleeper = put(level_map, Hunter, (13, 8))
    far = put(level_map, Hunter, (35, 20))
    far.asleep = False
    pet = PetController()
    assert pet.threats(snake, level_map) == []
    sleeper.asleep = False
    assert [pos for pos, _ in pet.threats(snake, level_map)] == [sleeper.center]


def test_in_the_dark_the_pet_sees_only_lit_food_and_walks_to_a_lantern(assets, game):
    level_map = garden(game, "lanterns")
    snake = snake_at((5, 12))
    put(level_map, FallenApple, (12, 17))  # in the dark
    pet = PetController()
    pet.choose(snake, level_map)
    assert pet.choice is None and pet.mood == "wander"
    lantern = put(level_map, Lantern, (8, 10))
    assert pet.choose(snake, level_map) == lantern.center and pet.mood == "light"
    lit = put(level_map, FallenApple, (9, 10))
    pet.choose(snake, level_map)
    assert pet.choice is lit


def test_the_pets_way_is_drawn_to_its_target_and_bends_round_a_new_hedge(assets, game):
    level_map = garden(game)
    snake = snake_at((4, 8))
    snake.controller = pet = PetController()
    apple = put(level_map, FallenApple, (16, 8))
    step(level_map, snake)
    way = pet.intent(snake)
    assert way and (way[-1] - (apple.pos + Vec2(4, 4))).length() < 8
    straight = max(abs(point.y - way[0].y) for point in way)
    for y in range(4, 12):  # a hedge across the way
        level_map.hand.sprouts[(10, y)] = SPROUT
    pet._age = pet.FIELD_EVERY
    step(level_map, snake)
    assert max(abs(point.y - way[0].y) for point in pet.intent(snake)) > straight


# ---- the hand ----------------------------------------------------------------------------------------------------


def test_the_budget_scales_with_the_difficulty(assets, game):
    assert garden(game, "orchard").hand.left == {"tree": 3, "hedge": 6}
    game.profile.difficulty = "easy"
    assert garden(game, "orchard").hand.left == {"tree": 5, "hedge": 10}
    game.profile.difficulty = "nightmare"
    assert garden(game, "orchard").hand.left == {"tree": 3, "hedge": 5}
    assert garden(game).hand.left == {"hedge": 12}  # a level's own override is what it says, not scaled again


def test_nothing_goes_on_walls_terrain_entities_the_snake_or_near_its_head(assets, game):
    level_map = garden(game)
    hand = level_map.hand
    snake = snake_at((30, 18), length=30)
    assert hand.can_place("hedge", (5, 5), snake)
    assert not hand.can_place("hedge", (0, 5), snake)  # the border
    assert not hand.can_place("hedge", (19, 9), snake)  # thorns
    put(level_map, FallenApple, (6, 5))
    assert not hand.can_place("hedge", (6, 5), snake)
    assert not hand.can_place("hedge", (26, 18), snake)  # the body
    assert not hand.can_place("hedge", (32, 18), snake)  # within CLEAR of the head
    assert (center((32, 18)) - snake.head.pos).length() < CLEAR


def test_a_hedge_sprouts_and_grows_into_a_wall_once_the_snake_has_left(assets, game):
    level_map = garden(game)
    hand = level_map.hand
    snake = snake_at((30, 18))
    assert hand.place("hedge", (5, 5), snake)
    assert hand.left["hedge"] == 11 and (5, 5) in hand.sprouts
    assert pyxel.tilemaps[level_map.tm].pget(5, 5) not in WALL_TILES
    step(level_map, snake, round(SPROUT * 24) + 2)
    assert (5, 5) in hand.planted
    assert pyxel.tilemaps[level_map.tm].pget(5, 5) in WALL_TILES
    under = level_map.tile_xy(snake.segs[-1].pos)
    hand.sprouts[under] = 0.0  # under the body: it waits
    step(level_map, snake)
    assert under in hand.sprouts


def test_lifting_gives_the_tool_back_and_leaves_the_levels_walls(assets, game):
    level_map = garden(game)
    hand = level_map.hand
    snake = snake_at((30, 18))
    hand.place("hedge", (5, 5), snake)
    step(level_map, snake, round(SPROUT * 24) + 2)
    assert hand.lift((5, 5), snake)
    assert hand.left["hedge"] == 12 and (5, 5) not in hand.planted
    assert pyxel.tilemaps[level_map.tm].pget(5, 5) not in WALL_TILES
    assert not hand.lift((20, 6), snake)  # the level's own wall
    assert pyxel.tilemaps[level_map.tm].pget(20, 6) in WALL_TILES


def test_placing_waits_for_the_cooldown(assets, game):
    level_map = garden(game)
    snake = snake_at((30, 18))
    assert level_map.hand.place("hedge", (5, 5), snake)
    assert not level_map.hand.place("hedge", (6, 5), snake)
    step(level_map, snake, 5)
    assert level_map.hand.place("hedge", (6, 5), snake)


def test_the_keys_move_the_cursor_and_place(assets, game, monkeypatch):
    level_map = garden(game)
    hand = level_map.hand
    snake = snake_at((30, 18))
    hand.cursor = (5, 5)
    pressed = {pyxel.KEY_RIGHT, pyxel.KEY_SPACE}
    monkeypatch.setattr(pyxel, "btnp", lambda key, hold=0, repeat=0: key in pressed)
    monkeypatch.setattr(pyxel, "btn", lambda key: False)
    HandInput().act(hand, snake, level_map)
    assert hand.cursor == (6, 5) and (6, 5) in hand.sprouts


def test_unknown_tools_fail_to_load(assets, game, monkeypatch):
    level_map = garden(game)
    level_map.cfg.hand = {"shovel": 3}
    with pytest.raises(ValueError):
        Hand(level_map)


# ---- the tools ---------------------------------------------------------------------------------------------------


def test_a_tree_grows_then_drops_a_few_apples_round_it(assets, game):
    level_map = garden(game, "orchard")
    snake = snake_at((30, 12))
    assert level_map.hand.place("tree", (10, 10), snake)
    tree = level_map.hand.placed[0]
    step(level_map, snake, round(Tree.GROW * 24) - 2)
    assert not tree.apples
    step(level_map, snake, round((Tree.DROP * Tree.CROP + 3) * 24))
    assert len(tree.apples) == Tree.CROP
    assert all((apple.pos - tree.pos).length() < 40 for apple in tree.apples)
    level_map.hand.lift((11, 11), snake)
    assert not any(apple.alive for apple in tree.apples) and level_map.hand.left["tree"] == 3


def test_a_hunter_near_a_lure_hunts_it_and_eats_it_up(assets, game):
    level_map = garden(game, "lures")
    snake = snake_at((30, 12))
    lure = put(level_map, Lure, (10, 6))
    level_map.hand.placed.append(lure)
    beetle = put(level_map, Hunter, (14, 6))
    beetle.asleep = False
    beetle.HUNT = (60.0, 60.0)
    beetle._begin("hunt", 60.0)
    for _ in range(24 * 30):
        step(level_map, snake)
        if beetle.state == "hunt":
            beetle.left = 60.0
        if not lure.alive:
            break
    assert not lure.alive  # BITES meals
    assert beetle.alive


def test_thorns_kill_beetles_in_the_garden(assets, game):
    level_map = garden(game)
    snake = snake_at((30, 18))
    beetle = put(level_map, Hunter, (19, 9))  # on a thorn bed
    step(level_map, snake)
    assert not beetle.alive and beetle.killed


def test_a_beetle_shut_in_by_hedges_gives_up(assets, game):
    level_map = garden(game, "lures")
    snake = snake_at((30, 12))
    beetle = put(level_map, Hunter, (10, 16))
    beetle.asleep = False
    for x in range(9, 12):
        for y in range(15, 18):
            if (x, y) != (10, 16):
                level_map.fill((x, y), (0, 8))
    level_map.hand.planted |= {(x, y) for x in range(9, 12) for y in range(15, 18)} - {(10, 16)}
    step(level_map, snake, round(Hunter.PENNED * 24) + 4)
    assert not beetle.alive and beetle.killed


def test_a_lantern_wakes_sleepers_burns_out_and_lifted_is_given_back(assets, game):
    level_map = garden(game, "lanterns")
    snake = snake_at((5, 12))
    hand = level_map.hand
    sleeper = put(level_map, Hunter, (25, 6))
    step(level_map, snake, 24 * 20)
    assert sleeper.asleep  # in the dark garden no nap ends: only light wakes it
    assert hand.place("lantern", (27, 6), snake)
    step(level_map, snake)
    assert not sleeper.asleep
    lantern = hand.placed[0]
    assert hand.lift((27, 6), snake) and hand.left["lantern"] == 4 and not lantern.alive
    hand.cooldown = 0
    hand.place("lantern", (27, 9), snake)
    step(level_map, snake, round(Lantern.OIL * 24) + 2)
    assert not hand.placed and hand.left["lantern"] == 3  # burnt out: gone for good


# ---- the hand bot ------------------------------------------------------------------------------------------------


def test_the_hand_bot_follows_its_plan_at_a_human_pace(assets, game):
    level_map = garden(game)
    snake = snake_at((30, 18))
    level_map.hand.player = HandBot([{"hedge": [[5, 5], [6, 5]]}, {"after": {"seconds": 2}}, {"lift": [[5, 5]]}])
    level_map.hand.cursor = (5, 5)  # (the cursor's way takes time too)
    step(level_map, snake)
    assert set(level_map.hand.sprouts) == {(5, 5)}
    step(level_map, snake, round(HandBot.REACTION * 24) - 2)
    assert (6, 5) not in level_map.hand.sprouts  # not yet: a person needs a moment
    step(level_map, snake, 4)
    assert (6, 5) in level_map.hand.sprouts or (6, 5) in level_map.hand.planted
    step(level_map, snake, 24 * 2)
    assert (5, 5) not in level_map.hand.planted


def test_the_hand_bot_lures_a_beetle_off_the_snake(assets, game):
    level_map = garden(game, "lures")
    snake = snake_at((20, 12))
    level_map.hand.player = HandBot([])
    beetle = put(level_map, Hunter, (17, 14))
    beetle.asleep = False
    step(level_map, snake)
    lures = [ent for ent in level_map.entities if isinstance(ent, Lure)]
    assert lures and level_map.hand.lure_for(beetle) is lures[0]


@pytest.mark.slow
@pytest.mark.parametrize("name", KEEPER)
def test_the_garden_needs_its_keeper(assets, game, name):
    """Left alone, the pet loses a Keeper level at least HELPLESS of the time: the tools are what wins it."""
    rate, _, outcomes = bot.win_rate(game, name, range(4), 240, hand=False)
    assert rate <= 1 - HELPLESS, (name, outcomes)


HELPLESS = 0.75


def test_a_beetle_met_head_first_only_bites_in_the_garden(assets, game):
    level_map = garden(game, "lures")
    snake = snake_at((20, 12), length=20)
    beetle = put(level_map, Hunter, (20, 12))
    beetle.asleep = False
    beetle.on_intersect(snake, level_map)
    assert not level_map.snake_killed and len(snake) == 20 - Hunter.CHUNK


def test_the_pet_leaves_food_a_beetle_guards(assets, game):
    level_map = garden(game)
    snake = snake_at((10, 8))
    put(level_map, FallenApple, (14, 8))
    guard = put(level_map, Hunter, (15, 8))
    guard.asleep = False
    other = put(level_map, FallenApple, (3, 8))
    pet = PetController()
    pet._threats = pet.threats(snake, level_map)
    pet.choose(snake, level_map)
    assert pet.choice is other
