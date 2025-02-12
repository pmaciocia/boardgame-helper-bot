import sqlite3
from abc import ABC, abstractmethod
import numbers
import uuid

# Guild = discord guild
# Event = next scheduled event in a guild
# Table = a player suggesting a game to be played at an event, with a maximum number of players
# Game = a game with name and max players and an optional BGG link
# Player = a discord user

# Store = a data store for the bot

# def create_tables():
#     conn = sqlite3.connect('boardgame_helper.db')
#     c = conn.cursor()

#     c.execute('''
#     CREATE TABLE IF NOT EXISTS Guild (
#         id TEXT PRIMARY KEY
#     )
#     ''')

#     c.execute('''
#     CREATE TABLE IF NOT EXISTS Event (
#         id TEXT PRIMARY KEY,
#         guild_id TEXT,
#         FOREIGN KEY (guild_id) REFERENCES Guild (id)
#     )
#     ''')

#     c.execute('''
#     CREATE TABLE IF NOT EXISTS Player (
#         id TEXT PRIMARY KEY,
#         mention TEXT
#     )
#     ''')

#     c.execute('''
#     CREATE TABLE IF NOT EXISTS Game (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT,
#         owner_id TEXT,
#         bgg_game_id INTEGER,
#         maxplayers INTEGER,
#         FOREIGN KEY (owner_id) REFERENCES Player (id)
#     )
#     ''')

#     c.execute('''
#     CREATE TABLE IF NOT EXISTS Table (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         event_id TEXT,
#         game_id INTEGER,
#         FOREIGN KEY (event_id) REFERENCES Event (id),
#         FOREIGN KEY (game_id) REFERENCES Game (id)
#     )
#     ''')

#     conn.commit()
#     conn.close()

# create_tables()

class Event:
    def __init__(self, id: str, guild_id: int, channel_id: int):
        self.id = id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.tables = {}

class Player:
    def __init__(self, id: str, display_name: str, mention: str):
        self.id = id
        self.display_name = display_name
        self.mention = mention
        self.table = None
        
    def __hash__(self):
        return hash(self.id) 
    
    def __eq__(self, value):
        if value is None:
            return False
        
        if isinstance(value, numbers.Number):
            return self.id == int(value)
        
        return self.id == value.id
    
class Game:
    def __init__(self, name: str, bgg_game=None):
        self.name = bgg_game.name if bgg_game else name
        if bgg_game:
            self.bgg_game = bgg_game
            self.id = bgg_game.id
            self.link = f"https://boardgamegeek.com/boardgame/{bgg_game.id}"
            self.description = bgg_game.description
            self.thumbnail = bgg_game.thumbnail
            self.minplayers = bgg_game.min_players
            self.maxplayers = bgg_game.max_players
            self.recommended_players = max((rank.best, rank.player_count) for rank in bgg_game._player_suggestion)[1]
        else:
            self.bgg_game = None
            self.id = None
            self.link = None
            self.description = ""
            self.thumbnail = ""
            self.minplayers = -1
            self.maxplayers = -1
            self.recommended_players = -1

class Table:
    def __init__(self, event: Event, owner: Player, game: Game):
        self.id = str(uuid.uuid4())
        self.event = event
        self.owner = owner
        self.game = game
        self.players = {}
        self.message = None
    
class Store(ABC):
    @abstractmethod
    def get_event_for_guild_id(self, guild_id: int) -> Event:
        pass
    
    @abstractmethod
    def add_event(self, guild_id: int, event_id: str, channel_id: int) -> Event:
        pass
    
    @abstractmethod
    def get_events(self, guild_id: int = None, event_id: int = None) -> list[Event]:
        pass

    @abstractmethod
    def remove_event(self, event: Event) -> None:
        pass
    
    @abstractmethod
    def add_table(self, event: Event, owner: Player, game: Game) -> Table:
        pass
    
    @abstractmethod
    def get_table(self, table_id: str) -> Table:
        pass

    @abstractmethod
    def join_table(self, player: Player, table: Table) -> Table:
        pass
    
    @abstractmethod
    def leave_table(self, player: Player, table: Table) -> Table:
        pass

    @abstractmethod
    def remove_table(self, table: Table):
        pass
    
    @abstractmethod
    def get_player(self, user_id: str) -> Player:
        pass

    @abstractmethod
    def add_table_message(self, table: Table, message: int) -> Table:
        pass

    @abstractmethod
    def reset() -> None:
        pass

        
class MemoryStore(Store):
    def __init__(self):
        self.guild_events = {}
        self.events = {}
        self.tables = {}
        self.games = {}
        self.players = {}

    def get_event_for_guild_id(self, guild_id: int) -> Event:
        return self.guild_events.get(guild_id)

    def add_event(self, guild_id: str, channel_id: str, event_id: str) -> Event:
        event = Event(event_id, guild_id, channel_id)
        self.guild_events[guild_id] = event
        self.events[event_id] = event
        return event

    def get_event(self, event_id: str) -> Event:
        return self.events.get(event_id)

    def get_events(self, guild_id:int = None, event_id:int = None) -> list[Event]:
        if guild_id:
            return self.guild_events.get(guild_id)
        
        if event_id and event_id in self.events:
            return [self.events.get(event_id)]
        
        return list(self.events.values())

    def remove_event(self, event: Event) -> None:
        if event.id in self.events:
            del self.events[event.id]
        if event.guild_id in self.guild_events:
            del self.guild_events[event.guild_id]

    def add_table(self, event: Event, owner: Player, game: Game) -> Table:
        table = Table(event=event, owner=owner, game=game)
        table.players[owner.id] = owner
        event.tables[owner.id] = table
        
        self.tables[table.id] = table
        self.players[owner.id] = owner
        owner.table = table.id
        return table
    
    def get_table(self, table_id: str) -> Table:
        return self.tables.get(table_id)

    def join_table(self, player: Player, table: Table) -> Table:
        if table is None:
            return None
        
        if len(table.players) >= table.game.maxplayers:
            raise Exception("Table is full")
        
        table.players[player.id] = player
        self.players[player.id] = player
        player.table = table.id
        return table
    
    def leave_table(self, player: Player, table: Table) -> Table:
        if table is None:
            return None
        
        if not player in table.players:
            return table
        
        del table.players[player.id]
        player.table = None
        return table

    def remove_table(self, table: Table):
        if table in self.tables:
            del self.tables[table]
        
        event = table.event
        if table.owner.id in event.tables:
            del event.tables[table.owner.id]
        
        table.owner.table = None
        for player in table.players.values():
            player.table = None
    
    def get_player(self, user_id):
        return self.players.get(user_id)
    
    def add_table_message(self, table: Table, message: int) -> Table:
        table.message = message
        return table
    
    def reset(self):
        self.guild_events = {}
        self.events = {}
        self.tables = {}
        self.games = {}
        self.players = {}