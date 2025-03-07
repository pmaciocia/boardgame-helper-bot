
import discord

from .base import BaseView
from store import Store
from utils import setup_logging

logger = setup_logging("boardgame.helper.views.list")

class GuildSettingsView(BaseView):
    channel_choice: int = None

    def __init__(self, store: Store):
        self.store = store
        super().__init__(timeout=None)
        
    async def update(self):
        if self.channel_choice:
            guild = self.store.get_guild(self.interaction.guild_id)
            if guild:
                if self.channel_choice != guild.channel_id:
                    self.store.update_guild(guild, self.channel_choice)
            else:
                guild = self.store.add_guild(self.interaction.guild_id, self.channel_choice)

            await self._edit(content="Guild settings updated", view=None)
            self.stop()

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Select channel")
    async def channel_callback(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.channel_choice = select.values[0].id
        await self.update()