"""The player's saved state: highscores and snake palette, stored as JSON in Pyxel's per-user data directory."""

import datetime
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from snake_quest.palettes import DEFAULT_PALETTE, PALETTES

MAX_HIGHSCORES = 10


@dataclass
class Highscore:
    score: int
    level: int
    date: str  # ISO date


@dataclass
class Profile:
    palette: str = DEFAULT_PALETTE
    highscores: list[Highscore] = field(default_factory=list)
    path: Path | None = field(default=None, compare=False, repr=False)

    @classmethod
    def load(cls, path: Path) -> "Profile":
        """Read a profile; a missing or unreadable file gives a fresh one (it is only a convenience, never fatal)."""
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise ValueError("profile must be a JSON object")
            highscores = [Highscore(**entry) for entry in data.get("highscores", [])]
            name = data.get("palette", DEFAULT_PALETTE)
            profile = cls(palette=name if name in PALETTES else DEFAULT_PALETTE, highscores=highscores)
        except (OSError, ValueError, TypeError):
            profile = cls()
        profile.path = path
        profile.highscores = sorted(profile.highscores, key=lambda h: -h.score)[:MAX_HIGHSCORES]
        return profile

    def save(self) -> None:
        if self.path is None:
            return
        data = {"palette": self.palette, "highscores": [asdict(h) for h in self.highscores]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=1))
        except OSError:
            pass  # e.g. a read-only home directory: the game still works, it just forgets

    def add_highscore(self, score: int, level: int, date: datetime.date | None = None) -> int | None:
        """Record a score; returns its 1-based rank if it made the table, else None. Saves the profile."""
        if score <= 0:
            return None
        entry = Highscore(score=score, level=level, date=(date or datetime.date.today()).isoformat())
        # stable sort: a tie ranks below the older entry
        ranked = sorted([*self.highscores, entry], key=lambda h: -h.score)
        rank = next(i for i, h in enumerate(ranked) if h is entry)  # identity: an equal old entry may exist
        if rank >= MAX_HIGHSCORES:
            return None
        self.highscores = ranked[:MAX_HIGHSCORES]
        self.save()
        return rank + 1
