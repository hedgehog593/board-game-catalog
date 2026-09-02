from __future__ import annotations

import argparse
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "service"))
from bgg_client import collection_ids, import_games
from catalog_db import initialize_database, upsert_games

def main() -> None:
    parser = argparse.ArgumentParser(description="Import owned board games from BoardGameGeek.")
    parser.add_argument("--username", help="BGG username. Imports owned boardgames from the public collection.")
    parser.add_argument("--ids", help="Comma-separated BGG game IDs to import.")
    args = parser.parse_args()

    if not args.username and not args.ids:
        parser.error("Provide --username or --ids.")

    bgg_ids = collection_ids(args.username) if args.username else [int(value.strip()) for value in args.ids.split(",")]
    games = import_games(bgg_ids)
    initialize_database(seed=False)
    upsert_games(games)
    print(f"Imported {len(games)} games from BoardGameGeek.")


if __name__ == "__main__":
    main()
