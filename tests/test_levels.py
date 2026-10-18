"""Validate level files without loading them into a Map."""

from pathlib import Path

import omegaconf
import pytest

from .conftest import ROOT

LEVEL_FILES = sorted((ROOT / "levels").glob("*.yaml"))
TILEMAP_SIZE = 256 * 8  # pyxel tilemaps are 256x256 tiles of 8px


@pytest.mark.parametrize("path", LEVEL_FILES, ids=lambda p: p.name)
def test_level_schema(path: Path):
    cfg = omegaconf.OmegaConf.load(path)
    assert cfg.tm in (0, 1, 2, 3, 4, 5, 6, 7)
    assert 0 < cfg.width <= TILEMAP_SIZE
    assert 0 < cfg.height <= TILEMAP_SIZE
    assert 0 <= cfg.start.x < cfg.width
    assert 0 <= cfg.start.y < cfg.height
    # an empty goal would win the level on the first frame
    assert set(cfg.goal) & {"score", "length"}
    assert set(cfg.goal) <= {"score", "length"}


@pytest.mark.parametrize("path", LEVEL_FILES, ids=lambda p: p.name)
def test_level_timers(path: Path):
    cfg = omegaconf.OmegaConf.load(path)
    for name, timer in cfg.get("timers", {}).items():
        assert timer.duration >= 0, name
        assert timer.frequency >= 0, name
        assert timer.fire_n >= 0, name
        assert timer.callback.type in ("spawn", "grow"), name
        if timer.callback.type == "spawn":
            assert timer.callback.entity in ("enemy", "apple", "golden"), name
        else:
            assert isinstance(timer.callback.value, int), name


@pytest.mark.xfail(
    strict=True, reason="levels 4-8 not designed yet; Game.level_up increments by 1, so winning level 3 crashes"
)
def test_levels_are_consecutive():
    numbers = sorted(int(p.stem) for p in LEVEL_FILES if p.stem.isdigit())
    assert numbers == list(range(1, len(numbers) + 1))
