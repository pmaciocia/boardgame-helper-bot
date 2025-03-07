import discord

from .base import BaseView
from store import Store, Event
from utils import setup_logging
from embeds import GameEmbed

logger = setup_logging("boardgame.helper.views.list")

class GameListView(BaseView):
    interaction: discord.Interaction | None = None
    message: discord.Message | None = None

    def __init__(self, event: Event, store: Store):
        self.event_id = event.id
        self.store = store
        self.tables = list(event.tables.values())
        self.index = 0
        self.choice = None

        super().__init__(timeout=None)

        self.children[0].disabled = True
        self.children[1].disabled = len(self.tables) == 1

    async def edit_page(self, interaction: discord.Interaction):
        event = self.store.get_event(self.event_id)
        if not event:
            await self.on_timeout()
            return

        self.tables = list(event.tables.values())

        logger.info("index: %s - tables: %d", self.index, len(self.tables))
        table = self.tables[self.index]
        l, r = self.children[0:2]
        l.disabled = self.index == 0
        r.disabled = self.index == len(self.tables)-1

        await self._edit(embed=GameEmbed(table, list_players=True), view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, button: discord.Button, interaction: discord.Interaction):
        logger.info("LEFT BUTTON:- index: %s - tables: %d",
                    self.index, len(self.tables))
        self.index = max(self.index-1, 0)
        await self.edit_page(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, button: discord.Button, interaction: discord.Interaction):
        logger.info("RIGHT BUTTON:- index: %s - tables: %d",
                    self.index, len(self.tables))
        self.index = min(self.index+1, len(self.tables)-1)
        await self.edit_page(interaction)

    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.blurple)
    async def join(self, button: discord.Button, interaction: discord.Interaction):
        logger.info("JOIN BUTTON:- index: %s - tables: %d",
                    self.index, len(self.tables))
        self.choice = self.index
        await self._edit(content=f"You chose {self.tables[self.index].game.name}", embed=None, view=None)

        self.disable_all_items()
        self.stop()

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.blurple)
    async def cancel(self, button: discord.Button, interaction: discord.Interaction):
        logger.info("CANCEL BUTTON:- index: %s - tables: %d",
                    self.index, len(self.tables))
        await self.message.edit(content="Cancelled", delete_after=0)
        self.stop()
