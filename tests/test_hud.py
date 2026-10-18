import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.hud import Hud
from snake_quest.map import Map
from snake_quest.snake import Snake

CAMPAIGN = load_campaign()


def make_hud(game, level_name="classic"):
    level_map = Map(level=CAMPAIGN.level(CAMPAIGN.resolve(level_name)), game=game)
    snake = Snake(pos=level_map.start, orient=0, size=2)
    return Hud(game=game, level_map=level_map, snake=snake)


def test_header_texts(assets, game):
    hud = make_hud(game, "maze")
    game.level_counter = CAMPAIGN.resolve("maze")
    assert hud.level_lines() == (f"LEVEL {game.level_counter}", "The Maze")
    assert hud.right_lines() == ("BEST 0", "LENGTH 1")


def test_best_is_the_better_of_table_and_current_score(assets, game):
    hud = make_hud(game)
    game.profile.add_highscore(500, 1)
    game.score = 120
    assert hud.right_lines()[0] == "BEST 500"
    game.score = 900  # beating the record shows live
    assert hud.right_lines()[0] == "BEST 900"


def test_footer_has_one_entry_per_goal(assets, game):
    hud = make_hud(game)
    game.score = 25
    assert hud.goal_entries() == [("SCORE 25/100", 0.25)]


def test_draw_fills_header_and_footer(assets, game):
    hud = make_hud(game)
    game.score = 50  # half way: the bar is partly filled
    pyxel.cls(0)
    hud.draw()
    header_bg, footer_bg = game.cfg.header.bg, game.cfg.footer.bg
    assert pyxel.pget(game.cfg.width // 4, 1) == header_bg
    footer_y = game.cfg.header.h + game.cfg.area.h
    assert pyxel.pget(game.cfg.width - 2, footer_y + 2) == footer_bg
    # the progress bar is drawn after the status text in the footer
    assert any(pyxel.pget(x, footer_y + 5) == 11 for x in range(0, game.cfg.width))
