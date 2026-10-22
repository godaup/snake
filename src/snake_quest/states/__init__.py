"""The game's screens (states) and their handlers, one module each."""

from enum import Enum


class StateID(Enum):
    """The game's states; `Game` keeps one handler for each."""

    MENU = 0
    PAUSE = 1
    RUNNING = 2
    DEATH = 3
    COUNTDOWN = 4
    VICTORY = 5
    HIGHSCORES = 6
    CREDITS = 7
    CUSTOMIZE = 8
    MISSION = 9
    LEVEL_COMPLETE = 10
    SELECT = 11
    SETTINGS = 12
