
from abc import ABC, abstractmethod

from dataclasses import dataclass, field
from typing import Dict, Optional
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
    message: Optional[int] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Generate unique ID per instance

@dataclass(frozen=True)
class Event:
    id: str
    guild_id: int
    channel_id: int
    tables: Dict[str, Table] = field(default_factory=dict)



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
    def remove_table(self, table: Table) -> None:
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
