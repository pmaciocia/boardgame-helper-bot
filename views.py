
from __future__ import annotations

import typing
import traceback
import logging

import discord
from discord.ui.select import BaseSelect

from embeds import GameEmbed
from store import Store, Table, Player, Game

logger = logging.getLogger("boardgame.helper.view")

class BaseView(discord.ui.View):
    interaction: discord.Interaction | None = None
    message: discord.Message | None = None

    def __init__(self, user: discord.User | discord.Member, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "You cannot interact with this view.", ephemeral=True
            )
            return False
        self.interaction = interaction
        return True

    def _disable_all(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button) or isinstance(item, BaseSelect):
                item.disabled = True

    # after disabling all components we need to edit the message with the new view
    # now when editing the message there are two scenarios:
    # 1. the view was never interacted with i.e in case of plain timeout here message attribute will come in handy
    # 2. the view was interacted with and the interaction was processed and we have the latest interaction stored in the interaction attribute
    async def _edit(self, **kwargs: typing.Any) -> None:
        if self.interaction is None and self.message is not None:
            await self.message.edit(**kwargs)
        elif self.interaction is not None:
            try:
                await self.interaction.response.edit_message(**kwargs)
            except discord.InteractionResponded:
                await self.interaction.edit_original_response(**kwargs)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[BaseView]) -> None:
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        message = f"An error occurred while processing the interaction for {str(item)}:\n```py\n{tb}\n```"
        self._disable_all()
        await self._edit(content=message, view=self)
        self.stop()

    async def on_timeout(self) -> None:
        self._disable_all()
        await self._edit(view=self)


class GameJoinView(discord.ui.View):
    def __init__(self, table: Table, store: Store):
        self.table_id = table.id
        self.store = store
        super().__init__(timeout=None)

        join = discord.ui.Button(
            custom_id=f"{table.id}-join", label="Join", style=discord.ButtonStyle.blurple)
        join.callback = self.join_callback
        self.add_item(join)

        leave = discord.ui.Button(
            custom_id=f"{table.id}-leave", label="Leave", style=discord.ButtonStyle.blurple)
        leave.callback = self.leave_callback
        self.add_item(leave)

    async def update(self, interaction: discord.Interaction):
        table = self.store.get_table(self.table_id)
        if not table:
            return

        if len(table.players) == table.game.maxplayers:
            self.children[0].disabled = True

        e = GameEmbed(table, list_players=True)
        await interaction.response.edit_message(embed=e, view=self)

    async def join_callback(self, interaction: discord.Interaction):
        logger.info("JOIN BUTTON for user %s - id %s",
                    interaction.user.id, interaction.custom_id)
        user = interaction.user
        table = self.store.get_table(self.table_id)
        player = self.store.get_player(user.id) or Player(
            user.id, user.display_name, user.mention)

        if table and player and not player.id in table.players:
            logger.debug("user %s attempting to join table %s",
                         user.id, table.id)
            self.store.join_table(player, table)
        await self.update(interaction=interaction)

    async def leave_callback(self, interaction: discord.Interaction):
        logger.info("LEAVE BUTTON for user %s - id %s",
                    interaction.user.id, interaction.custom_id)
        user = interaction.user
        table = self.store.get_table(self.table_id)
        player = self.store.get_player(user.id) or Player(
            user.id, user.display_name, user.mention)

        if table and player and player in table.players:
            logger.debug("user %s attempting to leave table %s",
                         user.id, table.id)
            self.store.leave_table(player, table)
        await self.update(interaction=interaction)



class GameChooseView(discord.ui.View):
    def __init__(self, name: str, games: list):
        self.choice = None
        games = games[0:5]
        # desc = "\n".join(f"{idx+1}: [{game.name}](https://boardgamegeek.com/boardgame/{game.id}) ({game.year})"
        #                  for idx, game in enumerate(games[0:5]))
        # super().__init__(title=f"Games matching '{name}' (top 5 ranked results)", description=desc,
        #                  disable_on_timeout=True, timeout=60)

        super().__init__(disable_on_timeout=True)

        for idx, game in enumerate(games):
            self.add_button(index=idx, game=game)

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.blurple)
    async def cancel(self, button: discord.Button, interaction: discord.Interaction):
        logger.info("CHOOSE CANCEL BUTTON")
        await interaction.response.send_message('Cancelled', delete_after=1, ephemeral=True)
        self.clear_items()
        self.stop()

    def add_button(self, index: int, game: Game) -> discord.ui.Button:
        label = str(index+1)
        button = discord.ui.Button(
            label=label, style=discord.ButtonStyle.blurple)

        async def callback(interaction: discord.Interaction):
            logger.info("CHOOSE BUTTON:- index: %s - game: %s/%s",
                        index, game.id, game.name)
            self.choice = game
            await interaction.response.send_message(
                content=f"You chose {game.name}", ephemeral=True)
            self.clear_items()
            self.stop()

        button.callback = callback
        self.add_item(button)
        return button

    async def on_timeout(self):
        logger.info("timeout GameChooseView")
        self.clear_items()

    async def on_timeout(self):
        logger.info("timeout GameListView")
        self.clear_items()

        interaction = self.parent
        try:
            await interaction.response.edit_message(view=None, delete_after=5)
        except discord.InteractionResponded:
            await interaction.edit_original_response(view=None, delete_after=5)


class GameListView(discord.ui.View):
    def __init__(self, tables: list[Table]):
        self.tables = tables
        self.index = 0
        self.choice = None

        super().__init__(timeout=None)

        self.children[0].disabled = True
        self.children[1].disabled = len(tables) == 1

    async def on_timeout(self):
        logger.info("timeout GameListView")
        self.clear_items()

        interaction = self.parent
        try:
            await interaction.response.edit_message(view=None, delete_after=5)
        except discord.InteractionResponded:
            await interaction.edit_original_response(view=None, delete_after=5)

    async def edit_page(self, interaction: discord.Interaction):
        logger.info("index: %s - tables: %d", self.index, len(self.tables))
        table = self.tables[self.index]
        l, r = self.children[0:2]
        l.disabled = self.index == 0
        r.disabled = self.index == len(self.tables)-1

        e = GameEmbed(table, list_players=True)
        await interaction.response.edit_message(embed=e, view=self)

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
        await interaction.response.send_message(
            content=f"You chose {self.tables[self.index].game.name}", ephemeral=True)

        self.clear_items()
        self.stop()

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.blurple)
    async def cancel(self, button: discord.Button, interaction: discord.Interaction):
        logger.info("CANCEL BUTTON:- index: %s - tables: %d",
                    self.index, len(self.tables))
        await interaction.response.send_message('Cancelled', delete_after=1, ephemeral=True)
        self.clear_items()
        self.stop()
