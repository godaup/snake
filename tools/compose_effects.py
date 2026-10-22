"""Write the sound effects into a .pyxres: one sound per game event, in the slots named by EFFECTS in sound.py.

Like the menu theme (tools/compose_theme.py) the effects are plain text so they can be reviewed and changed here, and
edited further in Pyxel's sound editor (`pyxel edit`) afterwards. Each effect is a list of steps:

    c3 e3 ...   note and octave (sharps as c#3)
    -           hold the previous note
    r           rest

with a tone (t triangle, s square, p pulse, n noise), a volume (0-7), a speed (ticks of 1/120 s per step) and an
optional Pyxel effect for every step but the last (n none, s slide, v vibrato); the last step always fades out.

    python tools/compose_effects.py src/snake_quest/resources/garden.pyxres
"""

import argparse
from pathlib import Path

import pyxel

from snake_quest.sound import EFFECTS

SOUNDS = {
    "eat": {"steps": "c3 e3 g3", "tone": "p", "volume": 5, "speed": 4},
    "golden": {"steps": "c3 e3 g3 c4 e4 g4 c4 g4", "tone": "p", "volume": 5, "speed": 4},
    "speed": {"steps": "c2 c4 -", "tone": "s", "volume": 4, "speed": 7, "effect": "s"},
    "firefly": {"steps": "e4 b4 g#4 e4 b4 -", "tone": "t", "volume": 4, "speed": 6, "effect": "v"},
    "portal": {"steps": "g3 c2 g4 -", "tone": "t", "volume": 5, "speed": 7, "effect": "s"},
    "hurt": {"steps": "c2 a1 -", "tone": "n", "volume": 6, "speed": 6},
    "death": {"steps": "g2 f#2 f2 e2 d#2 d2 c#2 c2 - -", "tone": "s", "volume": 5, "speed": 10, "effect": "v"},
    "win": {"steps": "c3 e3 g3 c4 - r g3 c4 - -", "tone": "p", "volume": 5, "speed": 9},
    "shoot": {"steps": "a4 e4 a3", "tone": "s", "volume": 4, "speed": 2, "effect": "s"},
    "pickup": {"steps": "g3 c4 e4 g4", "tone": "p", "volume": 5, "speed": 4},
    "boom": {"steps": "c2 g1 d1 a0 - -", "tone": "n", "volume": 7, "speed": 5, "effect": "s"},
    "plant": {"steps": "e3 c3 g2", "tone": "n", "volume": 3, "speed": 4},
    "lift": {"steps": "g2 c3 e3", "tone": "n", "volume": 3, "speed": 4},
    "caw": {"steps": "a3 g3 d3 - r a3 f3 c3 -", "tone": "s", "volume": 4, "speed": 5, "effect": "s"},
}


def render(sound: dict) -> tuple[str, str, str, str]:
    """Pyxel note, tone, volume and effect strings for one effect."""
    steps = sound["steps"].split()
    notes, volumes, effects = [], [], []
    for i, step in enumerate(steps):
        if step == "-":
            step = notes[-1]
        notes.append(step)
        last = i == len(steps) - 1
        volumes.append("0" if step == "r" else str(sound["volume"]))
        effects.append("f" if last else sound.get("effect", "n"))
    return "".join(notes), sound["tone"] * len(notes), "".join(volumes), "".join(effects)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    resources = parser.parse_args().resources.resolve()  # before pyxel.init() changes the working directory
    assert set(SOUNDS) == set(EFFECTS), "every effect in sound.py needs a score here"
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    for name, slot in EFFECTS.items():
        pyxel.sounds[slot].set(*render(SOUNDS[name]), SOUNDS[name]["speed"])
        print(f"sound {slot}: {name}, {pyxel.sounds[slot].total_sec():.2f} s")
    pyxel.save(str(resources))


if __name__ == "__main__":
    main()
