import pyxel

from widget import TEXT_LINE_SPACING, WIDGET_MARGIN, Button, ImgInfo, LifeBar, Widget


def test_size_from_text():
    wdg = Widget(x=0, y=0, text=["abc", "a"])
    assert wdg.w == 3 * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN
    assert wdg.h == 2 * pyxel.FONT_HEIGHT + TEXT_LINE_SPACING + 2 * WIDGET_MARGIN


def test_size_with_image():
    img = ImgInfo(nr=0, u=0, v=0, h=32, w=32)
    wdg = Widget(x=0, y=0, text=["a"], img=img)
    assert wdg.h == 32 + 2 * WIDGET_MARGIN
    assert wdg.w == pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN + 32 + WIDGET_MARGIN


def test_explicit_size_wins():
    wdg = Widget(x=0, y=0, w=50, h=40, text=["a long line of text"])
    assert (wdg.w, wdg.h) == (50, 40)


def test_sub_widget_is_positioned_relative_to_parent():
    parent = Widget(x=10, y=20, w=100, h=100)
    child = Widget(x=5, y=0)
    parent.add_sub_widget(child)
    assert (child.x, child.y) == (10 + 5 + WIDGET_MARGIN, 20 + WIDGET_MARGIN)
    assert parent.sub_widgets == [child]


def test_draw_smoke():
    img = ImgInfo(nr=0, u=0, v=0, h=8, w=8, collkey=0)
    parent = Widget(x=0, y=0, w=100, h=30, bg=1, border=2, img=img, text=["hello"])
    parent.add_sub_widget(Widget(x=0, y=0, text=["child"]))
    parent.draw()
    parent.enabled = False
    parent.draw()


def test_button_without_input_does_not_click():
    clicks = []
    btn = Button(x=0, y=0, text=["ok"], on_click=lambda: clicks.append(1), hotkey=pyxel.KEY_P)
    btn.update()
    assert clicks == []


def test_life_bar_fills_proportionally():
    pyxel.cls(0)
    bar = LifeBar(x=0, y=0, h=4, w=20, bg=1, fg=8, val=0.5)
    bar.draw()
    assert pyxel.pget(5, 1) == 8
    assert pyxel.pget(15, 1) == 1


def test_disabled_life_bar_draws_nothing():
    pyxel.cls(0)
    bar = LifeBar(x=0, y=0, h=4, w=20, bg=1, fg=8, val=0.5)
    bar.enabled = False
    bar.draw()
    assert pyxel.pget(5, 1) == 0
