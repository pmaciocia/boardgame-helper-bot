
from abc import ABC, abstractmethod

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import IntEnum
import uuid

import logging
logger = logging.getLogger("boardgame.helper.store")

@dataclass(frozen=True)
class Game:
    id: int
    name: str
    year: int
    rank: int
    description: str
    thumbnail: str
    minplayers: int
    maxplayers: int
    recommended_players: int

    @property
    def link(self) -> str:
        return f"https://boardgamegeek.com/boardgame/{self.id}" 

@dataclass(unsafe_hash=True)
class Player:
    id: int
    display_name: str
    mention: str
    table: Optional["Table"] = None

@dataclass(unsafe_hash=True)
class Table:
    event: "Event"
    owner: Player
    game: Game
    players: Dict[str, Player] = field(default_factory=dict)
    messages: Optional[list["Message"]] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Generate unique ID per instance

@dataclass(frozen=False)
class Event:
    id: str
    guild: "Guild"
    tables: Dict[str, Table] = field(default_factory=dict)

@dataclass(frozen=False)
class Guild:
    id: str
    channel_id: int
    event: "Event"
    roles: list[int] = field(default_factory=list)

@dataclass(init=False)
class Message:
    id: int
    guild_id: int
    channel_id: int
    type: "MessageType"

    def __init__(self, id: int, guild_id: int, channel_id: int, type):
        self.id = id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.type = MessageType(type) if isinstance(type, int) else type

class MessageType(IntEnum):
    JOIN = 1 # Join view messages
    ADD = 2 # Game added view messages

class Store(ABC):
    
    @abstractmethod
    def add_guild(self, guild_id: int, channel_id: int, role_id:int = None) -> Guild:
        pass
    
    @abstractmethod
    def update_guild(self, guild: Guild, channel_id: int) -> Guild:
        pass

    @abstractmethod
    def get_guild(self, guild_id: int) -> Guild:
        pass

    @abstractmethod
    def add_role(self, guild: Guild, role_id: int) -> Guild:
        pass
    
    @abstractmethod
    def remove_role(self, guild: Guild, role_id: int) -> Guild:
        pass
    
    @abstractmethod
    def add_event(self, guild: Guild, event_id: str = None) -> Event:
        pass
    
    @abstractmethod
    def get_event(self, guild_id: int = None, event_id: int = None) -> list[Event]:
        pass

    @abstractmethod
    def get_all_events(self) -> list[Event]:
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
    def remove_table(self, table: Table) -> None:
        pass
    
    @abstractmethod
    def add_game(self, game: Game) -> Game:
        pass

    @abstractmethod
    def get_game(self, game_id: str) -> Game:
        pass

    @abstractmethod
    def remove_game(self, game: Game) -> None:
        pass

    @abstractmethod
    def add_player(self, player: Player) -> Player:
        pass

    @abstractmethod
    def get_player(self, user_id: str) -> Player:
        pass

    @abstractmethod
    def remove_player(self, user_id: str) -> Player:
        pass

    @abstractmethod
    def add_table_message(self, table: Table, message: Message) -> Table:
        pass

    @abstractmethod
    def get_table_for_message(self, message: int) -> Table:
        pass

    @abstractmethod
    def add_message(self, message: Message) -> Message:
        pass

    @abstractmethod
    def get_message(self, message_id: int) -> Message:
        pass

    @abstractmethod
    def delete_message(self, message: Message) -> None:
        pass

    @abstractmethod
    def reset() -> None:
        pass
