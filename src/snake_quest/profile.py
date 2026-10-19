"""The player's saved state: snake palette, difficulty and one highscore table per difficulty, stored as JSON in
Pyxel's per-user data directory."""

import datetime
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from snake_quest.difficulty import DEFAULT as DEFAULT_DIFFICULTY
from snake_quest.difficulty import NAMES as DIFFICULTIES
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
    difficulty: str = DEFAULT_DIFFICULTY
    highscores: dict[str, list[Highscore]] = field(default_factory=dict)  # difficulty name -> its table
    path: Path | None = field(default=None, compare=False, repr=False)

    @classmethod
    def load(cls, path: Path) -> "Profile":
        """Read a profile; a missing or unreadable file gives a fresh one (it is only a convenience, never fatal)."""
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise ValueError("profile must be a JSON object")
            tables = data.get("highscores", {})
            if isinstance(tables, list):  # before difficulties there was one table, played at medium
                tables = {DEFAULT_DIFFICULTY: tables}
            highscores = {
                name: [Highscore(**entry) for entry in entries]
                for name, entries in tables.items()
                if name in DIFFICULTIES
            }
            name = data.get("palette", DEFAULT_PALETTE)
            chosen = data.get("difficulty", DEFAULT_DIFFICULTY)
            profile = cls(
                palette=name if name in PALETTES else DEFAULT_PALETTE,
                difficulty=chosen if chosen in DIFFICULTIES else DEFAULT_DIFFICULTY,
                highscores=highscores,
            )
        except (OSError, ValueError, TypeError):
            profile = cls()
        profile.path = path
        profile.highscores = {
            name: sorted(table, key=lambda h: -h.score)[:MAX_HIGHSCORES] for name, table in profile.highscores.items()
        }
        return profile

    def save(self) -> None:
        if self.path is None:
            return
        data = {
            "palette": self.palette,
            "difficulty": self.difficulty,
            "highscores": {name: [asdict(h) for h in table] for name, table in self.highscores.items()},
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=1))
        except OSError:
            pass  # e.g. a read-only home directory: the game still works, it just forgets

    def table(self, name: str) -> list[Highscore]:
        """The highscores played at difficulty `name`, best first."""
        return self.highscores.get(name, [])

    def add_highscore(
        self, score: int, level: int, difficulty: str = DEFAULT_DIFFICULTY, date: datetime.date | None = None
    ) -> int | None:
        """Record a score in the table of its difficulty; returns its 1-based rank if it made the table, else None.
        Saves the profile."""
        if score <= 0:
            return None
        entry = Highscore(score=score, level=level, date=(date or datetime.date.today()).isoformat())
        # stable sort: a tie ranks below the older entry
        ranked = sorted([*self.table(difficulty), entry], key=lambda h: -h.score)
        rank = next(i for i, h in enumerate(ranked) if h is entry)  # identity: an equal old entry may exist
        if rank >= MAX_HIGHSCORES:
            return None
        self.highscores[difficulty] = ranked[:MAX_HIGHSCORES]
        self.save()
        return rank + 1
