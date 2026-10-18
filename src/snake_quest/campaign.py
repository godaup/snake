"""The campaign: arcs of levels in order of play, defined in levels/campaign.yaml."""

from dataclasses import dataclass
from pathlib import Path

import omegaconf
import pyxel

PACKAGE_DIR = Path(__file__).parent
LEVELS_DIR = PACKAGE_DIR / "levels"
RESOURCES_DIR = PACKAGE_DIR / "resources"
CAMPAIGN_FILE = LEVELS_DIR / "campaign.yaml"


@dataclass(frozen=True)
class Level:
    name: str
    number: int  # 1-based position in the whole campaign
    arc: str
    resources: Path  # .pyxres holding this level's tilemaps

    @property
    def path(self) -> Path:
        return LEVELS_DIR / f"{self.name}.yaml"

    def load_tilemaps(self) -> None:
        """Load fresh tilemaps for this level, keeping the shared images, sounds and music."""
        pyxel.load(str(self.resources), exclude_images=True, exclude_sounds=True, exclude_musics=True)


@dataclass(frozen=True)
class Campaign:
    sprites: Path
    levels: tuple[Level, ...]

    def __len__(self) -> int:
        return len(self.levels)

    def level(self, number: int) -> Level:
        """Level by its 1-based campaign number."""
        if not 1 <= number <= len(self.levels):
            raise IndexError(f"no level {number}, the campaign has {len(self.levels)}")
        return self.levels[number - 1]

    def resolve(self, value: str) -> int:
        """Campaign number for a level given by number or by name."""
        if value.isdigit():
            self.level(int(value))
            return int(value)
        for level in self.levels:
            if level.name == value:
                return level.number
        raise KeyError(f"unknown level {value!r}")

    def load_sprites(self) -> None:
        """Load the shared images, sounds and music (and the first arc's tilemaps)."""
        pyxel.load(str(self.sprites))


def load_campaign(path: Path = CAMPAIGN_FILE) -> Campaign:
    cfg = omegaconf.OmegaConf.load(path)
    levels = []
    for arc in cfg.arcs:
        for name in arc.levels:
            levels.append(
                Level(name=name, number=len(levels) + 1, arc=arc.name, resources=RESOURCES_DIR / arc.resources)
            )
    return Campaign(sprites=RESOURCES_DIR / cfg.sprites, levels=tuple(levels))
