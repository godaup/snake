from dataclasses import dataclass
from typing import List, Optional

import pyxel

TEXT_COL = 0


@dataclass
class ImgInfo:
    nr: int
    u: int
    v: int
    h: float
    w: float


class Widget:
    def __init__(self, x: int, y: int, h: int, w: int, bg: int, border: Optional[int] = None,
                 img: Optional[ImgInfo] = None, text: Optional[str] = None):
        self.x: int = x
        self.y: int = y
        self.h: int = h
        self.w: int = w
        self.bg: int = bg
        self.border: Optional[int] = border
        self.img: Optional[ImgInfo] = img
        self.text: Optional[str] = text
        self.sub_widgets: List[Widget] = []

    def update(self):
        for wdg in self.sub_widgets:
            wdg.update()

    def draw(self):
        # background
        pyxel.rect(self.x, self.y, self.w, self.h, self.bg)
        # optional border
        if self.border:
            pyxel.rectb(self.x, self.y, self.w, self.h, self.border)
        # optional image
        if self.img:
            pyxel.blt(x=self.x + 3, y=self.y + 3, img=self.img.nr, u=self.img.u, v=self.img.v, w=self.img.w,
                      h=self.img.h)
        # optional text
        if self.text:
            if self.img:
                pyxel.text(x=self.x + 3 + self.img.w, y=self.y + 3 + self.img.h, s=self.text, col=TEXT_COL)
            else:
                pyxel.text(x=self.x + 3, y=self.y + 3, s=self.text, col=TEXT_COL)
        for wdg in self.sub_widgets:
            wdg.draw()

    def add_sub_widget(self, wdg: 'Widget'):
        wdg.x += self.x
        wdg.y += self.y
        self.sub_widgets.append(wdg)


class LifeBar(Widget):
    def __init__(self, x: int, y: int, h: int, w: int, bg: int, fg: int, border: Optional[int] = None, val: float = 1.):
        super(LifeBar).__init__(x=x, y=y, h=h, w=w, bg=bg, border=border, text=None, img=None)
        self.val = val
        self.fg = fg

    def draw(self):
        super(LifeBar).draw()
        pyxel.rect(self.x, self.y, self.w * self.val, self.h, self.fg)
