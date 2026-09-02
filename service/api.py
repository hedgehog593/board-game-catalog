from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import secrets
import zlib
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from catalog_db import (
    DB_PATH,
    api_game_to_record,
    find_game_by_name,
    initialize_database,
    list_genres,
    query_games,
    replace_games,
)
from metadata_csv import DEFAULT_UPLOAD_PATH, load_metadata_catalog, normalize_name

HOST = "127.0.0.1"
PORT = 8000
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
CONFIG_DIR = Path(__file__).resolve().parent / "config"
PASSWORD_FILE = CONFIG_DIR / "admin_password.txt"
SESSION_SECRET_FILE = CONFIG_DIR / "session_secret.txt"
ADMIN_COOKIE = "board_game_admin"


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
            self.send_json({"ok": True, "database": str(DB_PATH)})
            return
        if parsed.path == "/api/metadata/status":
            if not self.require_admin():
                return
            self.handle_metadata_status()
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
        if parsed.path == "/api/metadata/csv":
            if not self.require_admin():
                return
            self.handle_metadata_upload()
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

    def handle_metadata_status(self) -> None:
        metadata = load_metadata_catalog()
        self.send_json(
            {
                "available": metadata.available,
                "source": metadata.source,
                "records": len(metadata.by_id) or len(metadata.by_name),
            }
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

        replace_games(result["games"])
        self.send_json(
            {
                "mode": "replace",
                "imported": len(result["games"]),
                "matchedOnBgg": result["matched_on_bgg"],
                "matchedFromMetadata": result["matched_from_metadata"],
                "metadataSource": result["metadata_source"],
                "unmatched": result["unmatched"],
                "bggUnavailable": False,
            }
        )

    def handle_metadata_upload(self) -> None:
        try:
            upload = self.read_uploaded_csv()
            rows = list(csv.DictReader(io.StringIO(upload)))
            if not rows:
                raise ValueError("The metadata CSV must include a header row and at least one game.")
            DEFAULT_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_UPLOAD_PATH.write_text(upload, encoding="utf-8")
            metadata = load_metadata_catalog()
        except ValueError as error:
            self.send_json({"error": str(error)}, status=400)
            return
        except Exception as error:
            self.send_json({"error": f"Metadata upload failed: {error}"}, status=502)
            return

        self.send_json(
            {
                "saved": True,
                "source": str(DEFAULT_UPLOAD_PATH),
                "records": len(metadata.by_id) or len(metadata.by_name),
            }
        )

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

    metadata = load_metadata_catalog()
    cached_games: list[dict] = []
    metadata_games: list[dict] = []
    fallback_games: list[dict] = []
    unmatched: list[str] = []

    for row in rows:
        normalized = normalize_row(row)
        name = first_value(normalized, "name", "gamename", "title", "game", "boardgame")
        bgg_id_text = first_value(normalized, "bggid", "bgg_id", "bbgid", "bbg_id", "objectid", "object_id")
        bgg_id = parse_bgg_id(bgg_id_text) if bgg_id_text else None

        metadata_game = None
        if bgg_id is not None:
            metadata_game = metadata.by_id.get(bgg_id)
        if metadata_game is None and name:
            metadata_game = metadata.by_name.get(normalize_name(name))

        if metadata_game is not None:
            metadata_games.append(merge_owned_row(metadata_game, normalized, name, bgg_id))
            continue

        if not name:
            continue

        cached = find_game_by_name(name)
        if cached and has_bgg_metadata(cached):
            cached_games.append(api_game_to_record(cached))
            continue

        unmatched.append(name)
        fallback_games.append(fallback_game_from_csv(name, normalized, bgg_id=bgg_id))

    if not metadata_games and not cached_games and not fallback_games:
        raise ValueError("The CSV must include a name, game name, title, game, or bgg_id column.")

    games = dedupe_games(cached_games + metadata_games + fallback_games)
    return {
        "games": games,
        "matched_on_bgg": len(cached_games) + len(metadata_games),
        "matched_from_metadata": len(metadata_games),
        "unmatched": unmatched,
        "metadata_source": metadata.source,
    }


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
    if owned_name and not merged.get("name"):
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
    return merged


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
            continue
        seen.add(key)
        unique_games.append(game)
    return unique_games


def main() -> None:
    initialize_database(seed=True)
    server = ThreadingHTTPServer((HOST, PORT), CatalogHandler)
    print(f"Board game catalog running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
