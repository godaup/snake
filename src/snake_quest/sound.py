import pyxel


class SoundManager:
    def __init__(self, effects: bool = True, music: bool = True):
        self.effects: bool = effects
        self.music: bool = music

    @staticmethod
    def interrupt():
        pyxel.stop()

    def play(self, music: int | None = None):
        if self.music and music is not None:
            pyxel.playm(music, loop=True)

    def fail(self):
        if self.effects:
            pyxel.play(ch=3, snd=2, loop=False)
