"""Write the level music into the sprites .pyxres: per track three voices (lead, bass, drums) on channels 0-2, looped;
channel 3 stays free for the sound effects.

The scores are plain text, written like the menu theme's (see compose_theme.py): bars of 8 steps (eighth notes) with
`c3`-style notes (sharps as `c#3`, octaves 0-4), `-` to hold, `r` to rest. Each track names its sections and a `form`,
the order they play in; a voice may leave a section out to rest through it. A voice's `volume` is a number, or for
drums one per octave of the noise pitch (kick, snare, hats); `vibrato` makes held notes waver.

    python tools/compose_music.py src/snake_quest/resources/garden.pyxres

Music numbers come from sound.MUSIC; the sound slots from FIRST_SOUND on (three per track) are this tool's.
"""

import argparse
from pathlib import Path

import pyxel

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
                "volume": {"0": 2, "4": 1},
                "sections": {
                    "a": ["a0 r e4 r a0 r e4 r"] * 7 + ["a0 r e4 r a0 e4 e4 e4"],
                    "a2": ["a0 r e4 r a0 r e4 r"] * 7 + ["a0 r e4 r a0 e4 e4 e4"],
                    "b": ["a0 r e4 e4 a0 r e4 r"] * 7 + ["a0 e4 a0 e4 a0 e4 e4 e4"],
                },
            },
        },
    },
    # The Wilds: tense, a hunting gallop, E minor. A: Em Em C D Em Em C B, A2 alike, B: Am Am C C Em Em B B
    "wilds": {
        "speed": 14,  # ~129 bpm
        "form": ["a", "a2", "b", "a"],
        "voices": {
            "lead": {
                "tone": "s",
                "volume": 2,
                "sections": {
                    "a": [
                        "e3 - r g3 - r f#3 e3",
                        "b2 - - - r - r -",
                        "e3 - r g3 - r a3 g3",
                        "f#3 - - - d3 - r -",
                        "e3 - r g3 - r b3 -",
                        "c4 - b3 - a3 - g3 -",
                        "e3 - g3 - c4 - b3 a3",
                        "b3 - - - d#3 - r -",
                    ],
                    "a2": [
                        "b3 - r b3 - r a3 g3",
                        "e3 - - - r - r -",
                        "c4 - r c4 - r b3 a3",
                        "f#3 - - - a3 - r -",
                        "g3 - f#3 - e3 - b2 -",
                        "e3 - g3 - b3 - e4 -",
                        "e4 - c4 - g3 - e3 -",
                        "f#3 - - - d#3 - r -",
                    ],
                    "b": [
                        "a3 - - c4 - - e4 -",
                        "d4 c4 b3 - a3 - r -",
                        "g3 - - c4 - - e4 -",
                        "d4 - c4 - g3 - r -",
                        "e4 - - - d4 - b3 -",
                        "g3 - b3 - e4 - g4 -",
                        "f#4 - d#4 - b3 - f#3 -",
                        "d#4 - - - b3 - r -",
                    ],
                },
            },
            "bass": {
                "tone": "t",
                "volume": 3,
                "sections": {
                    "a": [
                        "e1 r e1 e1 r e1 e1 r",
                        "e1 r e1 e1 r e1 b0 r",
                        "c1 r c1 c1 r c1 c1 r",
                        "d1 r d1 d1 r d1 d1 r",
                        "e1 r e1 e1 r e1 e1 r",
                        "e1 r e1 e1 r e1 b0 r",
                        "c1 r c1 c1 r c1 c1 r",
                        "b0 r b0 b0 r b0 b0 r",
                    ],
                    "a2": [
                        "e1 r e1 e1 r e1 e1 r",
                        "e1 r e1 e1 r e1 b0 r",
                        "c1 r c1 c1 r c1 c1 r",
                        "d1 r d1 d1 r d1 d1 r",
                        "e1 r e1 e1 r e1 e1 r",
                        "e1 r e1 e1 r e1 b0 r",
                        "c1 r c1 c1 r c1 c1 r",
                        "b0 r b0 b0 r b0 b0 r",
                    ],
                    "b": [
                        "a0 r a0 a0 r a0 a0 r",
                        "a0 r a0 a0 r a0 e1 r",
                        "c1 r c1 c1 r c1 c1 r",
                        "c1 r c1 c1 r c1 g0 r",
                        "e1 r e1 e1 r e1 e1 r",
                        "e1 r e1 e1 r e1 e1 r",
                        "b0 r b0 b0 r b0 b0 r",
                        "b0 r b0 b0 r b0 f#0 r",
                    ],
                },
            },
            "drums": {  # low toms: a0 thumps, c2 knocks
                "tone": "n",
                "volume": {"0": 2, "2": 1},
                "sections": {
                    "a": ["a0 r r a0 r r c2 r"] * 7 + ["a0 r c2 r a0 c2 c2 c2"],
                    "a2": ["a0 r r a0 r r c2 r"] * 7 + ["a0 r c2 r a0 c2 c2 c2"],
                    "b": ["a0 r c2 a0 r c2 c2 r"] * 7 + ["a0 c2 a0 c2 a0 c2 c2 c2"],
                },
            },
        },
    },
    # The Fortress: a mechanical march, C minor. A: Cm Cm Ab Bb Cm Fm G Cm, A2 alike, B: Ab Ab Bb Bb Fm Fm G G
    "fortress": {
        "speed": 16,  # ~112 bpm
        "form": ["a", "a2", "b", "a"],
        "voices": {
            "lead": {
                "tone": "s",
                "volume": 2,
                "sections": {
                    "a": [
                        "c3 - c3 d#3 g3 - c4 -",
                        "a#3 - g3 - d#3 - g3 -",
                        "g#3 - g#3 c4 d#4 - c4 -",
                        "a#3 - - - a#3 d4 a#3 -",
                        "c4 - g3 - d#3 - c3 -",
                        "f3 - g#3 - c4 - g#3 -",
                        "g3 - b3 - d4 - b3 -",
                        "c4 - - - r - r -",
                    ],
                    "a2": [
                        "g3 - g3 c4 d#4 - g3 -",
                        "c4 - d#4 - g4 - d#4 -",
                        "g#3 - c4 - d#4 - g#4 -",
                        "a#3 - d4 - f4 - d4 -",
                        "d#4 - d4 - c4 - g3 -",
                        "g#3 - f3 - c4 - f3 -",
                        "b3 - d4 - g4 - f4 -",
                        "d#4 - - - c4 - r -",
                    ],
                    "b": [
                        "g#3 g#3 g#3 - c4 c4 c4 -",
                        "d#4 - c4 - g#3 - r -",
                        "a#3 a#3 a#3 - d4 d4 d4 -",
                        "f4 - d4 - a#3 - r -",
                        "c4 - f4 - g#4 - f4 -",
                        "c4 - g#3 - f3 - r -",
                        "g3 - b3 - d4 - g4 -",
                        "f4 - d4 - b3 - g3 -",
                    ],
                },
            },
            "bass": {
                "tone": "t",
                "volume": 3,
                "sections": {
                    "a": [
                        "c1 r g0 r c1 r g0 r",
                        "c1 r g0 r c1 r g0 r",
                        "g#0 r d#1 r g#0 r d#1 r",
                        "a#0 r f1 r a#0 r f1 r",
                        "c1 r g0 r c1 r g0 r",
                        "f0 r c1 r f0 r c1 r",
                        "g0 r d1 r g0 r d1 r",
                        "c1 r g0 r c1 - - r",
                    ],
                    "a2": [
                        "c1 r g0 r c1 r g0 r",
                        "c1 r g0 r c1 r g0 r",
                        "g#0 r d#1 r g#0 r d#1 r",
                        "a#0 r f1 r a#0 r f1 r",
                        "c1 r g0 r c1 r g0 r",
                        "f0 r c1 r f0 r c1 r",
                        "g0 r d1 r g0 r d1 r",
                        "c1 r g0 r c1 - - r",
                    ],
                    "b": [
                        "g#0 r d#1 r g#0 r d#1 r",
                        "g#0 r d#1 r g#0 r d#1 r",
                        "a#0 r f1 r a#0 r f1 r",
                        "a#0 r f1 r a#0 r f1 r",
                        "f0 r c1 r f0 r c1 r",
                        "f0 r c1 r f0 r c1 r",
                        "g0 r d1 r g0 r d1 r",
                        "g0 r d1 r g0 g0 g0 r",
                    ],
                },
            },
            "drums": {  # a0 kick, c3 snare on the off beats, e4 ticks
                "tone": "n",
                "volume": {"0": 2, "3": 2, "4": 1},
                "sections": {
                    "a": ["a0 r c3 r a0 a0 c3 r"] * 7 + ["a0 c3 c3 c3 a0 c3 c3 c3"],
                    "a2": ["a0 e4 c3 e4 a0 a0 c3 e4"] * 7 + ["a0 c3 c3 c3 a0 c3 c3 c3"],
                    "b": ["a0 r c3 r a0 r c3 c3"] * 7 + ["c3 c3 c3 c3 c3 c3 c3 c3"],
                },
            },
        },
    },
    # Ouroboros: eerie and circling, A harmonic minor; the B part turns the A phrase around.
    # A: Am Am F E Am Dm E Am, B: F E Dm E F G E E
    "ouroboros": {
        "speed": 20,  # 90 bpm
        "form": ["a", "b"],
        "voices": {
            "lead": {
                "tone": "t",
                "volume": 2,
                "vibrato": True,
                "sections": {
                    "a": [
                        "a3 - c4 - e4 - d#4 -",
                        "e4 - - - - - r -",
                        "f4 - e4 - c4 - a3 -",
                        "g#3 - - - b3 - - -",
                        "a3 - c4 - e4 - a4 -",
                        "f4 - - - d4 - f4 -",
                        "e4 - d4 - b3 - g#3 -",
                        "a3 - - - - - r -",
                    ],
                    "b": [
                        "c4 - a3 - f3 - a3 -",
                        "g#3 - b3 - e4 - - -",
                        "d4 - f4 - a4 - f4 -",
                        "e4 - - - g#4 - - -",
                        "a4 - f4 - c4 - a3 -",
                        "b3 - d4 - g4 - d4 -",
                        "e4 - b3 - g#3 - b3 -",
                        "e3 - - - - - r -",
                    ],
                },
            },
            "bass": {
                "tone": "p",
                "volume": 2,
                "sections": {
                    "a": [
                        "a0 e1 a1 e1 a0 e1 a1 e1",
                        "a0 e1 a1 e1 a0 e1 a1 e1",
                        "f0 c1 f1 c1 f0 c1 f1 c1",
                        "e0 b0 e1 g#1 e0 b0 e1 g#1",
                        "a0 e1 a1 e1 a0 e1 a1 e1",
                        "d0 a0 d1 a0 d0 a0 d1 a0",
                        "e0 b0 e1 g#1 e0 b0 e1 g#1",
                        "a0 e1 a1 e1 a0 e1 a1 e1",
                    ],
                    "b": [
                        "f0 c1 f1 c1 f0 c1 f1 c1",
                        "e0 b0 e1 g#1 e0 b0 e1 g#1",
                        "d0 a0 d1 a0 d0 a0 d1 a0",
                        "e0 b0 e1 g#1 e0 b0 e1 g#1",
                        "f0 c1 f1 c1 f0 c1 f1 c1",
                        "g0 d1 g1 d1 g0 d1 g1 d1",
                        "e0 b0 e1 g#1 e0 b0 e1 g#1",
                        "e0 b0 e1 g#1 e1 b0 g#0 b0",
                    ],
                },
            },
            "drums": {  # a heartbeat
                "tone": "n",
                "volume": {"0": 2, "4": 1},
                "sections": {
                    "a": ["a0 r a0 r r r r r"] * 7 + ["a0 r a0 r r r e4 e4"],
                    "b": ["a0 r a0 r r r r r"] * 7 + ["a0 r a0 r e4 e4 e4 e4"],
                },
            },
        },
    },
    # The bosses: fast and driving, E with the flat second. A: Em F Em F Em G F E, A2 alike (an octave up),
    # B: Am Am F F G G B B
    "boss": {
        "speed": 12,  # 150 bpm
        "form": ["a", "a2", "b", "a2"],
        "voices": {
            "lead": {
                "tone": "s",
                "volume": 2,
                "sections": {
                    "a": [
                        "e3 e3 r e3 g3 - f3 -",
                        "f3 f3 r f3 a3 - g3 -",
                        "e3 e3 r e3 b3 - a3 -",
                        "c4 - b3 - a3 - f3 -",
                        "e3 e3 r e3 g3 - b3 -",
                        "d4 - b3 - g3 - d4 -",
                        "c4 - a3 - f3 - c4 -",
                        "b3 - - - g#3 - - -",
                    ],
                    "a2": [
                        "e4 - b3 - e4 - g4 -",
                        "f4 - c4 - f4 - a4 -",
                        "g4 - e4 - b3 - e4 -",
                        "f4 - e4 - d4 - c4 -",
                        "b3 - e4 - g4 - b4 -",
                        "a4 - g4 - d4 - b3 -",
                        "c4 - f4 - a4 - f4 -",
                        "g#4 - - - e4 - r -",
                    ],
                    "b": [
                        "a3 - - - c4 - e4 -",
                        "a4 - g4 - e4 - c4 -",
                        "f3 - - - a3 - c4 -",
                        "f4 - e4 - c4 - a3 -",
                        "g3 - - - b3 - d4 -",
                        "g4 - f4 - d4 - b3 -",
                        "b3 - d#4 - f#4 - b4 -",
                        "a4 - f#4 - d#4 - b3 -",
                    ],
                },
            },
            "bass": {
                "tone": "t",
                "volume": 3,
                "sections": {
                    "a": [
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                        "f1 f2 f1 f2 f1 f2 f1 f2",
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                        "f1 f2 f1 f2 f1 f2 f1 f2",
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                        "g1 g2 g1 g2 g1 g2 g1 g2",
                        "f1 f2 f1 f2 f1 f2 f1 f2",
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                    ],
                    "a2": [
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                        "f1 f2 f1 f2 f1 f2 f1 f2",
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                        "f1 f2 f1 f2 f1 f2 f1 f2",
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                        "g1 g2 g1 g2 g1 g2 g1 g2",
                        "f1 f2 f1 f2 f1 f2 f1 f2",
                        "e1 e2 e1 e2 e1 e2 e1 e2",
                    ],
                    "b": [
                        "a0 a1 a0 a1 a0 a1 a0 a1",
                        "a0 a1 a0 a1 a0 a1 a0 a1",
                        "f0 f1 f0 f1 f0 f1 f0 f1",
                        "f0 f1 f0 f1 f0 f1 f0 f1",
                        "g0 g1 g0 g1 g0 g1 g0 g1",
                        "g0 g1 g0 g1 g0 g1 g0 g1",
                        "b0 b1 b0 b1 b0 b1 b0 b1",
                        "b0 b1 b0 b1 b0 b1 b0 b1",
                    ],
                },
            },
            "drums": {  # a0 kick, c3 snare, e4 hats
                "tone": "n",
                "volume": {"0": 2, "3": 2, "4": 1},
                "sections": {
                    "a": ["a0 e4 c3 e4 a0 a0 c3 e4"] * 7 + ["a0 c3 c3 c3 c3 c3 c3 c3"],
                    "a2": ["a0 e4 c3 e4 a0 a0 c3 e4"] * 7 + ["a0 c3 c3 c3 c3 c3 c3 c3"],
                    "b": ["a0 a0 c3 e4 a0 a0 c3 c3"] * 7 + ["c3 c3 c3 c3 c3 c3 c3 c3"],
                },
            },
        },
    },
}


def render(voice: dict) -> tuple[str, str, str, str]:
    """Pyxel note, tone, volume and effect strings for one voice. Held notes repeat the pitch (wavering with
    `vibrato`); the last step of a note fades out, so phrases breathe."""
    steps = " ".join(voice["bars"]).split()
    notes, volumes, effects = [], [], []
    for i, step in enumerate(steps):
        held = step == "-"
        if held:
            step = notes[-1]
        notes.append(step)
        if step == "r":
            volumes.append("0")
            effects.append("n")
            continue
        volume = voice["volume"]
        volumes.append(str(volume[step[-1]] if isinstance(volume, dict) else volume))
        if i + 1 < len(steps) and steps[i + 1] == "-":
            effects.append("v" if held and voice.get("vibrato") else "n")
        else:
            effects.append("f")
    return "".join(notes), voice["tone"] * len(notes), "".join(volumes), "".join(effects)


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
