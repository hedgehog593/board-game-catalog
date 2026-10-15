"""Explicit network check: run against BGG using an isolated catalog."""
import os
import unittest
from support import Sandbox, api, bgg_client, catalog_db


class LiveBggTests(unittest.TestCase):
    def test_real_fetch_refresh_and_reimport(self):
        token_path = os.environ.get("BGG_TEST_TOKEN_FILE")
        if token_path:
            from pathlib import Path
            token = Path(token_path).read_text(encoding="utf-8").strip()
        else:
            token = bgg_client.bgg_api_token()
        self.assertTrue(token, "Live BGG tests require a token file or BGG_API_TOKEN.")
        with Sandbox():
            os.environ["BGG_API_TOKEN"] = token
            catalog_db.sync_games(api.games_from_csv("name,bgg_id\nCATAN,13\n")["games"])
            result = api.refresh_games_from_bgg()
            self.assertEqual(result["updated"], 1)
            game = catalog_db.query_games()[0]
            self.assertGreater(game["maxPlayers"], 1)
            self.assertTrue(game["genres"])
            self.assertGreater(game["complexity"], 0)
            catalog_db.sync_games(api.games_from_csv("name,bgg_id\nCATAN,13\n")["games"])
            self.assertEqual(catalog_db.query_games()[0], game)


if __name__ == "__main__":
    unittest.main(verbosity=2)
