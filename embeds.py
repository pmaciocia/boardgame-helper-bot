
import discord
from store import Table, Game
from boardgamegeek.objects.games import BoardGame



class PlayerListEmbed(discord.Embed):
    def __init__(self, table: Table):
        owner = table.owner
        game = table.game
        super().__init__(title=game.name, url=game.link,
                         description=f"{owner.mention} is bringing {game.name}")

        if len(table.players) > 0:
            players = ", ".join(p.display_name for p in table.players.values())
            response = f"Players: {players}"
        else:
            response = f"No-one has signed up yet to play {game.name}"

        self.add_field(name=game.name, value=response, inline=False)


class GamesEmbed(discord.Embed):
    def __init__(self, name: str, games: list[Game]):
        desc = "\n".join(f"{idx+1}: [{game.name}]({game.link}) ({game.year})"
                         for idx, game in enumerate(games))
        super().__init__(
            title=f"Games matching '{name}' (top 10 ranked results)", description=desc)


class GameEmbed(discord.Embed):
    def __init__(self, table: Table, list_players=False):
        owner = table.owner
        game = table.game
        super().__init__(title=game.name, url=game.link,
                         description=f"{owner.mention} is bringing {game.name}")

        description = game.description
        if len(game.description) > 300:
            description = description[:297] + "..."

        self.add_field(
            name="Players", value=f"{game.minplayers}-{game.maxplayers}", inline=True)
        self.add_field(
            name="Best", value=game.recommended_players, inline=True)
        self.add_field(name="Description", value=description)
        self.set_thumbnail(url=game.thumbnail)

        if list_players and len(table.players) > 0:
            self.add_field(name="Currently signed up to play:",
                           value=(", ".join(p.mention for p in table.players.values())))
