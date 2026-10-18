"""Validate level files without loading them into a Map."""

from pathlib import Path

import omegaconf
import pytest

from snake_quest.campaign import CAMPAIGN_FILE, LEVELS_DIR, load_campaign
from snake_quest.goals import GOALS

LEVEL_FILES = sorted(p for p in LEVELS_DIR.glob("*.yaml") if p != CAMPAIGN_FILE)
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
    assert cfg.goal
    assert set(cfg.goal) <= set(GOALS)


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


def test_campaign_references_existing_files():
    campaign = load_campaign()
    assert campaign.sprites.is_file()
    for level in campaign.levels:
        assert level.path.is_file(), level.name
        assert level.resources.is_file(), level.name


def test_campaign_levels_are_unique_and_numbered():
    levels = load_campaign().levels
    assert len({level.name for level in levels}) == len(levels)
    assert [level.number for level in levels] == list(range(1, len(levels) + 1))


def test_every_level_file_is_in_the_campaign():
    """Level files outside the campaign are dead weight, except scratch files starting with '_'."""
    in_campaign = {level.name for level in load_campaign().levels}
    on_disk = {p.stem for p in LEVEL_FILES if not p.stem.startswith("_")}
    assert on_disk == in_campaign


def test_resolve_by_number_and_name():
    campaign = load_campaign()
    assert campaign.resolve("1") == 1
    assert campaign.resolve("maze") == campaign.levels[[lv.name for lv in campaign.levels].index("maze")].number
    with pytest.raises(KeyError):
        campaign.resolve("nope")
    with pytest.raises(IndexError):
        campaign.resolve(str(len(campaign) + 1))
