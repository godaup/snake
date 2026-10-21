"""Write the level music into the sprites .pyxres: per track three voices (lead, bass, drums) on channels 0-2, looped;
channel 3 stays free for the sound effects.

The scores are plain text, written like the menu theme's (see compose_theme.py): bars of 8 steps (eighth notes) with
`c3`-style notes (sharps as `c#3`, octaves 0-4), `-` to hold, `r` to rest. Each track names its sections and a `form`,
the order they play in; a voice may leave a section out to rest through it.

    python tools/compose_music.py src/snake_quest/resources/garden.pyxres

Music numbers come from sound.MUSIC; the sound slots from FIRST_SOUND on (three per track) are this tool's.
"""

import argparse
from pathlib import Path

import pyxel
from compose_theme import render

from snake_quest.sound import MUSIC, MUSIC_CHANNELS

FIRST_SOUND = 16  # slots 0-7 and 12-14 hold the effects, 8-11 the menu theme
REST_BAR = "r r r r r r r r"

TRACKS = {
    # The Garden: light and bouncy, G major. A: G Em C D G Em Am-D G, A2: G Em C D C G D G, B: C D Bm Em C G/B Am D
    "garden": {
        "speed": 15,  # ticks per eighth: 120 bpm
        "form": ["a", "a2", "b", "a"],
        "voices": {
            "lead": {
                "tone": "p",
                "volume": 2,
                "sections": {
                    "a": [
                        "d4 - b3 - g3 - b3 d4",
                        "e4 - - d4 b3 - g3 -",
                        "e3 g3 c4 - e4 - c4 -",
                        "d4 - a3 - f#3 - a3 -",
                        "g3 b3 d4 g4 - - d4 -",
                        "e4 d4 b3 - g3 - e3 -",
                        "a3 - c4 - f#3 - a3 -",
                        "g3 - - - r - r -",
                    ],
                    "a2": [
                        "d4 - b3 - g3 - b3 d4",
                        "g4 - - e4 d4 - b3 -",
                        "c4 - e4 - g4 - e4 c4",
                        "d4 - - - a3 - - -",
                        "e4 - d4 c4 b3 - c4 -",
                        "d4 - b3 g3 b3 - d4 -",
                        "a3 - b3 - c4 - f#3 -",
                        "g3 - - - - - r -",
                    ],
                    "b": [
                        "e4 - - g4 e4 - c4 -",
                        "f#4 - - a4 f#4 - d4 -",
                        "d4 - b3 - f#3 - b3 -",
                        "e4 - - - g4 - e4 -",
                        "c4 - e4 - g4 - - -",
                        "b3 - d4 - g4 - d4 -",
                        "c4 - a3 - e3 - a3 -",
                        "d4 - f#4 - a4 - r -",
                    ],
                },
            },
            "bass": {
                "tone": "t",
                "volume": 3,
                "sections": {
                    "a": [
                        "g1 r d2 r g1 r d2 r",
                        "e1 r b1 r e1 r b1 r",
                        "c1 r g1 r c2 r g1 r",
                        "d1 r a1 r d2 r a1 r",
                        "g1 r d2 r g1 r d2 r",
                        "e1 r b1 r e1 r b1 r",
                        "a0 r e1 r d1 r a1 r",
                        "g1 r d2 r g1 - - r",
                    ],
                    "a2": [
                        "g1 r d2 r g1 r d2 r",
                        "e1 r b1 r e1 r b1 r",
                        "c1 r g1 r c2 r g1 r",
                        "d1 r a1 r d2 r a1 r",
                        "c1 r g1 r c2 r g1 r",
                        "g1 r d2 r g1 r d2 r",
                        "d1 r a1 r d2 r a1 r",
                        "g1 r d2 r g1 - - r",
                    ],
                    "b": [
                        "c1 r g1 r c2 r g1 r",
                        "d1 r a1 r d2 r a1 r",
                        "b0 r f#1 r b1 r f#1 r",
                        "e1 r b1 r e1 r b1 r",
                        "c1 r g1 r c2 r g1 r",
                        "b0 r d1 r g1 r d1 r",
                        "a0 r e1 r a1 r e1 r",
                        "d1 r a1 r d2 r a1 r",
                    ],
                },
            },
            "drums": {
                "tone": "n",
                "volume": {"kick": 2, "hat": 1},
                "sections": {
                    "a": ["a0 r e4 r a0 r e4 r"] * 7 + ["a0 r e4 r a0 e4 e4 e4"],
                    "a2": ["a0 r e4 r a0 r e4 r"] * 7 + ["a0 r e4 r a0 e4 e4 e4"],
                    "b": ["a0 r e4 e4 a0 r e4 r"] * 7 + ["a0 e4 a0 e4 a0 e4 e4 e4"],
                },
            },
        },
    },
}


def voice_bars(voice: dict, form: list[str], bars_per_section: dict[str, int]) -> list[str]:
    """The voice's bars in the order of the form; sections it leaves out are rests."""
    bars = []
    for name in form:
        bars += voice["sections"].get(name, [REST_BAR] * bars_per_section[name])
    return bars


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    resources = parser.parse_args().resources.resolve()  # before pyxel.init() changes the working directory
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    slot = FIRST_SOUND
    for name, track in TRACKS.items():
        voices = track["voices"]
        assert len(voices) <= MUSIC_CHANNELS, f"{name}: at most {MUSIC_CHANNELS} voices (channel 3 is the effects')"
        lengths = {
            section: len(bars) for voice in voices.values() for section, bars in voice["sections"].items()
        }  # every voice must agree on a section's length
        for voice_name, voice in voices.items():
            for section, bars in voice["sections"].items():
                assert len(bars) == lengths[section], f"{name}/{voice_name}/{section}: {len(bars)} bars"
                for bar in bars:
                    assert len(bar.split()) == 8, f"{name}/{voice_name}/{section}: {bar!r} is not 8 steps"
        channels = []
        for voice_name, voice in voices.items():
            rendered = dict(voice, bars=voice_bars(voice, track["form"], lengths))
            pyxel.sounds[slot].set(*render(rendered), track["speed"])
            channels.append([slot])
            print(f"sound {slot}: {name} {voice_name}, {pyxel.sounds[slot].total_sec():.1f} s")
            slot += 1
        pyxel.musics[MUSIC[name]].set(*channels, *([[]] * (4 - len(channels))))
        print(f"music {MUSIC[name]}: {name}")
    pyxel.save(str(resources))


if __name__ == "__main__":
    main()
