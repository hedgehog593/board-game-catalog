from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BGG_THING_URL = "https://boardgamegeek.com/xmlapi2/thing"
BGG_COLLECTION_URL = "https://boardgamegeek.com/xmlapi2/collection"
BGG_SEARCH_URL = "https://boardgamegeek.com/xmlapi2/search"
MAX_IDS_PER_REQUEST = 20
CONFIG_DIR = Path(__file__).resolve().parent / "config"
TOKEN_FILE = CONFIG_DIR / "bgg_api_token.txt"


def fetch_xml(url: str, retries: int = 4) -> ET.Element:
    for attempt in range(retries):
        request = urllib.request.Request(url, headers=request_headers())
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status == 202:
                    time.sleep(5)
                    continue
                return ET.fromstring(response.read())
        except urllib.error.HTTPError as error:
            if error.code in (202, 429, 500, 503) and attempt < retries - 1:
                time.sleep(5)
                continue
            raise
    raise RuntimeError(f"BGG did not return ready data after {retries} attempts: {url}")


def request_headers() -> dict[str, str]:
    headers = {"User-Agent": "LocalBoardGameCatalog/0.2"}
    token = bgg_api_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def bgg_api_token() -> str | None:
    token = os.environ.get("BGG_API_TOKEN")
    if token:
        return token.strip()
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    return None


def chunks(values: list[int], size: int) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def collection_ids(username: str) -> list[int]:
    query = urllib.parse.urlencode(
        {
            "username": username,
            "own": 1,
            "subtype": "boardgame",
            "excludesubtype": "boardgameexpansion",
        }
    )
    root = fetch_xml(f"{BGG_COLLECTION_URL}?{query}")
    return [int(item.attrib["objectid"]) for item in root.findall("item")]


def search_game_id(name: str) -> int | None:
    exact_id = search_game_id_by_mode(name, exact=True)
    if exact_id is not None:
        return exact_id
    return search_game_id_by_mode(name, exact=False)


def search_game_id_by_mode(name: str, exact: bool) -> int | None:
    query = urllib.parse.urlencode({"query": name, "type": "boardgame", "exact": int(exact)})
    root = fetch_xml(f"{BGG_SEARCH_URL}?{query}")
    items = root.findall("item")
    if not items:
        return None
    return int(items[0].attrib["id"])


def import_games(bgg_ids: list[int]) -> list[dict]:
    imported: list[dict] = []
    unique_ids = list(dict.fromkeys(bgg_ids))
    batches = chunks(unique_ids, MAX_IDS_PER_REQUEST)
    for index, batch in enumerate(batches):
        query = urllib.parse.urlencode({"id": ",".join(map(str, batch)), "stats": 1})
        root = fetch_xml(f"{BGG_THING_URL}?{query}")
        for item in root.findall("item"):
            imported.append(parse_game(item))
        if index < len(batches) - 1:
            time.sleep(5)
    return imported


def parse_game(item: ET.Element) -> dict:
    primary_name = item.find("name[@type='primary']")
    stats = item.find("statistics/ratings/averageweight")
    categories = [
        link.attrib["value"]
        for link in item.findall("link")
        if link.attrib.get("type") == "boardgamecategory"
    ]
    bgg_id = int(item.attrib["id"])
    complexity = float(stats.attrib["value"]) if stats is not None else None
    return {
        "bgg_id": bgg_id,
        "name": primary_name.attrib["value"] if primary_name is not None else f"BGG {bgg_id}",
        "min_players": attribute_int_or_none(item, "minplayers"),
        "max_players": attribute_int_or_none(item, "maxplayers"),
        "genres": categories[:5],
        "complexity": round(complexity, 2) if complexity is not None else None,
        "source_url": f"https://boardgamegeek.com/boardgame/{bgg_id}",
        "image_url": text_or_none(item.find("image")),
        "thumbnail_url": text_or_none(item.find("thumbnail")),
    }


def attribute_value(item: ET.Element, tag_name: str) -> str:
    element = item.find(tag_name)
    if element is None or "value" not in element.attrib:
        raise ValueError(f"Missing {tag_name} value for BGG item {item.attrib.get('id')}")
    return element.attrib["value"]


def attribute_int_or_none(item: ET.Element, tag_name: str) -> int | None:
    element = item.find(tag_name)
    if element is None or "value" not in element.attrib:
        return None
    return int(element.attrib["value"])


def text_or_none(element: ET.Element | None) -> str | None:
    return element.text.strip() if element is not None and element.text else None
