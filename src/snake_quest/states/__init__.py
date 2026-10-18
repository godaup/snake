from enum import Enum


class StateID(Enum):
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
