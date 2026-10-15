import http.cookiejar
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from support import Sandbox, PASSWORD, Response, XML, api, bgg_client


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox().__enter__()
        self.addCleanup(self.sandbox.__exit__, None, None, None)
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, data=None, method=None, content_type="application/json"):
        request = urllib.request.Request(self.sandbox.url + path, data=data, method=method,
                                         headers={"Content-Type": content_type})
        try:
            response = self.client.open(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def login(self):
        self.assertEqual(self.request("/api/admin/login", json.dumps({"password": PASSWORD}).encode())[0], 200)

    def test_filter_contract_and_invalid_input(self):
        self.assertTrue(self.request("/api/health")[1]["ok"])
        self.assertEqual(self.request("/api/games?players=4&genre=Economic&maxComplexity=3")[1]["count"], 1)
        self.assertEqual(self.request("/api/games?players=20")[1]["count"], 0)
        self.assertEqual(self.request("/api/games?players=bad")[0], 400)
        self.assertIn("Puzzle", self.request("/api/genres")[1]["genres"])

    def test_authentication_and_logout(self):
        for path in ("/api/import/csv", "/api/bgg/refresh"):
            self.assertEqual(self.request(path, b"", "POST")[0], 401)
        self.assertEqual(self.request("/api/admin/login", b'{"password":"wrong"}')[0], 401)
        self.login()
        self.assertTrue(self.request("/api/admin/status", b"", "POST")[1]["authenticated"])
        self.request("/api/admin/logout", b"", "POST")
        self.assertFalse(self.request("/api/admin/status", b"", "POST")[1]["authenticated"])

    def test_reimport_preserves_metadata_duplicates_and_removes_absent_games(self):
        self.login()
        csv = b"name,bgg_id\nCATAN,13\nCATAN,13\n"
        for _ in range(2):
            status, result = self.request("/api/import/csv", csv, content_type="text/csv")
            self.assertEqual(status, 200)
            self.assertEqual(result["imported"], 2)
        self.assertEqual(self.request("/api/games")[1]["count"], 2)
        game = self.request("/api/games")[1]["games"][0]
        self.assertEqual((game["minPlayers"], game["maxPlayers"], game["complexity"]), (3, 4, 2.3))
        self.assertEqual(game["genres"], ["Economic"])

    def test_invalid_import_does_not_replace_catalog(self):
        self.login()
        self.assertEqual(self.request("/api/import/csv", b"name,bgg_id\nOops,invalid", content_type="text/csv")[0], 400)
        self.assertEqual(self.request("/api/games")[1]["count"], 3)

    def test_bgg_refresh_updates_db_and_preserves_missing_results(self):
        self.login()
        with patch.object(bgg_client.urllib.request, "urlopen", return_value=Response()) as fetch:
            status, result = self.request("/api/bgg/refresh", b"", "POST")
        self.assertEqual(status, 200)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["skippedMissingIds"], 1)
        self.assertIn("Pandemic", result["unmatched"])
        self.assertIn("stats=1", fetch.call_args.args[0].full_url)
        self.assertEqual(fetch.call_args.args[0].get_header("Authorization"), "Bearer test-token")
        games = self.request("/api/games")[1]["games"]
        self.assertEqual(len(games), 3)
        self.assertEqual(games[0]["complexity"], 2.31)

    def test_bgg_failure_keeps_catalog(self):
        self.login()
        with patch.object(bgg_client.urllib.request, "urlopen", side_effect=urllib.error.HTTPError("https://example.com", 401, "Unauthorized", {}, None)):
            self.assertEqual(self.request("/api/bgg/refresh", b"", "POST")[0], 502)
        self.assertEqual(self.request("/api/games")[1]["count"], 3)


class BggClientTests(unittest.TestCase):
    def test_pending_and_rate_limit_retry(self):
        rate_limit = urllib.error.HTTPError("https://example.com", 429, "Rate limited", {}, None)
        with patch.object(bgg_client.urllib.request, "urlopen", side_effect=[Response(status=202), rate_limit, Response()]), patch.object(bgg_client.time, "sleep") as sleep:
            self.assertEqual(bgg_client.fetch_xml("https://example.com").find("item").get("id"), "13")
            self.assertEqual(sleep.call_count, 2)

    def test_retry_exhaustion(self):
        with patch.object(bgg_client.urllib.request, "urlopen", return_value=Response(status=202)), patch.object(bgg_client.time, "sleep"):
            with self.assertRaises(RuntimeError):
                bgg_client.fetch_xml("https://example.com", retries=2)

    def test_batching_deduplicates_ids(self):
        with patch.object(bgg_client.urllib.request, "urlopen", return_value=Response()) as fetch, patch.object(bgg_client.time, "sleep"):
            bgg_client.import_games(list(range(1, 22)) + [1])
            self.assertEqual(fetch.call_count, 2)

    def test_search_exact_then_fallback(self):
        with patch.object(bgg_client.urllib.request, "urlopen", side_effect=[Response(b"<items/>"), Response(b'<items><item id="13"/></items>')]) as fetch:
            self.assertEqual(bgg_client.search_game_id("CATAN"), 13)
            self.assertIn("exact=0", fetch.call_args.args[0].full_url)
