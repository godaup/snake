import datetime

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.goals import load_goals
from snake_quest.states import StateID
from snake_quest.states.countdown import CountdownHandler
from snake_quest.states.level_complete import LevelCompleteStateHandler, format_time
from snake_quest.states.mission import MissionStateHandler
from snake_quest.states.pause import PauseStateHandler
from snake_quest.states.running import RunningStateHandler

CAMPAIGN = load_campaign()


@pytest.mark.parametrize(
    "handler_cls", [MissionStateHandler, CountdownHandler, LevelCompleteStateHandler, PauseStateHandler]
)
def test_overlays_draw_the_level_dimmed_underneath(assets, game, handler_cls):
    handler = handler_cls(game)
    handler.on_enter()
    pyxel.cls(7)
    handler.draw()
    # the HUD of the level underneath is drawn, so the header is not the cleared colour
    assert pyxel.pget(game.cfg.width // 4, 1) == game.cfg.header.bg


def test_mission_lists_level_intro_and_goals(assets, game):
    content = MissionStateHandler(game).lines()
    assert content["kicker"] == f"LEVEL 1 OF {CAMPAIGN.story_last}  -  {CAMPAIGN.level(1).arc.upper()}  -  MEDIUM"
    assert content["title"] == "CLASSIC"
    assert content["intro"] == ["Eat the apples, don't bite your tail."]
    assert content["goals"] == ["Score 20 points"]


def test_running_hands_over_to_level_complete_once(assets, game):
    running = game.running_handler
    running.intro_pending = False
    running.map.goals = load_goals({"length": 1}, map=running.map)  # met right away
    game.dt = datetime.timedelta(seconds=1 / 24)
    running.update()
    running.update()
    assert game.requested_states == [StateID.LEVEL_COMPLETE]
    assert game.level_ups == 0  # the next level only starts from the level complete screen


def test_level_complete_snapshots_stats(assets, game):
    running = game.running_handler
    running.elapsed = 83.4
    game.score = running.score_at_start + 120
    screen = LevelCompleteStateHandler(game)
    screen.on_enter()
    assert screen.stats.goals == ["SCORE 120/20"]
    assert dict(screen.stat_rows()) == {"TIME": "1:23", "POINTS": "+120", "LENGTH": "1", "SCORE": "00120"}
    assert not screen.stats.last_level
    game.score += 50  # later changes don't alter the shown stats
    assert dict(screen.stat_rows())["SCORE"] == "00120"


def test_level_complete_knows_the_last_level(assets, game):
    game.level_counter = len(CAMPAIGN)
    screen = LevelCompleteStateHandler(game)
    screen.on_enter()
    assert screen.stats.last_level


@pytest.mark.parametrize(("seconds", "text"), [(0, "0:00"), (59.9, "0:59"), (61, "1:01"), (600, "10:00")])
def test_format_time(seconds, text):
    assert format_time(seconds) == text


def test_pause_redraws_everything_so_no_cursor_trail_remains(assets, game):
    """Pyxel draws the mouse cursor into the screen image; the pause screen shows the cursor, so it must repaint the
    whole screen every frame or old cursor images stay behind."""
    pause = PauseStateHandler(game)
    pause.draw()
    x, y = 40, game.cfg.header.h + 40  # somewhere in the dimmed play area, outside the panel
    pyxel.pset(x, y, 14)  # what an old cursor image would leave
    pause.draw()
    assert pyxel.pget(x, y) != 14


def test_running_counts_only_playing_time(assets, game):
    running = RunningStateHandler(game)
    game.dt = datetime.timedelta(seconds=0.5)
    running.update()
    running.update()
    assert running.elapsed == pytest.approx(1.0)


def test_finishing_an_arc_records_its_score(assets, game):
    arc = CAMPAIGN.arcs[0]
    game.level_counter = arc.last
    game.score = 300
    screen = LevelCompleteStateHandler(game)
    screen.on_enter()
    assert screen.stats.rank == 1
    assert dict(screen.stat_rows())["HIGHSCORE"] == "NEW #1"
    assert [h.score for h in game.profile.table("medium", arc.name)] == [300]


def test_levels_within_an_arc_record_nothing(assets, game):
    game.score = 300
    LevelCompleteStateHandler(game).on_enter()
    assert game.profile.table("medium") == []
