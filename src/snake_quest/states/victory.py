from snake_quest.states.death import DeathStateHandler

COL_VICTORY = 11


class VictoryStateHandler(DeathStateHandler):
    """Shown after the last level of the campaign; same keys as the game over screen."""

    TITLE = "YOU WIN!"
    BG = COL_VICTORY
