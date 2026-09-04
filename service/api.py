from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import zlib
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from catalog_db import (
    DB_PATH,
    api_game_to_record,
    find_game_by_bgg_id,
    find_game_by_name,
    initialize_database,
    list_genres,
    query_games,
    sync_games,
    upsert_games,
)
from bgg_client import bgg_api_token, import_games

HOST = os.environ.get("CATALOG_HOST", "127.0.0.1")
PORT = int(os.environ.get("CATALOG_PORT", "8000"))
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
CONFIG_DIR = Path(__file__).resolve().parent / "config"
PASSWORD_FILE = CONFIG_DIR / "admin_password.txt"
SESSION_SECRET_FILE = CONFIG_DIR / "session_secret.txt"
ADMIN_COOKIE = "board_game_admin"
APP_VERSION = "1.1-sync-import"


def parse_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


class CatalogHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/games":
            self.handle_games(parsed.query)
            return
        if parsed.path == "/api/genres":
            self.send_json({"genres": list_genres()})
            return
        if parsed.path == "/api/health":
            self.send_json(
                {
                    "ok": True,
                    "version": APP_VERSION,
                    "database": str(DB_PATH),
                    "bggTokenConfigured": bool(bgg_api_token()),
                }
            )
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/admin/login":
            self.handle_admin_login()
            return
        if parsed.path == "/api/admin/logout":
            self.handle_admin_logout()
            return
        if parsed.path == "/api/admin/status":
            self.send_json({"authenticated": self.is_admin()})
            return
        if parsed.path == "/api/import/csv":
            if not self.require_admin():
                return
            self.handle_csv_import()
            return
        if parsed.path == "/api/bgg/refresh":
            if not self.require_admin():
                return
            self.handle_bgg_refresh()
            return
        self.send_error(404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def handle_games(self, query: str) -> None:
        params = parse_qs(query)
        try:
            games = query_games(
                players=parse_int(first(params, "players")),
                genre=first(params, "genre"),
                max_complexity=parse_float(first(params, "maxComplexity")),
            )
        except ValueError:
            self.send_json({"error": "Invalid filter value."}, status=400)
            return
        self.send_json({"games": games, "count": len(games)})

    def handle_admin_login(self) -> None:
        try:
            payload = self.read_json()
        except ValueError as error:
            self.send_json({"error": str(error)}, status=400)
            return

        if not hmac.compare_digest(payload.get("password", ""), admin_password()):
            self.send_json({"error": "Invalid password."}, status=401)
            return

        self.send_json(
            {"authenticated": True},
            headers={"Set-Cookie": admin_cookie_header()},
        )

    def handle_admin_logout(self) -> None:
        self.send_json(
            {"authenticated": False},
            headers={"Set-Cookie": f"{ADMIN_COOKIE}=; Path=/; Max-Age=0; SameSite=Strict; HttpOnly"},
        )

    def handle_csv_import(self) -> None:
        try:
            upload = self.read_uploaded_csv()
            result = games_from_csv(upload)
        except ValueError as error:
            self.send_json({"error": str(error)}, status=400)
            return
        except Exception as error:
            self.send_json({"error": f"Import failed: {error}"}, status=502)
            return

        sync_result = sync_games(result["games"])
        self.send_json(
            {
                "mode": "sync",
                "imported": len(result["games"]),
                "matchedOnBgg": result["matched_on_bgg"],
                "unmatched": result["unmatched"],
                "removed": sync_result["removed"],
                "bggUnavailable": False,
            }
        )

    def handle_bgg_refresh(self) -> None:
        try:
            result = refresh_games_from_bgg()
        except Exception as error:
            self.send_json({"error": f"BGG refresh failed: {error}"}, status=502)
            return

        self.send_json(result)

    def read_uploaded_csv(self) -> str:
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            raise ValueError("Upload a CSV file.")
        body = self.rfile.read(length)

        if content_type.startswith("multipart/form-data"):
            return read_multipart_csv(content_type, body)

        return body.decode("utf-8-sig")

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            raise ValueError("Request body is required.")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("Request body must be valid JSON.")

    def serve_static(self, request_path: str) -> None:
        if request_path in ("", "/"):
            target = FRONTEND_DIR / "index.html"
        else:
            safe_path = request_path.lstrip("/").replace("/", "\\")
            target = (FRONTEND_DIR / safe_path).resolve()
            if not str(target).startswith(str(FRONTEND_DIR.resolve())):
                self.send_error(403)
                return

        if not target.exists() or target.is_dir():
            self.send_error(404)
            return

        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict, status: int = 200, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def require_admin(self) -> bool:
        if self.is_admin():
            return True
        self.send_json({"error": "Admin login required."}, status=401)
        return False

    def is_admin(self) -> bool:
        header = self.headers.get("Cookie", "")
        if not header:
            return False
        jar = cookies.SimpleCookie()
        jar.load(header)
        token = jar.get(ADMIN_COOKIE)
        return bool(token and hmac.compare_digest(token.value, admin_token()))

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def first(params: dict[str, list[str]], name: str) -> str | None:
    values = params.get(name)
    return values[0] if values else None


def admin_password() -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not PASSWORD_FILE.exists():
        PASSWORD_FILE.write_text("ChangeMe-BoardGames!\n", encoding="utf-8")
    return PASSWORD_FILE.read_text(encoding="utf-8").strip()


def admin_token() -> str:
    payload = f"admin:{admin_password()}".encode("utf-8")
    return hmac.new(session_secret(), payload, hashlib.sha256).hexdigest()


def admin_cookie_header() -> str:
    return f"{ADMIN_COOKIE}={admin_token()}; Path=/; SameSite=Strict; HttpOnly"


def session_secret() -> bytes:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSION_SECRET_FILE.exists():
        SESSION_SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
    return SESSION_SECRET_FILE.read_text(encoding="utf-8").strip().encode("utf-8")


def read_multipart_csv(content_type: str, body: bytes) -> str:
    boundary = multipart_boundary(content_type)
    delimiter = b"--" + boundary

    for part in body.split(delimiter):
        part = part.strip()
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue

        headers, content = part.split(b"\r\n\r\n", 1)
        if b'name="file"' not in headers:
            continue

        content = content.removesuffix(b"\r\n")
        content = content.removesuffix(b"--")
        if not content:
            raise ValueError("Upload a CSV file.")
        return content.decode("utf-8-sig")

    raise ValueError("Upload a CSV file.")


def multipart_boundary(content_type: str) -> bytes:
    for item in content_type.split(";"):
        item = item.strip()
        if item.startswith("boundary="):
            boundary = item.removeprefix("boundary=").strip('"')
            return boundary.encode("utf-8")
    raise ValueError("Invalid CSV upload: missing multipart boundary.")


def games_from_csv(csv_text: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    if not rows:
        raise ValueError("The CSV must include a header row and at least one game.")

    imported_games: list[dict] = []
    unmatched: list[str] = []
    matched_on_bgg = 0

    for row in rows:
        normalized = normalize_row(row)
        name = first_value(normalized, "name", "gamename", "title", "game", "boardgame")
        bgg_id_text = first_value(normalized, "bggid", "bgg_id", "bbgid", "bbg_id", "objectid", "object_id")
        bgg_id = parse_bgg_id(bgg_id_text) if bgg_id_text else None

        if not name:
            continue

        if bgg_id is None:
            cached = find_game_by_name(name)
            if cached and cached.get("bggId") and cached["bggId"] > 0:
                bgg_id = cached["bggId"]

        game = preserve_existing_metadata(fallback_game_from_csv(name, normalized, bgg_id=bgg_id), name, bgg_id)
        if game.get("source_url") and (game.get("complexity") is not None or game.get("genres")):
            matched_on_bgg += 1
        else:
            unmatched.append(name)
        imported_games.append(game)

    if not imported_games:
        raise ValueError("The CSV must include a name, game name, title, game, or bgg_id column.")

    games = dedupe_games(imported_games)
    return {
        "games": games,
        "matched_on_bgg": matched_on_bgg,
        "unmatched": unmatched,
    }


def refresh_games_from_bgg() -> dict:
    current_games = query_games()
    if not current_games:
        return {"updated": 0, "skippedMissingIds": 0, "unmatched": []}

    bgg_ids: list[int] = []
    rows_by_bgg_id: dict[int, list[dict]] = {}
    fallback_games: list[dict] = []
    unmatched: list[str] = []
    skipped_missing_ids = 0

    for game in current_games:
        bgg_id = refresh_bgg_id(game)
        if bgg_id is not None:
            bgg_ids.append(bgg_id)
            rows_by_bgg_id.setdefault(bgg_id, []).append(game)
            continue

        skipped_missing_ids += 1
        fallback_games.append(api_game_to_record(game))

    refreshed_games = []
    if bgg_ids:
        for game in import_games(bgg_ids):
            for current_game in rows_by_bgg_id.get(game["bgg_id"], []):
                owned_bgg_id = current_game.get("bggId")
                refreshed = merge_owned_row(game, {}, current_game["name"], owned_bgg_id)
                if isinstance(owned_bgg_id, int) and owned_bgg_id < 0:
                    refreshed["bgg_id"] = owned_bgg_id
                    refreshed["source_url"] = game.get("source_url")
                refreshed_games.append(refreshed)

    refreshed_local_ids = {game["bgg_id"] for game in refreshed_games}
    for current_games_for_bgg_id in rows_by_bgg_id.values():
        for current_game in current_games_for_bgg_id:
            if current_game["bggId"] not in refreshed_local_ids:
                unmatched.append(current_game["name"])
                fallback_games.append(api_game_to_record(current_game))

    games = dedupe_games(refreshed_games + fallback_games)
    upsert_games(games)
    return {
        "updated": len(refreshed_games),
        "skippedMissingIds": skipped_missing_ids,
        "unmatched": sorted(set(unmatched)),
    }


def refresh_bgg_id(game: dict) -> int | None:
    bgg_id = game.get("bggId")
    if isinstance(bgg_id, int) and bgg_id > 0:
        return bgg_id

    source_url = game.get("sourceUrl") or ""
    marker = "boardgame/"
    if marker not in source_url:
        return None
    value = source_url.split(marker, 1)[1].split("/", 1)[0]
    return int(value) if value.isdigit() else None


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {normalize_key(key): value.strip() for key, value in row.items() if key is not None and value is not None}


def normalize_key(key: str) -> str:
    return "".join(character for character in key.lower() if character.isalnum())


def first_value(row: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = row.get(normalize_key(name))
        if value:
            return value
    return None


def parse_bgg_id(value: str) -> int:
    cleaned = value.strip()
    if not cleaned.isdigit():
        raise ValueError(f"Invalid BGG ID: {value}")
    return int(cleaned)


def has_bgg_metadata(game: dict) -> bool:
    return bool(game["sourceUrl"] and game["genres"] and game["complexity"] is not None)


def merge_owned_row(metadata_game: dict, row: dict[str, str], owned_name: str | None, owned_bgg_id: int | None) -> dict:
    merged = dict(metadata_game)
    if owned_name:
        merged["name"] = owned_name
    if owned_bgg_id and (not merged.get("bgg_id") or merged["bgg_id"] < 0):
        merged["bgg_id"] = owned_bgg_id
        merged["source_url"] = f"https://boardgamegeek.com/boardgame/{owned_bgg_id}"

    fallback = fallback_game_from_csv(owned_name or merged["name"], row, bgg_id=owned_bgg_id)
    for key in ("min_players", "max_players", "complexity"):
        if merged.get(key) is None:
            merged[key] = fallback[key]
    if not merged.get("genres"):
        merged["genres"] = fallback["genres"]
    return preserve_existing_metadata(merged, owned_name, owned_bgg_id)


def preserve_existing_metadata(game: dict, owned_name: str | None, owned_bgg_id: int | None) -> dict:
    existing = existing_catalog_game(owned_name, owned_bgg_id)
    if not existing:
        return game

    preserved = dict(game)
    existing_record = api_game_to_record(existing)

    for key in ("min_players", "max_players"):
        if preserved.get(key) in (None, 1) and existing_record.get(key) not in (None, 1):
            preserved[key] = existing_record[key]

    for key in ("complexity", "source_url", "image_url", "thumbnail_url"):
        if preserved.get(key) in (None, "") and existing_record.get(key) not in (None, ""):
            preserved[key] = existing_record[key]

    if not preserved.get("genres") and existing_record.get("genres"):
        preserved["genres"] = existing_record["genres"]

    return preserved


def existing_catalog_game(owned_name: str | None, owned_bgg_id: int | None) -> dict | None:
    if owned_bgg_id and owned_bgg_id > 0:
        found = find_game_by_bgg_id(owned_bgg_id)
        if found:
            return found
    if owned_name:
        return find_game_by_name(owned_name)
    return None


def fallback_game_from_csv(name: str, row: dict[str, str], bgg_id: int | None = None) -> dict:
    min_players = int(first_value(row, "minplayers", "minimumplayers", "min") or 1)
    max_players = int(first_value(row, "maxplayers", "maximumplayers", "max") or min_players)
    complexity_text = first_value(row, "complexity", "weight", "averageweight")
    genres_text = first_value(row, "genre", "genres", "category", "categories") or ""
    fallback_bgg_id = bgg_id or -zlib.crc32(name.casefold().encode("utf-8"))
    return {
        "bgg_id": fallback_bgg_id,
        "name": name,
        "min_players": min_players,
        "max_players": max_players,
        "genres": [genre.strip() for genre in genres_text.replace("|", ";").split(";") if genre.strip()],
        "complexity": float(complexity_text) if complexity_text else None,
        "source_url": f"https://boardgamegeek.com/boardgame/{bgg_id}" if bgg_id else None,
        "image_url": None,
        "thumbnail_url": None,
    }


def dedupe_games(games: list[dict]) -> list[dict]:
    seen: set[object] = set()
    unique_games: list[dict] = []
    for game in games:
        key = game.get("bgg_id") if game.get("bgg_id") is not None else game["name"].casefold()
        if key in seen:
            game = dict(game)
            source_bgg_id = game.get("bgg_id")
            if isinstance(source_bgg_id, int) and source_bgg_id > 0:
                game["source_url"] = game.get("source_url") or f"https://boardgamegeek.com/boardgame/{source_bgg_id}"
            game["bgg_id"] = stable_local_id(game["name"], source_bgg_id)
            key = game["bgg_id"]
            while key in seen:
                game["bgg_id"] -= 1
                key = game["bgg_id"]
        seen.add(key)
        unique_games.append(game)
    return unique_games


def stable_local_id(name: str, source_bgg_id: object) -> int:
    seed = f"{name.casefold()}:{source_bgg_id}"
    return -zlib.crc32(seed.encode("utf-8"))


def main() -> None:
    initialize_database(seed=True)
    server = ThreadingHTTPServer((HOST, PORT), CatalogHandler)
    print(f"Board game catalog running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
