
from . import *
import logging

logger = logging.getLogger("boardgame.helper.store.local")

import sqlite3

from typing import Optional, Dict, List
from dataclasses import dataclass, field
from functools import wraps
from nanoid import generate

def lazy_load(load: str, keys: list[str]):
    def _decorate(func):
        @wraps(func)
        def decorate(instance, *args, **kwargs):
            field = f"_{func.__name__}"
            is_loaded_name = f"{field}_loaded"
            if not getattr(instance, is_loaded_name, False):
                logger.debug("lazy loading for %s - %s([%s])", field, load, ", ".join(map(str, keys)))
                store = getattr(instance.__class__, "_store")
                if store:
                    ks = [getattr(instance, key) for key in keys]
                    val = getattr(store, load)(*ks)
                    # if the field expects a dict but we get a list, convert it
                    if isinstance(getattr(instance, field), dict) and isinstance(val, list):
                        val = {v.id: v for v in val}
                    setattr(instance, is_loaded_name, True)
                    setattr(instance, field, val)
            return func(instance, *args, **kwargs)
        return decorate
    return _decorate

class Base(object):
    _store: any

@dataclass(unsafe_hash=True)
class _Player(Base, Player):
    _table: Table | None = field(default=None)

    @property
    @lazy_load(load="get_table_for_player", keys=["id"])
    def table(self):
        return self._table
    
    @table.setter
    def table(self, table):
        self._table = table

@dataclass(unsafe_hash=True)
class _Table(Base):
    event_id: str
    owner_id: str
    game_id: str
    note: str = ""

    _event: "Event" = field(default=None)
    _owner: Player = field(default=None)
    _game: Game = field(default=None)

    _players: Dict[str, Player] = field(default_factory=dict)
    _messages: Optional[list["Message"]] = field(default_factory=list)
    id: str = field(default_factory=lambda: generate(size=10))  # Generate unique ID per instance

    @property
    @lazy_load(load="get_event", keys=["event_id"])
    def event(self):
        return self._event
    
    @event.setter
    def event(self, event):
        self._event = event

    @property
    @lazy_load(load="get_player", keys=["owner_id"])
    def owner(self):
        return self._owner
    
    @owner.setter
    def owner(self, owner):
        self._owner = owner

    @property
    @lazy_load(load="get_game", keys=["game_id"])
    def game(self):
        return self._game
    
    @game.setter
    def game(self, game):
        self._game = game

    @property
    @lazy_load(load="get_players_for_table", keys=["id"])
    def players(self):
        return self._players
    
    @players.setter
    def players(self, players):
        self._players = players

    @property
    @lazy_load(load="get_messages_for_table", keys=["id"])
    def messages(self):
        return self._messages
    
    @messages.setter
    def messages(self, messages):
        self._messages = messages
    

@dataclass(unsafe_hash=True)
class _Event(Base):
    guild_id: int
    channel_id: int
    _guild: "_Guild" = field(default=None)
    _tables: Dict[str, Table] = field(default_factory=dict)
    id: str = field(default_factory=lambda: generate(size=10))  # Generate unique ID per instance

    @property
    @lazy_load(load="get_tables_for_event", keys=["id"])
    def tables(self):
        return self._tables
    
    @tables.setter
    def tables(self, tables):
        self._tables = tables
        
    @property
    @lazy_load(load="get_guild", keys=["guild_id"])
    def guild(self):
        return self._guild
    
    @guild.setter
    def guild(self, guild):
        self._guild = guild
        
        
@dataclass(unsafe_hash=True)
class _Guild(Base):
    id: str
    channel_id: int
    _event: "_Event" = field(default=None)

    @property
    @lazy_load(load="get_event_for_guild_id", keys=["id"])
    def event(self):
        return self._event
    
    @event.setter
    def event(self, event):
        self._event = event


class SQLiteStore:
    def __init__(self, db_path: str = "bhb.sqlite"):
        self.conn = sqlite3.connect(db_path, autocommit=True)
        self.conn.row_factory = dict_factory
        # self.conn.set_trace_callback(print)
        self._initialize_db()
        _Player._store = self
        _Table._store = self
        _Event._store = self
        _Guild._store = self

    def _initialize_db(self):
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild (
                    id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS event (
                    id TEXT PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    FOREIGN KEY(guild_id) REFERENCES guild(id)
                );
                CREATE TABLE IF NOT EXISTS _table (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    game_id INTEGER NOT NULL,
                    note TEXT,
                    FOREIGN KEY(event_id) REFERENCES event(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_id) REFERENCES player(id),
                    FOREIGN KEY(game_id) REFERENCES game(id)
                );
                CREATE TABLE IF NOT EXISTS table_player (
                    table_id TEXT,
                    player_id INTEGER,
                    UNIQUE(table_id, player_id) ON CONFLICT IGNORE,
                    FOREIGN KEY(table_id) REFERENCES _table(id) ON DELETE CASCADE,
                    FOREIGN KEY(player_id) REFERENCES player(id)
                );
                CREATE TABLE IF NOT EXISTS table_message (
                    table_id TEXT,
                    message_id INTEGER,
                    UNIQUE(table_id, message_id) ON CONFLICT IGNORE,
                    FOREIGN KEY(table_id) REFERENCES _table(id) ON DELETE CASCADE,
                    FOREIGN KEY(message_id) REFERENCES message(id)
                );
                CREATE TABLE IF NOT EXISTS player (
                    id INTEGER PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    mention TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS game (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    year INTEGER,
                    rank INTEGER,
                    description TEXT,
                    thumbnail TEXT,
                    minplayers INTEGER,
                    maxplayers INTEGER,
                    recommended_players INTEGER
                );
                CREATE TABLE IF NOT EXISTS message (
                    id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    type INTEGER
                );
                """
            )
            
    def add_guild(self, guild_id: int, channel_id: int, role_id:int = None):
        with self.conn:
            self.conn.execute("INSERT INTO guild (id, channel_id) VALUES (?, ?)", (guild_id, channel_id,))
            if role_id:
                self.conn.execute("INSERT INTO guild_roles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id,))
                
        return self.get_guild(guild_id)
    
    def update_guild(self, guild: Guild, channel_id: int) -> Guild:
        with self.conn:
            self.conn.execute("UPDATE guild SET channel_id = ? WHERE id = ?", (channel_id, guild.id,))
        return self.get_guild(guild.id)

    def get_guild(self, guild_id: int):
        cursor = self.conn.execute("SELECT * FROM guild WHERE id = ?", (guild_id,))
        row = cursor.fetchone()
        return _Guild(**row) if row else None
    
    def add_role(self, guild: Guild, role_id: int) -> Guild:
        with self.conn:
            self.conn.execute("INSERT INTO guild_roles (guild_id, role_id) VALUES (?, ?)", (guild.id, role_id,))
        
        return self.get_guild(guild.id)
    
    def remove_role(self, guild: Guild, role_id: int):
        with self.conn:
            self.conn.execute("DELETE FROM guild_roles WHERE guild_id = ? AND role_id = ?", (guild.id, role_id,))
        
        return self.get_guild(guild.id)
    
    def get_roles_for_guild(self, guild_id: int):
        cursor = self.conn.execute("SELECT role_id FROM guild_roles WHERE guild_id = ?", (guild_id,))
        rows = cursor.fetchall()
        return [row["role_id"] for row in rows]
    
    def remove_guild(self, guild: Guild):
        with self.conn:
            self.conn.execute("DELETE FROM guild WHERE id = ?", (guild.id,))
            self.conn.execute("DELETE FROM guild_roles WHERE guild_id = ?", (guild.id,))
           
    def get_event_for_guild_id(self, guild_id: int):
        cursor = self.conn.execute("SELECT * FROM event WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        return _Event(**row) if row else None

    def add_event(self, guild: Guild, event_id: str = None):
        if event_id is None:
            event_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute("INSERT INTO event (id, guild_id, channel_id) VALUES (?, ?, ?)", (event_id, guild.id, guild.channel_id))
        
        return self.get_event(event_id=event_id)

    def get_event(self, event_id: str = None) -> _Event:
        cursor = self.conn.execute( "SELECT * FROM event WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        return _Event(**row) if row else None
    
    def get_all_events(self) -> List:
        cursor = self.conn.execute("SELECT * FROM event")
        rows = cursor.fetchall()
        return [_Event(**row) for row in rows]

    def remove_event(self, event: Event) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM event WHERE id = ?", (event.id,))

    def add_table(self, event: Event, owner: Player, game: Game, note: str=None) -> str:
        table_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute("INSERT INTO _table (id, event_id, owner_id, game_id, note) VALUES (?, ?, ?, ?, ?)",
                              (table_id, event.id, owner.id, game.id, note or ""))
        return self.get_table(table_id=table_id)

    def get_table(self, table_id: str):
        cursor = self.conn.execute("SELECT * FROM _table WHERE id = ?", (table_id,))
        row =  cursor.fetchone()
        return _Table(**row) if row else None

    def add_game(self, game: Game):
        with self.conn:
            self.conn.execute("""
                INSERT INTO game (id, name, year, rank, description, thumbnail, minplayers, maxplayers, recommended_players)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING;
            """, (game.id, game.name, game.year, game.rank, game.description, game.thumbnail, game.minplayers, game.maxplayers, game.recommended_players))
        return self.get_game(game.id)


    def get_game(self, game_id: str):
        cursor = self.conn.execute("SELECT * FROM game WHERE id = ?", (game_id,))    
        row =  cursor.fetchone()
        return Game(**row) if row else None

    def get_tables_for_event(self, event_id: str):
        cursor = self.conn.execute("SELECT id FROM _table WHERE event_id = ?", (event_id,))
        rows = cursor.fetchall()
        return [self.get_table(table_id=row["id"]) for row in rows] if rows else []

    def join_table(self, player: Player, table: Table):
        with self.conn:
            self.conn.execute("INSERT INTO table_player (player_id, table_id) VALUES (?, ?)", (player.id, table.id))

        return self.get_table(table_id=table.id)

    def leave_table(self, player: Player, table: Table):
        with self.conn:
            self.conn.execute("DELETE FROM table_player WHERE player_id = ? AND table_id = ?", (player.id, table.id))

        return self.get_table(table_id=table.id)

    def remove_table(self, table: Table) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM _table WHERE id = ?", (table.id,))
            self.conn.execute("DELETE FROM table_player WHERE table_id = ?", (table.id,))
            self.conn.execute("DELETE FROM table_message WHERE table_id = ?", (table.id,))

    def add_player(self, player: Player):
        with self.conn:
            self.conn.execute("""
                INSERT INTO player (id, display_name, mention )
                VALUES (?, ?, ?);
            """, (player.id, player.display_name, player.mention))

        return self.get_player(player.id)

    def get_player(self, player_id: int):
        cursor = self.conn.execute("SELECT * FROM player WHERE id = ?", (player_id,))
        row = cursor.fetchone()
        return _Player(**row) if row else None

    def get_players_for_table(self, table_id: int):
        cursor = self.conn.execute("SELECT p.id, p.display_name, p.mention FROM player p LEFT JOIN table_player tp ON tp.player_id = p.id WHERE tp.table_id = ?", (table_id,))
        rows = cursor.fetchall()

        players = []
        for row in rows:
            players.append(Player(**row))

        return players
    
    def get_table_for_player(self, player_id: int) -> Table:
        cursor = self.conn.execute("SELECT t.* FROM table t LEFT JOIN table_player tp ON tp.table_id = t.id WHERE tp.player_id = ?", (player_id,))
        row = cursor.fetchone()
        return _Table(**row) if row else None

    def add_table_message(self, table: Table, message: Message) -> Table:
        self.add_message(message)
        with self.conn:
            self.conn.execute("INSERT INTO table_message (table_id, message_id) VALUES (?, ?)", (table.id, message.id))
        return self.get_table(table_id=table.id)

    def get_table_for_message(self, message: int) -> Table:
        cursor = self.conn.execute("SELECT * FROM _table WHERE message = ?", (message,))
        row = cursor.fetchone()
        return _Table(**row) if row else None

    def get_messages_for_table(self, table_id: int) -> List[Message]:
        cursor = self.conn.execute("SELECT m.* FROM message m LEFT JOIN table_message tm ON tm.message_id = m.id WHERE tm.table_id = ?", (table_id,))
        rows = cursor.fetchall()
        return [Message(**row) for row in rows] if len(rows) > 0 else []

    def add_message(self, message: Message) -> Message:
        with self.conn:
            self.conn.execute("INSERT INTO message (id, guild_id, channel_id, type) VALUES (?, ?, ?, ?)", (message.id, message.guild_id, message.channel_id, message.type))
        return self.get_message(message.id)

    def get_message(self, message_id: int) -> Message:
        cursor = self.conn.execute("SELECT * FROM message WHERE id = ?", (message_id,))
        row = cursor.fetchone()
        return Message(**row) if row else None

    def delete_message(self, message: Message) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM message WHERE id = ?", (message.id,))
            self.conn.execute("DELETE FROM table_message WHERE message_id = ?", (message.id,))

    def reset(self) -> None:
        with self.conn:
            self.conn.executescript("""
                DROP TABLE IF EXISTS guild_roles;
                DROP TABLE IF EXISTS table_player;
                DROP TABLE IF EXISTS table_message;
                DROP TABLE IF EXISTS event;
                DROP TABLE IF EXISTS _table;
                DROP TABLE IF EXISTS player;
                DROP TABLE IF EXISTS game;
                DROP TABLE IF EXISTS message;
                DROP TABLE IF EXISTS guild;
            """)
            self._initialize_db()


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {k: v for k, v in zip(fields, row)}