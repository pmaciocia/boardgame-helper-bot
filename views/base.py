
import discord
import traceback
import typing

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

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item["BaseView"]) -> None:
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