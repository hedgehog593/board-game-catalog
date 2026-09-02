from __future__ import annotations

import csv
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "service"))
from catalog_db import initialize_database, query_games

APP_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = APP_ROOT / "data" / "manual_metadata_template.csv"


def main() -> None:
    initialize_database(seed=False)
    games = query_games()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "name",
                "bgg_id",
                "min_players",
                "max_players",
                "genres",
                "complexity",
                "source_url",
            ],
        )
        writer.writeheader()
        for game in games:
            writer.writerow(
                {
                    "name": game["name"],
                    "bgg_id": game["bggId"] if game["bggId"] > 0 else "",
                    "min_players": game["minPlayers"] if game["minPlayers"] != 1 else "",
                    "max_players": game["maxPlayers"] if game["maxPlayers"] != 1 else "",
                    "genres": "; ".join(game["genres"]),
                    "complexity": game["complexity"] or "",
                    "source_url": game["sourceUrl"] or "",
                }
            )

    print(f"Wrote {len(games)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
