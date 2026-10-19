import datetime

import pytest
import pyxel

from snake_quest import game as game_module
from snake_quest.campaign import load_campaign
from snake_quest.palettes import PALETTES
from snake_quest.states import StateID
from snake_quest.states.credits import CREDITS, LINE_H, CreditsStateHandler
from snake_quest.states.customize import CustomizeStateHandler
from snake_quest.states.death import DeathStateHandler
from snake_quest.states.highscores import HighscoresStateHandler
from snake_quest.states.menu import MenuStateHandler
from snake_quest.states.menu_common import MENU_MUSIC, Backdrop, Title
from snake_quest.states.running import RunningStateHandler

FRAME = datetime.timedelta(seconds=1 / 24)


def test_menu_items_lead_where_they_say(game):
    menu = MenuStateHandler(game)
    actions = dict(menu.items)
    actions["PLAY"]()
    assert game.restarts == 1
    actions["HIGHSCORES"]()
    actions["CUSTOMIZE"]()
    actions["CREDITS"]()
    assert game.requested_states == [StateID.HIGHSCORES, StateID.CUSTOMIZE, StateID.CREDITS]
    assert "QUIT" in actions


@pytest.mark.parametrize(
    "handler_cls", [MenuStateHandler, HighscoresStateHandler, CustomizeStateHandler, CreditsStateHandler]
)
def test_menu_screens_share_theme_and_backdrop(assets, game, handler_cls):
    handler = handler_cls(game)
    assert handler.get_music() == MENU_MUSIC
    assert handler.is_visible()
    t = game.backdrop.t
    game.dt = FRAME
    handler.update()
    handler.draw()
    assert game.backdrop.t > t  # the shared animation advanced


def test_levels_do_not_play_the_menu_theme(assets, game):
    assert RunningStateHandler(game).get_music() != MENU_MUSIC


def test_theme_song_is_in_the_sprites_file(assets):
    seqs = pyxel.musics[MENU_MUSIC].seqs
    assert len([seq for seq in seqs if list(seq)]) == 4
    durations = {round(pyxel.sounds[list(seq)[0]].total_sec(), 2) for seq in seqs}
    assert len(durations) == 1  # voices loop in sync
    assert durations.pop() > 4


def test_highscore_rows(game):
    screen = HighscoresStateHandler(game)
    assert screen.rows() == []
    game.profile.add_highscore(1234, 4, date=datetime.date(2026, 10, 18))
    (row,) = screen.rows()
    assert "1234" in row and "LEVEL 4" in row and "2026-10-18" in row


def test_customize_cycles_palettes_and_recolors_backdrop(game):
    screen = CustomizeStateHandler(game)
    names = list(PALETTES)
    screen.choose(screen.index + 1)
    assert game.profile.palette == names[1]
    assert game.backdrop.snake.head.col == PALETTES[names[1]].head
    screen.choose(-1)  # wraps around
    assert game.profile.palette == names[-1]


def test_credits_scroll_loops_and_restart_on_enter(game):
    screen = CreditsStateHandler(game)
    game.dt = datetime.timedelta(seconds=0.1)
    for _ in range(10):
        screen.update()
    assert screen.offset > 0
    screen.on_enter()
    assert screen.offset == 0
    screen.offset = screen.height + len(CREDITS) * LINE_H + 1
    screen.update()
    assert screen.offset < LINE_H  # looped back to the start


def test_game_over_records_highscore(game):
    death = DeathStateHandler(game)
    game.score = 42
    game.level_counter = 2
    death.on_enter()
    assert death.rank == 1
    assert "NEW MEDIUM HIGHSCORE #1!" in death.wdg.text
    assert "SCORE 42" in death.wdg.text
    assert game.profile.table("medium")[0].score == 42


def test_game_over_without_points_records_nothing(game):
    death = DeathStateHandler(game)
    death.on_enter()
    assert death.rank is None
    assert game.profile.table("medium") == []
    assert not any("HIGHSCORE" in line for line in death.wdg.text)


def test_demo_snake_stays_on_screen(game):
    backdrop = Backdrop(game)
    for _ in range(24 * 60):  # one minute
        backdrop.update(FRAME)
        head = backdrop.snake.head.pos
        assert 0 <= head.x <= backdrop.width and 0 <= head.y <= backdrop.height


def test_title_draws(assets):
    Title("SNAKE QUEST").draw(160, 40, t=1.0)


class FakeHandler:
    def __init__(self, music):
        self.music = music
        self.entered = 0

    def is_visible(self):
        return True

    def get_music(self):
        return self.music

    def on_enter(self):
        self.entered += 1


def test_music_only_restarts_when_it_changes():
    played = []
    instance = game_module.Game.__new__(game_module.Game)
    instance.music = None
    instance.sm = type(
        "SM", (), {"interrupt": lambda self: played.append("stop"), "play": lambda self, music: played.append(music)}
    )()
    instance._state_handlers = {
        StateID.MENU: FakeHandler(MENU_MUSIC),
        StateID.CREDITS: FakeHandler(MENU_MUSIC),
        StateID.RUNNING: FakeHandler(0),
    }
    instance.change_state(StateID.MENU)
    instance.change_state(StateID.CREDITS)  # same theme: keeps playing
    instance.change_state(StateID.RUNNING)
    assert played == ["stop", MENU_MUSIC, "stop", 0]
    assert instance._state_handlers[StateID.CREDITS].entered == 1


def test_campaign_still_loads():
    assert len(load_campaign()) >= 1
