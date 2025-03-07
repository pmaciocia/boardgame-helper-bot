import discord

from .base import BaseView
from store import Table, Store, Player
from utils import get_message, setup_logging
from embeds import GameEmbed

logger = setup_logging("boardgame.helper.views.join")

class JoinButton(discord.ui.Button):
    def __init__(self, table: Table, store: Store):
        super().__init__(custom_id=f"{table.id}-join", label="Join", style=discord.ButtonStyle.blurple)
        self.table_id = table.id
        self.store = store

    async def callback(self, interaction: discord.Interaction):
        logger.info("JOIN BUTTON for user %s - id %s", interaction.user.id, interaction.id)
        user = interaction.user
        table = self.store.get_table(self.table_id)
        player = self.store.get_player(user.id)
        if player is None:
            player = self.store.add_player(Player(user.id, user.display_name, user.mention))

        if table and player and not player.id in table.players:
            logger.debug("user %s attempting to join table %s", user.id, table.id)
            self.store.join_table(player, table)
        await self.view.update(interaction=interaction)

class LeaveButton(discord.ui.Button):
    def __init__(self, table: Table, store: Store):
        super().__init__(custom_id=f"{table.id}-leave", label="Leave", style=discord.ButtonStyle.blurple)
        self.table_id = table.id
        self.store = store

    async def callback(self, interaction: discord.Interaction):
        logger.info("LEAVE BUTTON for user %s - id %s", interaction.user.id, interaction.id)
        user = interaction.user
        table = self.store.get_table(self.table_id)
        player = self.store.get_player(user.id) or Player(user.id, user.display_name, user.mention)
        
        if not table:
            await self.view.update(interaction=interaction)
            return

        logger.debug("player %d table %s - players [%s]", player.id, table.id, ", ".join(str(p.id) for p in table.players.values()))
        if table and player and player.id in table.players:
            logger.debug("user %s attempting to leave table %s", user.id, table.id)
            self.store.leave_table(player, table)
        await self.view.update(interaction=interaction)

class RemoveButton(discord.ui.Button):
    def __init__(self, table: Table, store: Store):
        super().__init__(custom_id=f"{table.id}-remove", label="Remove", style=discord.ButtonStyle.blurple)
        self.table_id = table.id
        self.store = store

    async def callback(self, interaction: discord.Interaction):
        logger.info("REMOVE BUTTON for user %s - id %s", interaction.user.id, interaction.id)        
        table = self.store.get_table(self.table_id)
        if table and interaction.user.id == table.owner.id:
            game = table.game
            self.view.clear_items()
            self.view.stop()
            await self.view._edit(content=f"Game {game.name} was removed", view=None, embed=None)
            
            if self.view.bot:
                messages = table.messages
                for message in messages:
                    msg = await get_message(self.view.bot, message.id, message.channel_id)
                    if msg:
                        await msg.delete()
                        
            self.store.remove_table(table)
        else:
            await interaction.response.send_message('Only the owner can remove the table', delete_after=5, ephemeral=True)

class GameJoinView(BaseView):
    def __init__(self, table: Table, store: Store, bot: discord.Client = None):
        self.bot = bot
        self.table_id = table.id
        self.store = store
        super().__init__(timeout=None)

        self.add_item(JoinButton(table, store))
        self.add_item(LeaveButton(table, store))
        self.add_item(RemoveButton(table, store))

    async def update(self, interaction: discord.Interaction):
        table = self.store.get_table(self.table_id)
        if not table:
            self.disable_all_items()
            self.stop()
            await self._edit(content="Table no longer exists", view=self)
            return

        logger.debug("Update join view - %s - %d/%d", table.game.name,
                     len(table.players), table.game.maxplayers)
        self.children[0].disabled = len(table.players) == table.game.maxplayers

        e = GameEmbed(table, list_players=True, show_note=True)
        await self._edit(embed=e, view=self)
