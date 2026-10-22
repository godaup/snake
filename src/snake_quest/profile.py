"""The player's saved state: snake palette, difficulty, settings (volumes, display), finished arcs and highscores
(one top-10 table per arc and difficulty: a score counts the points made in one arc), stored as JSON in Pyxel's
per-user data directory."""

import contextlib
import datetime
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from snake_quest.difficulty import DEFAULT as DEFAULT_DIFFICULTY
from snake_quest.difficulty import NAMES as DIFFICULTIES
from snake_quest.palettes import DEFAULT_PALETTE, PALETTES
from snake_quest.sound import VOLUME_STEPS

MAX_HIGHSCORES = 10
SCREEN_MODES = ("CRISP", "SMOOTH", "RETRO")  # pyxel.screen_mode 0-2


@dataclass
class Highscore:
    """One entry of a highscore table: the points made in one arc, the level reached and the date."""

    score: int
    level: int
    date: str  # ISO date
    arc: str = ""  # name of the arc played; empty in profiles from before arcs had their own tables


@dataclass
class Profile:
    """What the game remembers between runs: the snake's palette, the difficulty, the settings, finished and seen arcs
    and the highscores. Loaded and saved as JSON at `path`."""

    palette: str = DEFAULT_PALETTE
    difficulty: str = DEFAULT_DIFFICULTY
    highscores: dict[str, list[Highscore]] = field(default_factory=dict)  # difficulty name -> its arcs' tables
    arcs_done: list[str] = field(default_factory=list)  # names of the arcs played through (checkpoints)
    arcs_seen: list[str] = field(default_factory=list)  # arcs seen open on the map (their fog has lifted)
    music_volume: int = VOLUME_STEPS  # 0..VOLUME_STEPS
    sound_volume: int = VOLUME_STEPS
    fullscreen: bool = False
    screen_mode: int = 0  # index into SCREEN_MODES
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
                arcs_done=[name for name in data.get("arcs_done", []) if isinstance(name, str)],
                arcs_seen=[name for name in data.get("arcs_seen", []) if isinstance(name, str)],
                music_volume=_choice(data.get("music_volume"), range(VOLUME_STEPS + 1), VOLUME_STEPS),
                sound_volume=_choice(data.get("sound_volume"), range(VOLUME_STEPS + 1), VOLUME_STEPS),
                fullscreen=data.get("fullscreen") is True,
                screen_mode=_choice(data.get("screen_mode"), range(len(SCREEN_MODES)), 0),
            )
        except (OSError, ValueError, TypeError):
            profile = cls()
        profile.path = path
        profile.highscores = {name: _capped(table) for name, table in profile.highscores.items()}
        return profile

    def save(self) -> None:
        """Write the profile back to where it was loaded from; quietly does nothing when that fails or it was never
        loaded (tests)."""
        if self.path is None:
            return
        data = {
            "palette": self.palette,
            "difficulty": self.difficulty,
            "arcs_done": self.arcs_done,
            "arcs_seen": self.arcs_seen,
            "music_volume": self.music_volume,
            "sound_volume": self.sound_volume,
            "fullscreen": self.fullscreen,
            "screen_mode": self.screen_mode,
            "highscores": {name: [asdict(h) for h in table] for name, table in self.highscores.items()},
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=1))
        except OSError:
            pass  # e.g. a read-only home directory: the game still works, it just forgets

    def complete_arc(self, name: str) -> None:
        """Remember that an arc was played through, so the next one can be started from the level select. Saves."""
        if name not in self.arcs_done:
            self.arcs_done.append(name)
            self.save()

    def see_arcs(self, names: list[str]) -> None:
        """Remember arcs seen open on the map, so their fog lifts only once. Saves when that changes anything."""
        new = [name for name in names if name not in self.arcs_seen]
        if new:
            self.arcs_seen.extend(new)
            self.save()

    def assign_arcs(self, arc_of: Callable[[int], str]) -> None:
        """Give entries from before arcs had their own tables the arc of the level they reached."""
        for table in self.highscores.values():
            for entry in table:
                if not entry.arc:
                    with contextlib.suppress(IndexError, StopIteration):  # a level the campaign no longer has
                        entry.arc = arc_of(entry.level)
        self.highscores = {name: _capped(table) for name, table in self.highscores.items()}

    def table(self, name: str, arc: str | None = None) -> list[Highscore]:
        """The highscores of `arc` played at difficulty `name`, best first (all arcs' when `arc` is None)."""
        table = self.highscores.get(name, [])
        return table if arc is None else [h for h in table if h.arc == arc]

    def add_highscore(
        self,
        score: int,
        level: int,
        difficulty: str = DEFAULT_DIFFICULTY,
        arc: str = "",
        date: datetime.date | None = None,
    ) -> int | None:
        """Record a score in the table of its arc and difficulty; returns its 1-based rank if it made the table,
        else None. Saves the profile."""
        if score <= 0:
            return None
        entry = Highscore(score=score, level=level, date=(date or datetime.date.today()).isoformat(), arc=arc)
        # stable sort: a tie ranks below the older entry
        ranked = sorted([*self.table(difficulty, arc), entry], key=lambda h: -h.score)
        rank = next(i for i, h in enumerate(ranked) if h is entry)  # identity: an equal old entry may exist
        if rank >= MAX_HIGHSCORES:
            return None
        others = [h for h in self.table(difficulty) if h.arc != arc]
        self.highscores[difficulty] = _capped([*others, *ranked])
        self.save()
        return rank + 1


def _choice(value, allowed: range, default: int) -> int:
    """A saved whole number if it is one of `allowed`, else the default."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value in allowed else default


def _capped(table: list[Highscore]) -> list[Highscore]:
    """Best first, at most MAX_HIGHSCORES per arc."""
    kept: list[Highscore] = []
    for entry in sorted(table, key=lambda h: -h.score):
        if sum(h.arc == entry.arc for h in kept) < MAX_HIGHSCORES:
            kept.append(entry)
    return kept
