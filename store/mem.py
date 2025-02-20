
from . import *
import logging

logger = logging.getLogger("boardgame.helper.store.mem")
        
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

    def get_event(self, guild_id:int = None, event_id:int = None) -> list[Event]:
        if guild_id:
            return self.guild_events.get(guild_id)
        
        if event_id and event_id in self.events:
            return [self.events.get(event_id)]
        
        return list(self.events.values())
    
    def get_all_events(self) -> list[Event]:
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
        owner.table = table
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
        player.table = table
        return table
    
    def leave_table(self, player: Player, table: Table) -> Table:
        if table is None:
            return None
        
        logger.info("player %d leaving table %s - players [%s]", player.id, table.id, 
                     ", ".join(str(p.id) for p in table.players.values()))
        if not player.id in table.players:
            logger.info({"player %s not found", player.id})
            return table
        
        del table.players[player.id]
        player.table = None
        return table

    def remove_table(self, table: Table) -> None:
        if table.id in self.tables:
            del self.tables[table.id]
        
        event = table.event
        if table.owner.id in event.tables:
            del event.tables[table.owner.id]
        
        table.owner.table = None
        for player in table.players.values():
            player.table = None
    
    def get_player(self, user_id) -> Player:
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