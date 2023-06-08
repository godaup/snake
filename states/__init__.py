from enum import Enum


class StateID(Enum):
    MENU = 0
    PAUSE = 1
    RUNNING = 2
    DEATH = 3
    COUNTDOWN = 4
