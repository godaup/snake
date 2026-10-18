"""Write the menu theme song into a .pyxres: one sound per voice and a music that plays them together, looped.

The score below is plain text so it can be reviewed and changed here; after writing it can also be edited in Pyxel's
sound and music editors (`pyxel edit`). Each voice is a list of bars of 8 steps (eighth notes):

    c3 e3 ...   note and octave (sharps as c#3)
    -           hold the previous note
    r           rest

    python tools/compose_theme.py src/snake_quest/resources/garden.pyxres

Sound slots and the music number are fixed below; the menu screens play MENU_MUSIC (see states/menu_common.py).
"""

import argparse
from pathlib import Path

import pyxel

from snake_quest.states.menu_common import MENU_MUSIC

FIRST_SOUND = 8  # slots 0-2 hold the sound effects
SPEED = 16  # ticks (1/120 s) per step: ~112 bpm in eighth notes

# chords: C | G | C | G | F | C | G | C
VOICES = {
    "melody": {
        "tone": "s",
        "volume": 5,
        "bars": [
            "c3 - e3 - g3 - e3 -",
            "a3 - g3 e3 d3 - r -",
            "c3 - e3 - g3 - c4 -",
            "b3 a3 g3 - - - r -",
            "a3 - a3 g3 f3 - a3 -",
            "g3 - e3 - c3 - e3 -",
            "f3 - e3 - d3 - b2 -",
            "c3 - - - - - r -",
        ],
    },
    "arpeggio": {
        "tone": "p",
        "volume": 2,
        "bars": [
            "c2 e2 g2 e2 c2 e2 g2 e2",
            "g1 b1 d2 b1 g1 b1 d2 b1",
            "c2 e2 g2 e2 c2 e2 g2 e2",
            "g1 b1 d2 b1 g1 b1 d2 b1",
            "f1 a1 c2 a1 f1 a1 c2 a1",
            "c2 e2 g2 e2 c2 e2 g2 e2",
            "g1 b1 d2 b1 g1 b1 d2 b1",
            "c2 e2 g2 e2 c2 - - r",
        ],
    },
    "bass": {
        "tone": "t",
        "volume": 6,
        "bars": [
            "c1 - g1 - c2 - g1 -",
            "g0 - d1 - g1 - d1 -",
            "c1 - g1 - c2 - g1 -",
            "g0 - d1 - g1 - d1 -",
            "f0 - c1 - f1 - c1 -",
            "c1 - g1 - c2 - g1 -",
            "g0 - d1 - g1 - b0 -",
            "c1 - - - c1 - r -",
        ],
    },
    "drums": {
        "tone": "n",
        "volume": {"kick": 5, "hat": 2},
        # kick is a low noise burst, hat a high one
        "bars": ["a0 r e4 r a0 a0 e4 r"] * 7 + ["a0 r e4 r a0 e4 e4 e4"],
    },
}


def render(voice: dict) -> tuple[str, str, str, str]:
    """Pyxel note, tone, volume and effect strings for one voice. Held notes repeat the pitch; the last step of a
    note fades out, so phrases breathe."""
    steps = " ".join(voice["bars"]).split()
    notes, volumes, effects = [], [], []
    for i, step in enumerate(steps):
        if step == "-":
            step = notes[-1]
        notes.append(step)
        if step == "r":
            volumes.append("0")
            effects.append("n")
            continue
        volume = voice["volume"]
        if isinstance(volume, dict):  # drums: loudness by pitch
            volume = volume["kick"] if step[-1] in "01" else volume["hat"]
        volumes.append(str(volume))
        held_next = i + 1 < len(steps) and steps[i + 1] == "-"
        effects.append("n" if held_next else "f")
    return "".join(notes), voice["tone"] * len(notes), "".join(volumes), "".join(effects)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    resources = parser.parse_args().resources.resolve()  # before pyxel.init() changes the working directory
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    channels = []
    for slot, (name, voice) in enumerate(VOICES.items(), start=FIRST_SOUND):
        pyxel.sounds[slot].set(*render(voice), SPEED)
        channels.append([slot])
        print(f"sound {slot}: {name}, {pyxel.sounds[slot].total_sec():.1f} s")
    pyxel.musics[MENU_MUSIC].set(*channels)
    pyxel.save(str(resources))
    print(f"music {MENU_MUSIC}: {len(channels)} voices -> {resources.name}")


if __name__ == "__main__":
    main()
