from contextlib import ExitStack
import gc
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))
import api
import bgg_client
import catalog_db

PASSWORD = "test-only-password"
CSV = "name,bgg_id,min_players,max_players,genre,complexity\nCATAN,13,3,4,Economic,2.3\nPandemic,30549,2,4,Medical,2.4\nSolo Puzzle,,1,1,Puzzle,1.1\n"
XML = b'''<items><item type="boardgame" id="13"><name type="primary" value="CATAN"/>
<minplayers value="3"/><maxplayers value="4"/>
<link type="boardgamecategory" value="Economic"/>
<statistics><ratings><averageweight value="2.31"/></ratings></statistics>
<image>https://example.com/catan.jpg</image></item></items>'''


class Response:
    status = 200

    def __init__(self, body=XML, status=200):
        self.body, self.status = body, status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


class Sandbox:
    """Run the real HTTP service with disposable data and credentials."""
    def __enter__(self):
        self.stack = ExitStack()
        folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(catalog_db, "DB_PATH", folder / "catalog.sqlite"))
        self.stack.enter_context(patch.object(api, "DB_PATH", folder / "catalog.sqlite"))
        self.stack.enter_context(patch.object(catalog_db, "DATA_DIR", folder))
        self.stack.enter_context(patch.object(api, "CONFIG_DIR", folder))
        self.stack.enter_context(patch.object(api, "PASSWORD_FILE", folder / "password.txt"))
        self.stack.enter_context(patch.object(api, "SESSION_SECRET_FILE", folder / "session.txt"))
        self.stack.enter_context(patch.object(bgg_client, "TOKEN_FILE", folder / "token.txt"))
        self.stack.enter_context(patch.dict("os.environ", {"BGG_API_TOKEN": "test-token"}))
        api.PASSWORD_FILE.write_text(PASSWORD, encoding="utf-8")
        catalog_db.initialize_database(seed=False)
        catalog_db.sync_games(api.games_from_csv(CSV)["games"])
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), api.CatalogHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        gc.collect()
        self.stack.close()
