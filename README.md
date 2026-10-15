# Board Game Catalog

Local-first board game catalog starter with:

- SQLite database for owned games.
- Python standard-library API service.
- Static frontend that can be served by the Python service or by IIS.
- BoardGameGeek XML API metadata enrichment using a local token file.
- Browser CSV upload for syncing the catalog with your owned games.

## Why SQLite

SQLite is the best starting database for this project because it is portable, requires no server install, works well for a personal catalog, and can later be migrated to SQL Server or PostgreSQL if the app grows.

## Run Locally

From this folder:

```powershell
python .\service\api.py
```

Open:

```text
http://127.0.0.1:8000
```

Randomizer:

```text
http://127.0.0.1:8000/randomizer.html
```

Admin tools:

```text
http://127.0.0.1:8000/admin.html
```

The admin password is stored in:

```text
service\config\admin_password.txt
```

The service creates that file on first run if it does not exist. The starter password is:

```text
ChangeMe-BoardGames!
```

Change `service\config\admin_password.txt` and restart the service to use a different password. The repository includes `service\config\admin_password.example.txt` as a safe example; the real password file is ignored by Git.

The BoardGameGeek API token is stored in:

```text
service\config\bgg_api_token.txt
```

The repository includes `service\config\bgg_api_token.example.txt` as a safe example; the real token file is ignored by Git. You can also set `BGG_API_TOKEN` as an environment variable instead of using the file.

The first run creates:

```text
data\board_games.sqlite
```

## Run With Docker Desktop

From this folder:

```powershell
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:8000
```

The Docker container is named `board-game-catalog` and uses `restart: unless-stopped`, so Docker Desktop will restart it automatically when Docker starts. The container stores catalog data and admin config in the local `data` and `service\config` folders through bind mounts.

To have it come back after a computer restart, enable Docker Desktop's setting to start when you sign in. Once Docker Desktop starts, the `restart: unless-stopped` policy brings the `board-game-catalog` container back up automatically.

To access the site from another device on your home network, use the hosting computer's LAN address. For example:

```text
http://<hosting-computer-LAN-IP>:8000
```

Windows Firewall must allow inbound TCP traffic on port `8000` for the private network profile. From an elevated PowerShell window:

```powershell
.\tools\open_firewall_port.ps1
```

Or run the rule directly:

```powershell
netsh advfirewall firewall add rule name="Board Game Catalog Docker 8000" dir=in action=allow protocol=TCP localport=8000 profile=private
```

To stop it manually:

```powershell
docker compose down
```

## API

```text
GET /api/health
GET /api/genres
GET /api/games
GET /api/games?players=4
GET /api/games?genre=Economic
GET /api/games?players=4&genre=Economic&maxComplexity=3
POST /api/import/csv
POST /api/bgg/refresh
POST /api/admin/login
POST /api/admin/logout
POST /api/admin/status
```

## Randomizer

The Finder page includes a `Randomizer` button that opens a slot-machine style picker. The Randomizer loads your current catalog from the API and filters locally by player-count limit, one or more genres, and complexity range before choosing a game at random.

## Import Your Owned Games From CSV

Export your Excel list as `.csv`, then upload it from the web page.

Best CSV format:

```csv
name,bgg_id
CATAN,13
Ticket to Ride,9209
Pandemic,30549
```

Supported columns:

- `bgg_id`, `bggid`, `object_id`, or `objectid`
- `bbg_id` or `bbgid`, accepted as common typo aliases for `bgg_id`
- `name`, `game name`, `title`, `game`, or `boardgame`
- optional fallback columns if BGG cannot match a game: `min_players`, `max_players`, `genre`, `complexity`

`bgg_id` is preferred because BoardGameGeek names can be ambiguous. The CSV import syncs the owned-game list and keeps any BGG metadata that is already in the catalog.

Uploading a CSV syncs the app to your master owned-game list. Existing BGG metadata is preserved, changed rows are updated, and games removed from your master CSV are removed from the app after the import is parsed.

Use the Admin `Refresh BGG Data` button to update current catalog games that already have BGG IDs without re-uploading the CSV.

## Useful Tips

- Treat your spreadsheet as the master ownership list. Export it to CSV, then import it from Admin when games are added, renamed, or removed.
- CSV import syncs ownership only. It preserves existing BGG metadata, but it does not pull fresh BGG metadata by itself.
- After importing the CSV, click `Refresh BGG Data` in Admin to fetch players, genres, complexity, images, and BGG source links for rows that have BGG IDs.
- Keep BGG IDs in the CSV where possible. Title-only matching is useful, but BGG IDs avoid ambiguous names and edition mix-ups.

## Automated Tests

Every Docker image build runs the API suite and Chromium user journeys before
creating the runtime image. A failing test fails the build. The tests use a
temporary SQLite database, test credentials, and simulated BGG responses; they
never change your owned catalog or contact BGG during an ordinary build.
Docker can reuse a passing cached test layer when the source is unchanged.

Coverage includes Finder searching/filtering/reset, Randomizer handle and
filtered selection, empty results, Admin login/import/refresh/reimport/logout,
desktop/mobile dropdown stacking, authentication, invalid imports, duplicate
rows, metadata preservation, and BGG parsing, batching, retries and failures.

```powershell
docker compose build
# Force a fresh test run even if the source has not changed:
docker compose build --no-cache
# Live BGG fetch and DB refresh, in addition to the ordinary tests:
docker build --no-cache --build-arg RUN_LIVE_BGG_TESTS=1 --secret id=bgg_api_token,src=service/config/bgg_api_token.txt -t board-game-catalog .
```

The live check fetches CATAN (BGG ID 13), verifies its metadata in a disposable
database, and checks that reimport preserves it. It requires network access and
a valid token; BGG outages or authorization failures fail that explicit build.
The token is mounted as a BuildKit secret, not copied into an image layer.

To run outside Docker (Python 3.12+):

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r tests/requirements.txt
.venv/Scripts/python -m playwright install chromium
.venv/Scripts/python -m unittest discover -s tests -p "test_*.py" -v
# API tests alone do not require Playwright:
python -m unittest discover -s tests -p "test_api.py" -v
python tests/live_bgg.py
```

Browser runs save screenshots and Playwright traces to ignored `test-results/`.
Open a trace with `python -m playwright show-trace <trace.zip>`.
GitHub Actions builds and tests pushes and pull requests. For live BGG testing,
add a repository Actions secret named `BGG_API_TOKEN` and manually run the
workflow with `live_bgg` enabled. Test tools remain in the build stage; the
running site stays dependency-light.

## IIS Starting Point

For a simple local IIS setup:

1. Host `frontend` as a static IIS site.
2. Run the Python API service on `http://127.0.0.1:8000`.
3. If the frontend is served from a different local origin, keep API CORS enabled or configure an IIS reverse proxy to forward `/api/*` to the Python service.

For production-style IIS hosting, the next likely step is replacing the Python service with ASP.NET Core once the .NET Hosting Bundle is installed.
