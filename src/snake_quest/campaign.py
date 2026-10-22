"""The campaign: arcs of levels in order of play, defined in levels/campaign.yaml."""

from dataclasses import dataclass, field
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
    music: str = "garden"  # its arc's music (see sound.MUSIC); a level file may name another (`music: boss`)
    bonus: bool = False  # in a bonus arc (`bonus: true`), played after the story's end

    @property
    def path(self) -> Path:
        return LEVELS_DIR / f"{self.name}.yaml"

    def load_tilemaps(self) -> None:
        """Load fresh tilemaps for this level, keeping the shared images, sounds and music."""
        pyxel.load(str(self.resources), exclude_images=True, exclude_sounds=True, exclude_musics=True)


@dataclass(frozen=True)
class Arc:
    name: str
    first: int  # campaign numbers of its first and last level
    last: int
    theme: dict = field(default_factory=dict, compare=False)  # its look on the overview map (campaign.yaml `map`)


@dataclass(frozen=True)
class Campaign:
    sprites: Path
    levels: tuple[Level, ...]
    themes: dict[str, dict] = field(default_factory=dict, compare=False)  # arc name -> its `map` section

    def __len__(self) -> int:
        return len(self.levels)

    @property
    def story_last(self) -> int:
        """Number of the story's last level (the bonus arcs come after it)."""
        return max((level.number for level in self.levels if not level.bonus), default=len(self.levels))

    @property
    def endings(self) -> set[int]:
        """Levels after which the victory screen shows: the story's last and the very last."""
        return {self.story_last, len(self.levels)}

    def level(self, number: int) -> Level:
        """Level by its 1-based campaign number."""
        if not 1 <= number <= len(self.levels):
            raise IndexError(f"no level {number}, the campaign has {len(self.levels)}")
        return self.levels[number - 1]

    @property
    def arcs(self) -> list[Arc]:
        """The arcs in order of play."""
        arcs: list[Arc] = []
        for level in self.levels:
            if arcs and arcs[-1].name == level.arc:
                arcs[-1] = Arc(level.arc, arcs[-1].first, level.number, arcs[-1].theme)
            else:
                arcs.append(Arc(level.arc, level.number, level.number, self.themes.get(level.arc, {})))
        return arcs

    def arc_of(self, number: int) -> Arc:
        """The arc of the level with this campaign number."""
        return next(arc for arc in self.arcs if arc.first <= number <= arc.last)

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
    themes = {arc.name: omegaconf.OmegaConf.to_container(arc.map) if "map" in arc else {} for arc in cfg.arcs}
    for arc in cfg.arcs:
        for name in arc.levels:
            levels.append(
                Level(
                    name=name,
                    number=len(levels) + 1,
                    arc=arc.name,
                    resources=RESOURCES_DIR / arc.resources,
                    music=arc.get("music", "garden"),
                    bonus=arc.get("bonus", False),
                )
            )
    return Campaign(sprites=RESOURCES_DIR / cfg.sprites, levels=tuple(levels), themes=themes)
