import pytest

from snake_quest.cam import Cam, _follow
from snake_quest.campaign import load_campaign
from snake_quest.map import Map
from snake_quest.snake import Snake
from snake_quest.utils import Vec2

CAMPAIGN = load_campaign()


@pytest.mark.parametrize(
    ("target", "expected"),
    [(50, 0), (500, 160 - 500), (990, 320 - 1000), (160, 0)],
    ids=["near start edge", "middle", "near end edge", "exactly centred at the edge"],
)
def test_follow_centres_but_never_shows_beyond_the_map(target, expected):
    assert _follow(screen=320, world=1000, target=target) == expected


def test_follow_centres_a_small_map():
    assert _follow(screen=320, world=200, target=10) == 60
    assert _follow(screen=320, world=320, target=300) == 0


def cam_for(level_name, game, head):
    level_map = Map(level=CAMPAIGN.level(CAMPAIGN.resolve(level_name)), game=game)
    snake = Snake(pos=head, orient=0, size=2)
    cam = Cam(snake=snake, map=level_map, game=game)
    cam.update()
    return cam


@pytest.mark.parametrize("head", [Vec2(10, 30), Vec2(160, 116), Vec2(310, 205)])
def test_screen_sized_map_never_scrolls(assets, game, head):
    """classic is exactly as large as the play area, so it must stay put wherever the snake is."""
    cam = cam_for("classic", game, head)
    assert (cam.offset.x, cam.offset.y) == (0, 0)


def test_large_map_keeps_head_centred_and_edges_clamped(assets, game):
    header = game.cfg.header.h
    middle = cam_for("maze", game, Vec2(700, header + 320))
    assert middle.offset.x == game.cfg.width / 2 - 700
    assert middle.offset.y == game.cfg.area.h / 2 - 320
    corner = cam_for("maze", game, Vec2(5, header + 5))
    assert (corner.offset.x, corner.offset.y) == (0, 0)
    far = cam_for("maze", game, Vec2(1400, header + 635))
    assert far.offset.x == game.cfg.width - far.map.cfg.width
    assert far.offset.y == game.cfg.area.h - far.map.cfg.height
