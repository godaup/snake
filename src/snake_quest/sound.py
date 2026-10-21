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
VOLUME_STEPS = 10  # the settings screen's volume levels; the loudest is Pyxel's default gain
FULL_GAIN = 0.125


class SoundManager:
    def __init__(self, effects: bool = True, music: bool = True):
        self.effects: bool = effects
        self.music: bool = music
        self.music_volume: int = VOLUME_STEPS
        self.sound_volume: int = VOLUME_STEPS
        self.playing: int | None = None  # the music started last

    def set_volume(self, music: int | None = None, sound: int | None = None) -> None:
        """Change the music and effect volumes (0..VOLUME_STEPS) at once, also for what is playing. Music turned
        up from silence starts again."""
        silent = self.music_volume == 0
        if music is not None:
            self.music_volume = max(0, min(VOLUME_STEPS, music))
        if sound is not None:
            self.sound_volume = max(0, min(VOLUME_STEPS, sound))
        for channel in range(len(pyxel.channels)):
            pyxel.channels[channel].gain = self._gain(channel, self.playing)
        if silent and self.music_volume and self.playing is not None:
            self.play(self.playing)

    def _gain(self, channel: int, music: int | None) -> float:
        """The effect channel is at the effect volume, unless the music plays on it (the menu theme does)."""
        uses = music is not None and channel < len(pyxel.musics[music].seqs) and list(pyxel.musics[music].seqs[channel])
        volume = self.sound_volume if channel == EFFECT_CHANNEL and not uses else self.music_volume
        return FULL_GAIN * volume / VOLUME_STEPS

    @staticmethod
    def interrupt():
        pyxel.stop()

    def play(self, music: int | None = None):
        """Loop a music. Each channel is started with pyxel.play() instead of playm: in Pyxel 2.9.9 playm can
        deadlock with the audio thread (it waits for SDL's audio lock while holding the channels lock that the audio
        callback needs), which froze the game. Check again with tools/audio_stress.py before using playm."""
        self.playing = music
        if not self.music or music is None or self.music_volume == 0:
            return
        for channel, seq in enumerate(pyxel.musics[music].seqs):
            sounds = list(seq)
            if sounds:  # an empty music (e.g. the level music slot) makes no audio calls at all
                pyxel.channels[channel].gain = self._gain(channel, music)
                pyxel.play(channel, sounds, loop=True)

    def effect(self, name: str) -> None:
        """Play a sound effect by name (see EFFECTS); a new one cuts the one still playing."""
        if self.effects and self.sound_volume:
            pyxel.channels[EFFECT_CHANNEL].gain = FULL_GAIN * self.sound_volume / VOLUME_STEPS
            pyxel.play(EFFECT_CHANNEL, EFFECTS[name])
