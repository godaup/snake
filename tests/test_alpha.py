import datetime

import omegaconf
import pytest

from snake_quest import bot
from snake_quest.bosses import AlphaBoss
from snake_quest.campaign import load_campaign
from snake_quest.entity import Alpha, Hunter, Nest
from snake_quest.goals import load_goals
from snake_quest.map import Map
from snake_quest.snake import Snake, SnakeSeg
from snake_quest.utils import Vec2
from snake_quest.weapons import Gun

CAMPAIGN = load_campaign()
SECOND = datetime.timedelta(seconds=1)


@pytest.fixture
def lair(assets, game):
    game.level_counter = CAMPAIGN.resolve("alpha")
    return Map(level=CAMPAIGN.level(game.level_counter), game=game)


def snake_at(pos: Vec2, length=20) -> Snake:
    snake = Snake(pos=pos, orient=0, size=2)
    snake.grow = 0
    snake.segs += [SnakeSeg(Vec2(pos.x - i * 1.3, pos.y), 2, 0) for i in range(1, length)]
    return snake


def boss_cfg(**values):
    base = {"type": "alpha", "pos": [300, 200], "health": 6, "call": 5, "pack": 2}
    base.update(values)
    base.setdefault("phases", [{"below": 1.0}, {"below": 0.5, "call": 2, "speed": 1.6}])
    return omegaconf.OmegaConf.create(base)


def test_level_puts_the_alpha_in_its_lair(lair):
    boss = lair.boss
    assert isinstance(boss, AlphaBoss) and boss.alpha in lair.entities
    assert boss.alpha.asleep and boss.alpha.w == 16 and boss.alpha.hostile
    assert boss.bar(lair, None) == 1.0
    assert boss.label() == "THE ALPHA I"


def test_the_bar_is_its_health_and_phases_go_by_damage(lair):
    lair.entities.clear()
    boss = AlphaBoss(boss_cfg(), lair)
    snake = snake_at(Vec2(60, 60))
    for _ in range(3):
        boss.alpha.hit(1)
    boss.update(lair, snake, SECOND)
    assert boss.bar(lair, snake) == 0.5 and boss.phase == 1
    assert boss.alpha.SPEED == 1.6
    assert boss.phase_message() == "THE ALPHA CALLS ITS PACK"


def test_it_calls_beetles_out_of_its_burrows_up_to_its_pack(lair):
    lair.entities.clear()
    boss = AlphaBoss(boss_cfg(), lair)
    nest = Nest.at_pos(Vec2(400, 300))
    lair.entities.append(nest)
    snake = snake_at(Vec2(60, 60))
    for _ in range(4):
        boss.left = 0
        boss.update(lair, snake, SECOND)
    beetles = [ent for ent in lair.entities if type(ent) is Hunter]
    assert len(beetles) == 2 and all(beetle.pos == nest.pos and beetle.state == "hunt" for beetle in beetles)


def test_no_burrows_no_reinforcements(lair):
    lair.entities.clear()
    boss = AlphaBoss(boss_cfg(), lair)
    boss.left = 0
    boss.update(lair, snake_at(Vec2(60, 60)), SECOND)
    assert lair.entities == [boss.alpha]


def test_wakes_when_the_snake_comes_near_or_its_lair_time_is_over(lair):
    alpha = Alpha.at_pos(Vec2(300, 200))
    alpha.update(snake_at(Vec2(60, 60)), lair)
    assert alpha.asleep
    alpha.update(snake_at(alpha.center + Vec2(-Alpha.WAKE + 10, 0)), lair)
    assert not alpha.asleep
    late = Alpha.at_pos(Vec2(300, 200))
    late.left = 0.01
    late.update(snake_at(Vec2(60, 60)), lair)
    assert not late.asleep


def test_boss_goal_is_won_when_the_alpha_falls(lair):
    (goal,) = load_goals({"boss": "defeated"}, map=lair)
    assert goal.describe() == "Defeat the boss" and goal.status(lair, None) == "BOSS 100%"
    assert not goal.done(lair, None)
    lair.boss.alpha.hit(lair.boss.full)
    assert goal.done(lair, None) and goal.progress(lair, None) == 1.0


def test_harder_difficulties_make_it_tougher(assets, game):
    game.level_counter = CAMPAIGN.resolve("alpha")
    medium = Map(level=CAMPAIGN.level(game.level_counter), game=game).boss.full
    game.profile.difficulty = "nightmare"
    assert Map(level=CAMPAIGN.level(game.level_counter), game=game).boss.full > medium


def test_bot_goes_for_the_alpha_once_armed(lair):
    snake = snake_at(Vec2(100, 100), length=30)
    snake.weapon = Gun(ammo=10)
    assert bot.target(snake, lair) == lair.boss.alpha.center
