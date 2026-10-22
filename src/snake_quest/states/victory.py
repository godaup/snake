"""The victory screen."""

from snake_quest.states.death import DeathStateHandler

COL_VICTORY = 11


class VictoryStateHandler(DeathStateHandler):
    """Shown after the last level of the story and after the bonus arc's; same keys as the game over screen."""

    TITLE = "YOU WIN!"
    BONUS_TITLE = "THE GARDEN IS KEPT!"
    BG = COL_VICTORY

    def on_enter(self) -> None:
        bonus = self.game.campaign.level(self.game.level_counter).bonus
        self.TITLE = self.BONUS_TITLE if bonus else type(self).TITLE
        super().on_enter()
