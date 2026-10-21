import pyxel

# sound slot of each effect, written by tools/compose_effects.py (slots 8-11 hold the menu theme)
EFFECTS = {
    **{name: slot for slot, name in enumerate(["eat", "golden", "speed", "firefly", "portal", "hurt", "death", "win"])},
    "shoot": 12,
    "pickup": 13,
    "boom": 14,
}
# the level music of each arc and the bosses' (a level picks one by name: its arc's `music`, or its own), written by
# tools/compose_music.py into the sprites file; music 1 is the menu theme (MENU_MUSIC in states/menu_common.py)
MUSIC = {"garden": 0, "wilds": 2, "fortress": 3, "ouroboros": 4, "boss": 5}
MUSIC_CHANNELS = 3  # level music plays on channels 0-2 only
# effects play on the last channel, which no music uses
EFFECT_CHANNEL = 3


class SoundManager:
    def __init__(self, effects: bool = True, music: bool = True):
        self.effects: bool = effects
        self.music: bool = music

    @staticmethod
    def interrupt():
        pyxel.stop()

    def play(self, music: int | None = None):
        """Loop a music. Each channel is started with pyxel.play() instead of playm: in Pyxel 2.9.9 playm can
        deadlock with the audio thread (it waits for SDL's audio lock while holding the channels lock that the audio
        callback needs), which froze the game. Check again with tools/audio_stress.py before using playm."""
        if not self.music or music is None:
            return
        for channel, seq in enumerate(pyxel.musics[music].seqs):
            sounds = list(seq)
            if sounds:  # an empty music (e.g. the level music slot) makes no audio calls at all
                pyxel.play(channel, sounds, loop=True)

    def effect(self, name: str) -> None:
        """Play a sound effect by name (see EFFECTS); a new one cuts the one still playing."""
        if self.effects:
            pyxel.play(EFFECT_CHANNEL, EFFECTS[name])
