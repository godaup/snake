import datetime

from snake_quest.palettes import DEFAULT_PALETTE, PALETTES, palette
from snake_quest.profile import MAX_HIGHSCORES, Profile
from snake_quest.snake import Snake
from snake_quest.utils import Vec2

DAY = datetime.date(2026, 10, 18)


def test_missing_file_gives_fresh_profile(tmp_path):
    profile = Profile.load(tmp_path / "nope.json")
    assert profile.palette == DEFAULT_PALETTE
    assert profile.table("medium") == []


def test_round_trip(tmp_path):
    path = tmp_path / "sub" / "profile.json"
    profile = Profile.load(path)
    profile.palette = "Ocean"
    profile.add_highscore(500, 3, date=DAY)
    loaded = Profile.load(path)
    assert loaded.palette == "Ocean"
    assert [(h.score, h.level, h.date) for h in loaded.table("medium")] == [(500, 3, "2026-10-18")]


def test_corrupt_or_odd_files_never_crash(tmp_path):
    path = tmp_path / "profile.json"
    for content in ("{not json", "[]", '{"highscores": [{"bogus": 1}]}'):
        path.write_text(content)
        assert Profile.load(path).table("medium") == []
    path.write_text('{"palette": "Neon"}')  # a palette that no longer exists
    assert Profile.load(path).palette == DEFAULT_PALETTE


def test_ranking():
    profile = Profile()
    assert profile.add_highscore(100, 1, date=DAY) == 1
    assert profile.add_highscore(300, 2, date=DAY) == 1
    assert profile.add_highscore(200, 2, date=DAY) == 2
    assert [h.score for h in profile.table("medium")] == [300, 200, 100]


def test_tie_ranks_below_the_older_score():
    profile = Profile()
    profile.add_highscore(100, 1, date=DAY)
    assert profile.add_highscore(100, 1, date=DAY) == 2  # identical entry, still recorded
    assert len(profile.table("medium")) == 2


def test_table_is_capped():
    profile = Profile()
    for score in range(10, 10 * (MAX_HIGHSCORES + 1), 10):
        profile.add_highscore(score, 1, date=DAY)
    assert len(profile.table("medium")) == MAX_HIGHSCORES
    assert profile.add_highscore(5, 1, date=DAY) is None  # too low for a full table
    assert profile.add_highscore(1000, 1, date=DAY) == 1
    assert len(profile.table("medium")) == MAX_HIGHSCORES


def test_zero_scores_are_not_recorded():
    profile = Profile()
    assert profile.add_highscore(0, 1) is None
    assert profile.table("medium") == []


def test_palettes_use_pyxel_colours():
    assert DEFAULT_PALETTE in PALETTES
    for p in PALETTES.values():
        assert all(0 <= col <= 15 for col in (p.head, *p.body))
        assert p.body
    assert palette("does not exist") == PALETTES[DEFAULT_PALETTE]


def test_snake_recolor():
    snake = Snake(pos=Vec2(0, 0), orient=0, size=2)
    snake.grow = 0
    snake.segs.append(snake.segs[0].__class__(Vec2(1, 0), 2, snake.body_color(1)))
    ocean = PALETTES["Ocean"]
    snake.recolor(ocean)
    assert snake.head.col == ocean.head
    assert snake.segs[1].col == ocean.body[1]
