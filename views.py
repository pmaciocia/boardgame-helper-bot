
from __future__ import annotations

import typing
import traceback
import logging

import discord
import discord.ext
import discord.ext.pages
from embeds import GameEmbed
from store import Store, Table, Player, Game, Event

logger = logging.getLogger("boardgame.helper.view")


class BaseView(discord.ui.View):
    message: discord.Message | None = None
    interaction: discord.Interaction | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _disable_all(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button) or isinstance(item, discord.ui.Select):
                item.disabled = True

    async def interaction_check(self, interaction):
        self.interaction = interaction
        return True

    async def _edit(self, **kwargs: typing.Any) -> None:
        if self.interaction is None and self.message is not None:
            await self.message.edit(**kwargs)
        elif self.interaction is not None:
            try:
                await self.interaction.response.edit_message(**kwargs)
            except discord.InteractionResponded:
                await self.interaction.edit_original_response(**kwargs)

    async def on_error(self, error: Exception, item: discord.ui.Item[BaseView], interaction: discord.Interaction) -> None:
        tb = "".join(traceback.format_exception(
            type(error), error, error.__traceback__))
        message = f"An error occurred while processing the interaction for {str(item)}:\n```py\n{tb}\n```"
        self._disable_all()
        await self._edit(content=message, view=self)
        self.stop()

    async def on_timeout(self) -> None:
        self._disable_all()
        await self._edit(view=self)
        self.stop()


class GameJoinView(BaseView):
    def __init__(self, table: Table, store: Store, bot: discord.Client = None):
        self.bot = bot
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

        remove_button = discord.ui.Button(emoji="❌",
            custom_id=f"{table.id}-remove", style=discord.ButtonStyle.blurple)
        remove_button.callback = self.remove_callback
        self.add_item(remove_button)

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

    async def join_callback(self, interaction: discord.Interaction):
        logger.info("JOIN BUTTON for user %s - id %s",
                    interaction.user.id, interaction.custom_id)
        user = interaction.user
        table = self.store.get_table(self.table_id)
        player = self.store.get_player(user.id)
        if player is None:
            player = self.store.add_player(
                Player(user.id, user.display_name, user.mention))

        if table and player and not player.id in table.players:
            logger.debug("user %s attempting to join table %s",
                         user.id, table.id)
            self.store.join_table(player, table)
        await self.update(interaction=interaction)
    
    async def remove_callback(self, interaction: discord.Interaction):
        logger.info("REMOVE BUTTON")
        table = self.store.get_table(self.table_id)
        if table and interaction.user.id == table.owner.id:
            game = table.game
            self.disable_all_items()
            self.stop()
            await self._edit(content=f"Game {game.name} was removed", view=None, embed=None)
            
            if self.bot:
                messages = table.messages
                for message in messages:
                    msg = self.bot.get_message(message.id)
                    if not msg:
                        channel = await self.bot.fetch_channel(message.channel_id)
                        msg = await channel.fetch_message(message.id)
                    if msg:
                        await msg.delete()
                        
            self.store.remove_table(table)
        else:
            await interaction.response.send_message('Only the owner can remove the table', delete_after=5, ephemeral=True)


    async def leave_callback(self, interaction: discord.Interaction):
        logger.info("LEAVE BUTTON for user %s - id %s",
                    interaction.user.id, interaction.custom_id)
        user = interaction.user
        table = self.store.get_table(self.table_id)
        player = self.store.get_player(user.id) or Player(
            user.id, user.display_name, user.mention)
        
        if not table:
            await self.update(interaction=interaction)
            return

        logger.debug("player %d table %s - players [%s]", player.id, table.id,
                     ", ".join(str(p.id) for p in table.players.values()))
        if table and player and player.id in table.players:
            logger.debug("user %s attempting to leave table %s",
                         user.id, table.id)
            self.store.leave_table(player, table)
        await self.update(interaction=interaction)


class GameChooseView(BaseView):
    def __init__(self, games: list, timeout: int = 300):
        self.choice = None
        games = games[0:5]
        super().__init__(disable_on_timeout=True, timeout=timeout)
        for idx, game in enumerate(games):
            self.add_button(index=idx, game=game)

    @discord.ui.button(row=1, emoji="❌", style=discord.ButtonStyle.blurple)
    async def cancel(self, button: discord.Button, interaction: discord.Interaction):
        logger.info("CHOOSE CANCEL BUTTON")
        self.disable_all_items()
        self.stop()
        await self._edit(content="Cancelled", embed=None, view=None, delete_after=5)

    def add_button(self, index: int, game: Game) -> discord.ui.Button:
        label = str(index+1)
        button = discord.ui.Button(
            label=label, style=discord.ButtonStyle.blurple)

        async def callback(interaction: discord.Interaction):
            logger.info("CHOOSE BUTTON:- index: %s - game: %s/%s",
                        index, game.id, game.name)
            self.choice = game
            await self._edit(content=f"You chose {game.name}", view=None, embed=None, delete_after=5)
            self.disable_all_items()
            self.stop()

        button.callback = callback
        self.add_item(button)
        return button


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

    @discord.ui.channel_select(placeholder="Select channel")
    async def channel_callback(self, select, interaction):
        self.channel_choice = select.values[0].id
        await self.update()


class DynamicButton(discord.ui.DynamicItem[discord.ui.Button], template=r'button:user:(?P<id>[0-9]+)'):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            discord.ui.Button(
                label='Do Thing',
                style=discord.ButtonStyle.blurple,
                custom_id=f'button:user:{user_id}',
                emoji='\N{THUMBS UP SIGN}',
            )
        )
        self.user_id: int = user_id

    # This is called when the button is clicked and the custom_id matches the template.
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        user_id = int(match['id'])
        return cls(user_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the user who created the button to interact with it.
        return interaction.user.id == self.user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message('This is your very own button!', ephemeral=True)