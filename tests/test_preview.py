import pyxel

from snake_quest import cli
from snake_quest.campaign import load_campaign
from snake_quest.map import Map
from snake_quest.preview import COL_PATH, COL_PATH_RING, render

PNG_MAGIC = b"\x89PNG"


def test_render_writes_png(assets, tmp_path):
    out = tmp_path / "maze.png"
    campaign = load_campaign()
    render(campaign.level(campaign.resolve("maze")), out)
    assert out.read_bytes().startswith(PNG_MAGIC)


def test_preview_option_is_resolved_before_pyxel_changes_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = cli.build_parser().parse_args(["--level", "maze", "--preview", "out.png"])
    assert args.preview == tmp_path / "out.png"


def test_main_with_preview_does_not_start_the_game(monkeypatch, tmp_path):
    rendered = []
    monkeypatch.setattr(cli, "preview", lambda level, filename: rendered.append((level.name, filename)))
    monkeypatch.setattr("snake_quest.game.Game", lambda **kwargs: rendered.append("game started"))
    cli.main(["--level", "maze", "--preview", str(tmp_path / "maze.png")])
    assert rendered == [("maze", tmp_path / "maze.png")]


def test_path_is_clearly_marked(assets, tmp_path, game):
    """The in-game breadcrumb is a 2x2 dot; the preview must show the path at whole-level scale."""
    campaign = load_campaign()
    level = campaign.level(campaign.resolve("maze"))
    out = tmp_path / "maze.png"
    render(level, out, scale=1)
    img = pyxel.Image.from_image(str(out))
    first = Map(level=level, game=game).path[0]
    x0, y0 = int(first.x), int(first.y) - game.cfg.header.h
    marked = sum(img.pget(x0 + dx, y0 + dy) in (COL_PATH, COL_PATH_RING) for dx in range(8) for dy in range(8))
    assert marked >= 20
