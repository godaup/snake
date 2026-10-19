"""Stress-test music switching against Pyxel's audio thread, to catch audio deadlocks.

Pyxel 2.9.9's playm() can deadlock with the SDL audio callback: the game froze while switching music (Oct 2026). This
switches music as fast as possible with a real SDL audio thread (offscreen video, dummy audio: no window, no sound):

    SDL_VIDEODRIVER=offscreen SDL_AUDIODRIVER=dummy timeout -s KILL 90 \\
        python tools/audio_stress.py src/snake_quest/resources/garden.pyxres game 60

Modes: `game` uses the game's SoundManager, music plus an effect per switch (must finish), `playm` uses pyxel.playm
directly (deadlocked after a few thousand switches with Pyxel 2.9.9; rerun it after upgrading Pyxel to see whether the
bug is fixed). A deadlock blocks the process for good, even against SIGTERM, hence `timeout -s KILL`: exit code 124
from timeout means it hung.
"""

import argparse
import time
from pathlib import Path

import pyxel

from snake_quest.sound import EFFECTS, SoundManager
from snake_quest.states.menu_common import MENU_MUSIC


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    parser.add_argument("mode", choices=["game", "playm"])
    parser.add_argument("seconds", type=float)
    args = parser.parse_args()
    resources = args.resources.resolve()  # before pyxel.init() changes the working directory
    pyxel.init(64, 64)  # not headless: headless Pyxel runs no audio thread, so the bug cannot show
    pyxel.load(str(resources))
    sound = SoundManager(effects=True, music=True)
    effects = list(EFFECTS)
    switches = 0
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        sound.interrupt()
        if args.mode == "playm":
            pyxel.playm(MENU_MUSIC, loop=True)
        else:
            sound.play(MENU_MUSIC)
            sound.effect(effects[switches % len(effects)])  # effects share the last channel with the music
        switches += 1
        if switches % 1000 == 0:
            print(f"{switches} switches", flush=True)
        time.sleep(0.0005)
    print(f"ok: {args.mode}, {switches} music switches without a deadlock", flush=True)


if __name__ == "__main__":
    main()
