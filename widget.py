from dataclasses import dataclass
from typing import List, Optional, Callable

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
    collkey: Optional[int] = None


class Widget:
    def __init__(self, x: int, y: int, w: Optional[int] = None, h: Optional[int] = None, bg: Optional[int] = None,
                 border: Optional[int] = None, img: Optional[ImgInfo] = None, text: Optional[List[str]] = None,
                 text_col: int = TEXT_COL):
        self.x: int = x
        self.y: int = y
        if h:
            self.h: int = h
        else:
            if text and isinstance(text, list) and len(text) >= 1:
                self.h: int = (pyxel.FONT_HEIGHT * len(text)) + (len(text) - 1) * TEXT_LINE_SPACING + 2 * WIDGET_MARGIN
            else:
                self.h: int = pyxel.FONT_HEIGHT + 2 * WIDGET_MARGIN
            if img:
                self.h = max(self.h, int(img.h) + 2*WIDGET_MARGIN)
        if w:
            self.w: int = w
        else:
            if text and isinstance(text, list) and len(text) >= 1:
                self.w: int = pyxel.FONT_WIDTH * max(map(len, text)) + 2 * WIDGET_MARGIN
            else:
                self.w: int = pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN
            if img:
                self.w += img.w + WIDGET_MARGIN
        self.bg: Optional[int] = bg
        self.border: Optional[int] = border
        self.img: Optional[ImgInfo] = img
        self.text: Optional[List[str]] = text
        self.text_col: int = text_col
        self.sub_widgets: List[Widget] = []
        self.enabled: bool = True

    def update(self):
        if not self.enabled:
            return
        for wdg in self.sub_widgets:
            wdg.update()

    def draw(self):
        if not self.enabled:
            return
        # background
        if self.bg:
            pyxel.rect(self.x, self.y, self.w, self.h, self.bg)
        # optional border
        if self.border:
            pyxel.rectb(self.x, self.y, self.w, self.h, self.border)
        # optional image
        if self.img:
            pyxel.blt(x=self.x + WIDGET_MARGIN, y=self.y + WIDGET_MARGIN, img=self.img.nr, u=self.img.u, v=self.img.v, w=self.img.w,
                      h=self.img.h, colkey=self.img.collkey)
        # optional text
        if self.text:
            if self.img:
                x_offset = WIDGET_MARGIN * 2 + self.img.w
            else:
                x_offset = WIDGET_MARGIN

            for ix, line in enumerate(self.text):
                y_offset = (pyxel.FONT_HEIGHT + TEXT_LINE_SPACING) * ix + WIDGET_MARGIN + 1
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


class Button(Widget):
    def __init__(self, x: int, y: int, text: list[str], on_click: Callable, h: Optional[int] = None,
                 w: Optional[int] = None, img: Optional[ImgInfo] = None, hotkey: Optional[int] = None, bg: int = 11,
                 hover: Optional[int] = 3, border: Optional[int] = 14):
        super().__init__(x=x, y=y, h=h, w=w, bg=bg, border=border, text=text, img=img)
        self.on_click = on_click
        self.unhovered_bg = bg
        self.hovered_bg = hover
        self.hotkey = hotkey

    def update(self):
        if self.hotkey and pyxel.btnp(self.hotkey):
            self.on_click()
        elif self.x <= pyxel.mouse_x <= self.x + self.w and self.y <= pyxel.mouse_y <= self.y + self.h:
            self.bg = self.hovered_bg
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.on_click()
        else:
            self.bg = self.unhovered_bg
        super().update()
