PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bgg_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    min_players INTEGER NOT NULL,
    max_players INTEGER NOT NULL,
    complexity REAL,
    complexity_label TEXT,
    source_url TEXT,
    image_url TEXT,
    thumbnail_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_genres (
    game_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    PRIMARY KEY (game_id, genre_id),
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_games_player_range
ON games (min_players, max_players);

CREATE INDEX IF NOT EXISTS idx_games_complexity
ON games (complexity);
