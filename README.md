# Board Game Catalog

Local-first board game catalog starter with:

- SQLite database for owned games.
- Python standard-library API service.
- Static frontend that can be served by the Python service or by IIS.
- Local BoardGameGeek metadata CSV matching.
- Browser CSV upload for replacing the catalog with your owned games.

## Why SQLite

SQLite is the best starting database for this project because it is portable, requires no server install, works well for a personal catalog, and can later be migrated to SQL Server or PostgreSQL if the app grows.

## Run Locally

From this folder:

```powershell
C:\Users\hedge\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\service\api.py
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

The first run creates:

```text
data\board_games.sqlite
```

## API

```text
GET /api/health
GET /api/genres
GET /api/games
GET /api/games?players=4
GET /api/games?genre=Economic
GET /api/games?players=4&genre=Economic&maxComplexity=3
GET /api/metadata/status
POST /api/metadata/csv
POST /api/import/csv
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

`bgg_id` is preferred because BoardGameGeek names can be ambiguous. If the CSV only includes names, the app matches by normalized game name against the local metadata CSV.

Uploading a CSV always replaces the current catalog with the uploaded owned-game list. Games removed from your master CSV are removed from the app on the next import, and duplicate rows in the CSV are collapsed into one catalog entry.

## BoardGameGeek Metadata CSV

The import no longer calls the BoardGameGeek XML API. Instead, it looks for a local metadata CSV in this order:

1. The path in the `BGG_METADATA_CSV` environment variable.
2. `data\manual_metadata.csv`
3. `data\bgg_metadata.csv`
4. `data\bg_ranks.csv`

The BoardGameGeek ranks dump is available at:

```text
https://boardgamegeek.com/data_dumps/bg_ranks
```

Download the CSV from that page and save it as:

```text
data\bg_ranks.csv
```

You can also use the web page:

1. Upload the BGG ranks CSV using `Save Metadata CSV`.
2. Upload your owned-games CSV using `Import CSV`.

BGG's ranks dump provides names, IDs, ranks, and average rating. If your metadata CSV also includes fields like `minplayers`, `maxplayers`, `averageweight`, `genres`, `thumbnail`, or `url`, the app will use them too. Otherwise it keeps the owned game name, creates the BGG source link when an ID is available, and falls back to CSV-only values for missing fields.

## Manual Metadata While Waiting For API Access

To create a fillable metadata template from the current catalog:

```powershell
C:\Users\hedge\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\tools\export_manual_metadata_template.py
```

Edit:

```text
data\manual_metadata_template.csv
```

Fill in columns like `min_players`, `max_players`, `genres`, and `complexity`, then either upload it with `Save Metadata CSV` or save a copy as:

```text
data\manual_metadata.csv
```

## IIS Starting Point

For a simple local IIS setup:

1. Host `frontend` as a static IIS site.
2. Run the Python API service on `http://127.0.0.1:8000`.
3. If the frontend is served from a different local origin, keep API CORS enabled or configure an IIS reverse proxy to forward `/api/*` to the Python service.

For production-style IIS hosting, the next likely step is replacing the Python service with ASP.NET Core once the .NET Hosting Bundle is installed.
