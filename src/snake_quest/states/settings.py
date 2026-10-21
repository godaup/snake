import pyxel

from snake_quest.profile import SCREEN_MODES
from snake_quest.sound import VOLUME_STEPS
from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.states.menu_common import (
    COL_DIM,
    COL_HIGHLIGHT,
    COL_TEXT,
    MENU_MUSIC,
    Title,
    back,
    centered_text,
    confirm,
    down,
    left,
    panel,
    right,
    up,
)

PANEL_W = 176
ITEM_SPACING = 14
BAR_STEP = 5  # px per volume step
COL_BAR, COL_BAR_EMPTY = 11, 5
ITEMS = ("MUSIC", "SOUND", "FULLSCREEN", "SCREEN", "BACK")


class SettingsStateHandler(GameStateHandler):
    """Music and sound volume, fullscreen and the screen filter. Changes apply at once; leaving saves them."""

    def __init__(self, game):
        super().__init__(game=game)
        self.title = Title("SETTINGS", scale=2)
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        self.selected = 0
        self.top = 64

    @staticmethod
    def is_visible() -> bool:
        return True

    def get_music(self) -> int | None:
        return MENU_MUSIC

    def on_enter(self) -> None:
        self.selected = 0

    def change(self, item: str, step: int) -> None:
        """Turn a setting up or down (volumes stop at their ends, the others go round)."""
        profile = self.game.profile
        if item == "MUSIC":
            profile.music_volume = max(0, min(VOLUME_STEPS, profile.music_volume + step))
        elif item == "SOUND":
            profile.sound_volume = max(0, min(VOLUME_STEPS, profile.sound_volume + step))
        elif item == "FULLSCREEN":
            profile.fullscreen = not profile.fullscreen
        elif item == "SCREEN":
            profile.screen_mode = (profile.screen_mode + step) % len(SCREEN_MODES)
        self.game.apply_settings()
        if item == "SOUND":
            self.game.sm.effect("eat")  # hear the new volume

    def leave(self) -> None:
        self.game.profile.save()
        self.game.change_state(StateID.MENU)

    def item_rect(self, index: int) -> tuple[int, int, int, int]:
        return (self.game.cfg.width - PANEL_W) // 2 + 4, self.top + 10 + index * ITEM_SPACING - 3, PANEL_W - 8, 12

    def update(self) -> None:
        self.game.backdrop.update(self.game.dt)
        if up():
            self.selected = (self.selected - 1) % len(ITEMS)
        if down():
            self.selected = (self.selected + 1) % len(ITEMS)
        item = ITEMS[self.selected]
        # mouse: hovering selects, a click on the left half turns down, on the right half up
        for index in range(len(ITEMS)):
            x, y, w, h = self.item_rect(index)
            if x <= pyxel.mouse_x < x + w and y <= pyxel.mouse_y < y + h:
                self.selected = item_index = index
                if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                    if ITEMS[item_index] == "BACK":
                        self.leave()
                    else:
                        self.change(ITEMS[item_index], -1 if pyxel.mouse_x < x + w // 2 else 1)
                    return
        if item != "BACK" and (left() or right()):
            self.change(item, -1 if left() else 1)
        if back() or (confirm() and item == "BACK"):
            self.leave()
        elif confirm() and item in ("FULLSCREEN", "SCREEN"):
            self.change(item, 1)

    def value(self, item: str) -> str | int:
        """What a setting is at: a volume as its step (drawn as a bar), the others as text."""
        profile = self.game.profile
        if item == "MUSIC":
            return profile.music_volume
        if item == "SOUND":
            return profile.sound_volume
        if item == "FULLSCREEN":
            return "ON" if profile.fullscreen else "OFF"
        if item == "SCREEN":
            return SCREEN_MODES[profile.screen_mode]
        return ""

    def draw(self) -> None:
        width = self.game.cfg.width
        self.game.backdrop.draw()
        self.title.draw(width / 2, 30, self.game.backdrop.t)
        panel((width - PANEL_W) // 2, self.top, PANEL_W, len(ITEMS) * ITEM_SPACING + 12)
        for index, item in enumerate(ITEMS):
            x, y, w, _ = self.item_rect(index)
            y += 3
            col = COL_HIGHLIGHT if index == self.selected else COL_TEXT
            if index == self.selected:
                pyxel.text(x + 2, y, ">", COL_HIGHLIGHT)
            if item == "BACK":
                centered_text(y, item, col, width)
                continue
            pyxel.text(x + 10, y, item, col)
            value = self.value(item)
            right_x = x + w - 6
            if isinstance(value, int):
                left_x = right_x - VOLUME_STEPS * BAR_STEP
                for step in range(VOLUME_STEPS):
                    bar_h = 2 + step * 3 // VOLUME_STEPS
                    filled = step < value
                    pyxel.rect(
                        left_x + step * BAR_STEP,
                        y + 5 - bar_h,
                        BAR_STEP - 1,
                        bar_h,
                        COL_BAR if filled else COL_BAR_EMPTY,
                    )
                pyxel.text(left_x - 16, y, "OFF" if value == 0 else f"{value:>2}", col)
            else:
                text = f"< {value} >" if index == self.selected else value
                pyxel.text(right_x - len(text) * pyxel.FONT_WIDTH, y, text, col)
        if not (self.game.cfg.music and self.game.cfg.effects):
            centered_text(self.top + len(ITEMS) * ITEM_SPACING + 18, "MUTED BY --mute", COL_DIM, width)
        centered_text(self.height - 22, "UP / DOWN: CHOOSE   LEFT / RIGHT: CHANGE   ESC: SAVE", COL_DIM, width)
