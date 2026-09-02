from __future__ import annotations

import json
import sqlite3
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
DB_PATH = DATA_DIR / "board_games.sqlite"
SCHEMA_PATH = DATA_DIR / "schema.sql"
SEED_PATH = DATA_DIR / "seed_games.json"


def complexity_label(value: float | None) -> str:
    if value is None:
        return "Unrated"
    if value < 2:
        return "Light"
    if value < 3:
        return "Medium"
    if value < 4:
        return "Heavy"
    return "Very Heavy"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(seed: bool = True) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if seed and not has_games(connection):
            upsert_games(load_seed_games(), connection)


def load_seed_games() -> list[dict]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def has_games(connection: sqlite3.Connection) -> bool:
    return connection.execute("SELECT EXISTS (SELECT 1 FROM games)").fetchone()[0] == 1


def replace_games(games: list[dict]) -> None:
    with connect() as db:
        db.execute("DELETE FROM game_genres")
        db.execute("DELETE FROM genres")
        db.execute("DELETE FROM games")
        upsert_games(games, db)


def upsert_games(games: list[dict], connection: sqlite3.Connection | None = None) -> None:
    owns_connection = connection is None
    db = connection or connect()
    try:
        for game in games:
            complexity = game.get("complexity")
            db.execute(
                """
                INSERT INTO games (
                    bgg_id, name, min_players, max_players, complexity,
                    complexity_label, source_url, image_url, thumbnail_url, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bgg_id) DO UPDATE SET
                    name = excluded.name,
                    min_players = excluded.min_players,
                    max_players = excluded.max_players,
                    complexity = excluded.complexity,
                    complexity_label = excluded.complexity_label,
                    source_url = excluded.source_url,
                    image_url = excluded.image_url,
                    thumbnail_url = excluded.thumbnail_url,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    game.get("bgg_id"),
                    game["name"],
                    game["min_players"],
                    game["max_players"],
                    complexity,
                    complexity_label(complexity),
                    game.get("source_url"),
                    game.get("image_url"),
                    game.get("thumbnail_url"),
                ),
            )

            game_id = db.execute(
                "SELECT id FROM games WHERE bgg_id = ?",
                (game.get("bgg_id"),),
            ).fetchone()["id"]

            db.execute("DELETE FROM game_genres WHERE game_id = ?", (game_id,))
            for genre in game.get("genres", []):
                db.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (genre,))
                genre_id = db.execute(
                    "SELECT id FROM genres WHERE name = ?",
                    (genre,),
                ).fetchone()["id"]
                db.execute(
                    "INSERT OR IGNORE INTO game_genres (game_id, genre_id) VALUES (?, ?)",
                    (game_id, genre_id),
                )
        db.commit()
    finally:
        if owns_connection:
            db.close()


def row_to_game(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "bggId": row["bgg_id"],
        "name": row["name"],
        "minPlayers": row["min_players"],
        "maxPlayers": row["max_players"],
        "complexity": row["complexity"],
        "complexityLabel": row["complexity_label"],
        "genres": row["genres"].split("|") if row["genres"] else [],
        "sourceUrl": row["source_url"],
        "imageUrl": row["image_url"],
        "thumbnailUrl": row["thumbnail_url"],
    }


def query_games(players: int | None = None, genre: str | None = None, max_complexity: float | None = None) -> list[dict]:
    where = []
    params: list[object] = []

    if players is not None:
        where.append("? BETWEEN g.min_players AND g.max_players")
        params.append(players)
    if genre:
        where.append(
            """
            EXISTS (
                SELECT 1
                FROM game_genres gg2
                JOIN genres ge2 ON ge2.id = gg2.genre_id
                WHERE gg2.game_id = g.id AND ge2.name = ?
            )
            """
        )
        params.append(genre)
    if max_complexity is not None:
        where.append("(g.complexity IS NULL OR g.complexity <= ?)")
        params.append(max_complexity)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT
            g.*,
            GROUP_CONCAT(ge.name, '|') AS genres
        FROM games g
        LEFT JOIN game_genres gg ON gg.game_id = g.id
        LEFT JOIN genres ge ON ge.id = gg.genre_id
        {where_sql}
        GROUP BY g.id
        ORDER BY g.name COLLATE NOCASE
    """

    with connect() as db:
        return [row_to_game(row) for row in db.execute(sql, params).fetchall()]


def find_game_by_bgg_id(bgg_id: int) -> dict | None:
    return find_game("WHERE g.bgg_id = ?", [bgg_id])


def find_game_by_name(name: str) -> dict | None:
    return find_game("WHERE LOWER(g.name) = LOWER(?)", [name])


def find_game(where_sql: str, params: list[object]) -> dict | None:
    sql = f"""
        SELECT
            g.*,
            GROUP_CONCAT(ge.name, '|') AS genres
        FROM games g
        LEFT JOIN game_genres gg ON gg.game_id = g.id
        LEFT JOIN genres ge ON ge.id = gg.genre_id
        {where_sql}
        GROUP BY g.id
        LIMIT 1
    """
    with connect() as db:
        row = db.execute(sql, params).fetchone()
        return row_to_game(row) if row else None


def api_game_to_record(game: dict) -> dict:
    return {
        "bgg_id": game["bggId"],
        "name": game["name"],
        "min_players": game["minPlayers"],
        "max_players": game["maxPlayers"],
        "genres": game["genres"],
        "complexity": game["complexity"],
        "source_url": game["sourceUrl"],
        "image_url": game["imageUrl"],
        "thumbnail_url": game["thumbnailUrl"],
    }


def list_genres() -> list[str]:
    with connect() as db:
        return [row["name"] for row in db.execute("SELECT name FROM genres ORDER BY name COLLATE NOCASE")]


if __name__ == "__main__":
    initialize_database(seed=True)
    print(f"Initialized {DB_PATH}")
