import pyxel


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

    def fail(self):
        if self.effects:
            pyxel.play(ch=3, snd=2, loop=False)
