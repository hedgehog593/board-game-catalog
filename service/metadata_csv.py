from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
DEFAULT_METADATA_PATHS = [
    DATA_DIR / "manual_metadata.csv",
    DATA_DIR / "bgg_metadata.csv",
    DATA_DIR / "bg_ranks.csv",
]
DEFAULT_UPLOAD_PATH = DATA_DIR / "bg_ranks.csv"


@dataclass
class MetadataCatalog:
    by_id: dict[int, dict]
    by_name: dict[str, dict]
    source: str | None

    @property
    def available(self) -> bool:
        return bool(self.by_id or self.by_name)


def load_metadata_catalog() -> MetadataCatalog:
    path = metadata_path()
    if path is None:
        return MetadataCatalog({}, {}, None)

    by_id: dict[int, dict] = {}
    by_name: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            normalized = normalize_row(row)
            game = metadata_game_from_row(normalized)
            if game is None:
                continue
            bgg_id = game["bgg_id"]
            if bgg_id is not None and bgg_id > 0:
                by_id[bgg_id] = game
            by_name.setdefault(normalize_name(game["name"]), game)

    return MetadataCatalog(by_id, by_name, str(path))


def metadata_path() -> Path | None:
    configured = os.environ.get("BGG_METADATA_CSV")
    paths = [Path(configured)] if configured else DEFAULT_METADATA_PATHS
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def metadata_game_from_row(row: dict[str, str]) -> dict | None:
    name = first_value(row, "name", "gamename", "primaryname", "title", "boardgame")
    bgg_id = parse_optional_int(first_value(row, "id", "bggid", "bgg_id", "objectid", "object_id"))
    if not name and bgg_id is None:
        return None

    display_name = name or f"BGG {bgg_id}"
    min_players = parse_optional_int(first_value(row, "minplayers", "min_players", "minimumplayers", "min")) or 1
    max_players = parse_optional_int(first_value(row, "maxplayers", "max_players", "maximumplayers", "max")) or min_players
    complexity = parse_optional_float(first_value(row, "averageweight", "average_weight", "complexity", "weight"))
    url = first_value(row, "url", "sourceurl", "source_url")
    thumbnail = first_value(row, "thumbnail", "thumbnailurl", "thumbnail_url")
    image = first_value(row, "image", "imageurl", "image_url")

    return {
        "bgg_id": bgg_id or stable_negative_id(display_name),
        "name": display_name,
        "min_players": min_players,
        "max_players": max_players,
        "genres": parse_genres(first_value(row, "genre", "genres", "category", "categories")),
        "complexity": complexity,
        "source_url": source_url(bgg_id, url),
        "image_url": normalize_url(image),
        "thumbnail_url": normalize_url(thumbnail),
    }


def source_url(bgg_id: int | None, url: str | None) -> str | None:
    if url:
        return normalize_url(url)
    if bgg_id:
        return f"https://boardgamegeek.com/boardgame/{bgg_id}"
    return None


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("/"):
        return f"https://boardgamegeek.com{value}"
    return value


def parse_genres(value: str | None) -> list[str]:
    if not value:
        return []
    separators = ["|", ";"]
    normalized = value
    for separator in separators:
        normalized = normalized.replace(separator, ",")
    return [genre.strip() for genre in normalized.split(",") if genre.strip()]


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {normalize_key(key): value.strip() for key, value in row.items() if key is not None and value is not None}


def normalize_key(key: str) -> str:
    return "".join(character for character in key.lower() if character.isalnum())


def normalize_name(name: str) -> str:
    return " ".join(name.casefold().replace("&", "and").split())


def first_value(row: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = row.get(normalize_key(name))
        if value:
            return value
    return None


def parse_optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_optional_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return round(float(value), 2)
    except ValueError:
        return None


def stable_negative_id(name: str) -> int:
    import zlib

    return -zlib.crc32(name.casefold().encode("utf-8"))
