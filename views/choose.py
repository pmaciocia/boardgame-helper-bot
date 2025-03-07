import discord

from .base import BaseView
from store import Game
from utils import setup_logging

logger = setup_logging("boardgame.helper.views.choose")


class GameChooseView(BaseView):
    def __init__(self, games: list, timeout: int = 300):
        self.choice = None
        games = games[0:5]
        super().__init__(timeout=timeout)
        for idx, game in enumerate(games):
            self.add_item(AddButton(label=str(idx+1), game=game))
        self.add_item(CancelButton())

class AddButton(discord.ui.Button):
    def __init__(self, label: str, game: Game):
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        game = self.game
        logger.info("CHOOSE BUTTON:- label: %s - game: %s/%s",
                    self.label, game.id, game.name)
        self.view.choice = game
        await self.view._edit(content=f"You chose {game.name}", view=None, embed=None, delete_after=5)
        self.view.clear_items()
        self.view.stop()


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(row=1, emoji="❌", style=discord.ButtonStyle.blurple)
        pass

    async def callback(self, interaction: discord.Interaction):
        logger.info("CHOOSE CANCEL BUTTON")
        self.view.clear_items()
        self.view.stop()
        await self.view._edit(content="Cancelled", embed=None, view=None, delete_after=5)
