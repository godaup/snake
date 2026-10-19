"""Bosses, built from the optional `boss` section of a level file: `boss: {type: <key>, phases: [...], ...}`.

A boss has a bar (0..1, drawn at the top of the play area by the HUD) and phases. By default a phase starts `after`
seconds of play; each phase is a dict of settings the boss reads through `self.setting(name)`, falling back to the
boss section itself. The level's goals decide when it is won (e.g. `hold_length` for The Hunger)."""

import datetime
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake

ROMAN = ["I", "II", "III", "IV", "V"]


class Boss(ABC):
    key: ClassVar[str]
    title: ClassVar[str]  # upper case, shown on the bar
    # settings harder difficulties raise (pressure), lower (relief) or apply to light radii, see difficulty.py
    pressure: ClassVar[tuple[str, ...]] = ()
    relief: ClassVar[tuple[str, ...]] = ()
    lights: ClassVar[tuple[str, ...]] = ()

    def __init__(self, cfg, map: "Map"):
        self.cfg = cfg
        self.phases: list = list(cfg.get("phases", [{"after": 0}]))
        self.phase = 0
        self.elapsed = 0.0  # seconds of play
        self.since_phase = 0.0  # seconds since the current phase started, e.g. for the HUD's banner

    def setting(self, name: str):
        """A value from the current phase, or from the boss section when the phase doesn't set it."""
        phase = self.phases[self.phase]
        return phase[name] if name in phase else self.cfg[name]

    def update(self, map: "Map", snake: "Snake", dt: datetime.timedelta) -> None:
        seconds = dt.total_seconds()
        self.elapsed += seconds
        self.since_phase += seconds
        if self.phase + 1 < len(self.phases) and self.next_phase_due(map, snake):
            self.phase += 1
            self.since_phase = 0.0
            self.on_phase(map, snake)
        self.act(map, snake, seconds)

    def next_phase_due(self, map: "Map", snake: "Snake") -> bool:
        """Whether to move on to the next phase; by time unless a boss decides otherwise (e.g. by its health)."""
        return self.elapsed >= self.phases[self.phase + 1]["after"]

    def on_phase(self, map: "Map", snake: "Snake") -> None:  # noqa: B027 (optional hook)
        """Called when a new phase starts."""

    @abstractmethod
    def act(self, map: "Map", snake: "Snake", seconds: float) -> None:
        """What the boss does every frame."""

    @abstractmethod
    def bar(self, map: "Map", snake: "Snake") -> float:
        """Fill of the boss bar, 0..1."""

    def label(self) -> str:
        """Text next to the bar: the title, with the phase number once there is more than one phase."""
        return self.title if len(self.phases) == 1 else f"{self.title} {ROMAN[self.phase]}"

    def phase_message(self) -> str | None:
        """Shown big for a moment when a phase starts (not the first)."""
        return None


class Hunger(Boss):
    """The Hunger (level 5): hunger rises all the time and the snake shrinks the hungrier it is, down to nothing;
    every meal (an entity eaten, not killed) eases it. The hungrier, the smaller the light around the head.

        boss: {type: hunger, rise: 0.05, meal: 0.4, starve: 3, light: [48, 20], phases: [{after: 0}, ...]}

    `rise`: hunger per second, `meal`: hunger a meal takes away, `starve`: segments lost per second at full hunger,
    `light`: radius of the head's light when full and when starving (needs `darkness`)."""

    key = "hunger"
    title = "THE HUNGER"
    pressure = ("rise", "starve")
    relief = ("meal",)
    lights = ("light",)

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        self.hunger = 0.0
        self.eaten = map.eaten
        self.starving = 0.0  # segments lost but not cut yet (shrinking is slower than one per frame)

    def act(self, map, snake, seconds):
        meals, self.eaten = map.eaten - self.eaten, map.eaten
        self.hunger = min(1.0, max(0.0, self.hunger + self.setting("rise") * seconds - meals * self.setting("meal")))
        self.starving += self.hunger * self.setting("starve") * seconds
        while self.starving >= 1:
            self.starving -= 1
            if not snake.cut(1):
                map.snake_killed = True  # starved
                break
        if map.darkness is not None:
            full, starving = self.setting("light")
            map.darkness.light = full + (starving - full) * self.hunger

    def bar(self, map, snake):
        return self.hunger

    def phase_message(self):
        return "THE HUNGER GROWS"


BOSSES: dict[str, type[Boss]] = {cls.key: cls for cls in [Hunger]}


def load_boss(cfg, map: "Map") -> Boss:
    if cfg.type not in BOSSES:
        raise ValueError(f"unknown boss type {cfg.type!r}, expected one of {sorted(BOSSES)}")
    return BOSSES[cfg.type](cfg, map)
