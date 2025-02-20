
from . import *
import logging

logger = logging.getLogger("boardgame.helper.store.local")

import sqlite3
import uuid
from typing import Optional, Dict, List
from dataclasses import dataclass, field, fields

class SQLiteStore:
    def __init__(self, db_path: str = "bhb.sqlite"):
        self.conn = sqlite3.connect(db_path, autocommit=True)
        self.conn.row_factory = dict_factory
        self.conn.set_trace_callback(print)
        self._initialize_db()

    def _initialize_db(self):
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS event (
                    id TEXT PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS _table (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    game_id INTEGER NOT NULL,
                    message INTEGER,

                    FOREIGN KEY(event_id) REFERENCES event(id)
                );
                CREATE TABLE IF NOT EXISTS table_player (
                    table_id TEXT,
                    player_id INTEGER,

                    FOREIGN KEY(table_id) REFERENCES _table(id)
                    FOREIGN KEY(player_id) REFERENCES player(id)
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
                """
            )

    def get_event_for_guild_id(self, guild_id: int):
        query = "SELECT * FROM event WHERE guild_id = ?"
        cursor = self.conn.execute(query, (guild_id,))
        row = cursor.fetchone()

        if not row:
            return None
        
        event = Event(**row)

        tables = self.get_tables_for_event(event_id=event.id)
        if tables:
            for t in tables:
                event.tables[t.owner.id] = t
          
        return event

    def add_event(self, guild_id: int, event_id: str, channel_id: int):
        with self.conn:
            self.conn.execute("INSERT INTO event (id, guild_id, channel_id) VALUES (?, ?, ?)", (event_id, guild_id, channel_id,))
        
        return self.get_event(event_id=event_id)

    def get_event(self, event_id: str = None, load_tables=True) -> List:
        query = "SELECT * FROM event WHERE id = ?"
        logger.info("get event %s", event_id)
        cursor = self.conn.execute(query, (event_id,))
        row = cursor.fetchone()

        if not row:
            return None
        
        event = Event(**row)
        if load_tables:
            tables = self.get_tables_for_event(event_id=event_id)
            for table in tables:
                event.tables[table.id] = table
            

          
        return event
    
    def get_all_events(self) -> List:
        query = "SELECT id FROM event"
        cursor = self.conn.execute(query)
        rows = cursor.fetchall()

        return [self.get_event(event_id=row["id"]) for  row in rows]

    def remove_event(self, event_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM event WHERE id = ?", (event_id,))

    def add_table(self, event: Event, owner: Player, game: Game) -> str:
        table_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute("INSERT INTO _table (id, event_id, owner_id, game_id) VALUES (?, ?, ?, ?)",
                              (table_id, event.id, owner.id, game.id))
        return self.get_table(table_id=table_id)

    def get_table(self, table_id: str):
        cursor = self.conn.execute("SELECT * FROM _table WHERE id = ?", (table_id,))
        row =  cursor.fetchone()

        if not row:
            return None
        
        event = self.get_event(row["event_id"], load_tables=False)
        del row["event_id"]
        row["event"] = event

        owner = self.get_player(row["owner_id"])
        del row["owner_id"]
        row["owner"] = owner

        game = self.get_game(row["game_id"])
        del row["game_id"]
        row["game"] = game

        table = Table(**row)

        players = self.get_players_for_table(table_id=table_id)
        if players:
            table.players = {p.id: p for p in players}

        return table
    
    def add_game(self, game: Game):
        with self.conn:
            self.conn.execute("""
                INSERT INTO game (id, name, year, rank, description, thumbnail, minplayers, maxplayers, recommended_players)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (game.id, game.name, game.year, game.rank, game.description, game.thumbnail, game.minplayers, game.maxplayers, game.recommended_players))
    
        return self.get_game(game.id)


    def get_game(self, game_id: str):
        cursor = self.conn.execute("SELECT * FROM game WHERE id = ?", (game_id,))    
        row =  cursor.fetchone()

        return Game(**row) if row else None

    def get_tables_for_event(self, event_id: str):
        cursor = self.conn.execute("SELECT id FROM _table WHERE event_id = ?", (event_id,))
        rows = cursor.fetchall()

        if not rows:
            return None
        
        return [self.get_table(table_id=row["id"]) for row in rows]

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
        return Player(**row) if row else None

    def get_players_for_table(self, table_id: int):
        cursor = self.conn.execute("SELECT p.id, p.display_name, p.mention FROM player p LEFT JOIN table_player tp ON tp.player_id = p.id WHERE tp.table_id = ?", (table_id,))
        rows = cursor.fetchall()

        players = []
        for row in rows:
            players.append(Player(**row))

        return players

    def add_table_message(self, table: Table, message: int):
        with self.conn:
            self.conn.execute("UPDATE _table SET message = ? WHERE id = ?", (message, table.id))

        return self.get_table(table_id=table.id)

    def reset(self) -> None:
        with self.conn:
            self.conn.executescript("DROP TABLE IF EXISTS event; DROP TABLE IF EXISTS _table; DROP TABLE IF EXISTS player; DROP TABLE IF EXISTS games;")
            self._initialize_db()


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {k: v for k, v in zip(fields, row)}