from dataclasses import dataclass
from typing import List, Optional

import pyxel

TEXT_COL = 0
WIDGET_MARGIN = 3
TEXT_LINE_SPACING = 2


@dataclass
class ImgInfo:
    nr: int
    u: int
    v: int
    h: float
    w: float


class Widget:
    def __init__(self, x: int, y: int, w: int, h: Optional[int] = None, bg: Optional[int] = None,
                 border: Optional[int] = None, img: Optional[ImgInfo] = None, text: Optional[List[str]] = None,
                 text_col: int = TEXT_COL):
        self.x: int = x
        self.y: int = y
        self.h: int = h if h else pyxel.FONT_HEIGHT + 2 * WIDGET_MARGIN
        self.w: int = w
        self.bg: Optional[int] = bg
        self.border: Optional[int] = border
        self.img: Optional[ImgInfo] = img
        self.text: Optional[List[str]] = text
        self.text_col: int = text_col
        self.sub_widgets: List[Widget] = []

    def update(self):
        for wdg in self.sub_widgets:
            wdg.update()

    def draw(self):
        # background
        if self.bg:
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
                x_offset = WIDGET_MARGIN * 2 + self.img.w
            else:
                x_offset = WIDGET_MARGIN

            for ix, line in enumerate(self.text):
                y_offset = (pyxel.FONT_HEIGHT + TEXT_LINE_SPACING) * (ix - len(self.text) // 2) + WIDGET_MARGIN
                pyxel.text(self.x + x_offset, self.y + y_offset, line, self.text_col)
        for wdg in self.sub_widgets:
            wdg.draw()

    def add_sub_widget(self, wdg: 'Widget'):
        wdg.x += self.x + WIDGET_MARGIN
        wdg.y += self.y + WIDGET_MARGIN
        self.sub_widgets.append(wdg)


class LifeBar(Widget):
    def __init__(self, x: int, y: int, h: int, w: int, bg: int, fg: int, border: Optional[int] = None, val: float = 1.):
        super(LifeBar).__init__(x=x, y=y, h=h, w=w, bg=bg, border=border, text=None, img=None)
        self.val = val
        self.fg = fg

    def draw(self):
        super(LifeBar).draw()
        pyxel.rect(self.x, self.y, self.w * self.val, self.h, self.fg)
