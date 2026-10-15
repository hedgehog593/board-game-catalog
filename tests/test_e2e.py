from pathlib import Path
import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
from support import Sandbox, PASSWORD, Response, bgg_client


class JourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.sandbox = Sandbox().__enter__()
        self.addCleanup(self.sandbox.__exit__, None, None, None)
        self.context = self.browser.new_context(viewport={"width": 1321, "height": 900})
        self.context.tracing.start(screenshots=True, snapshots=True)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("console", lambda message: self.errors.append(message.text) if message.type == "error" else None)

    def tearDown(self):
        folder = Path("test-results") / self._testMethodName
        folder.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(folder / "screen.png"), full_page=True)
        self.context.tracing.stop(path=str(folder / "trace.zip"))
        self.context.close()
        self.assertEqual(self.errors, [])

    def select(self, name, text, value):
        combo = self.page.locator(f'[data-filter-combo="{name}"]')
        combo.locator(".combo-toggle").click()
        combo.locator(".combo-search").fill(text)
        combo.locator(f'.combo-option[data-value="{value}"]').click()

    def test_finder_search_filter_clear_and_reset(self):
        self.page.goto(self.sandbox.url)
        expect(self.page.locator("#resultCount")).to_have_text("3 games")
        self.select("players", "4 players", "4")
        self.select("genre", "Econ", "Economic")
        self.select("maxComplexity", "Medium", "3")
        expect(self.page.locator("#resultCount")).to_have_text("1 game")
        expect(self.page.locator("#games .name")).to_have_text("CATAN")
        self.page.get_by_role("button", name="Find games", exact=True).click()
        combo = self.page.locator('[data-filter-combo="genre"]')
        combo.locator(".combo-toggle").click()
        self.page.locator("h1").click()
        expect(combo.locator(".combo-panel")).to_be_hidden()
        expect(combo.locator(".combo-toggle")).to_have_text("Economic")
        combo.locator(".combo-toggle").click()
        combo.get_by_role("button", name="Clear all").click()
        self.page.get_by_role("button", name="Reset", exact=True).click()
        expect(self.page.locator("#resultCount")).to_have_text("3 games")

    def test_randomizer_filtered_handle_and_empty_result(self):
        self.page.goto(self.sandbox.url)
        self.page.get_by_role("link", name="Randomizer", exact=True).click()
        expect(self.page.locator("#candidateCount")).to_have_text("3 games")
        self.select("playerLimit", "4 players", "4")
        self.select("complexityRange", "Medium", "2-3")
        self.select("genres", "Econ", "Economic")
        self.page.locator("h1").click()
        expect(self.page.locator("#candidateCount")).to_have_text("1 game")
        self.page.get_by_role("button", name="Pull the randomizer handle").click()
        expect(self.page.locator("#randomize")).to_be_disabled()
        expect(self.page.locator("#winnerName")).to_have_text("CATAN", timeout=10000)
        expect(self.page.locator("#winnerSource")).to_have_attribute("href", "https://boardgamegeek.com/boardgame/13")
        self.page.get_by_role("button", name="Reset", exact=True).click()
        expect(self.page.locator("#winnerCard")).to_be_hidden()
        self.select("playerLimit", "1 player", "1")
        self.select("complexityRange", "Very heavy", "4-5")
        self.page.get_by_role("button", name="Randomize", exact=True).click()
        expect(self.page.locator("#randomizerStatus")).to_contain_text("Adjust the filters")

    def test_admin_import_refresh_reimport_and_logout(self):
        self.page.goto(self.sandbox.url + "/admin.html")
        expect(self.page.locator("#adminPanel")).to_be_hidden()
        self.page.locator("#password").fill("wrong")
        self.page.get_by_role("button", name="Unlock").click()
        expect(self.page.locator("#loginStatus")).to_have_text("Invalid password.")
        self.assertEqual(len(self.errors), 1)
        self.assertIn("401 (Unauthorized)", self.errors[0])
        self.errors.clear()
        self.page.locator("#password").fill(PASSWORD)
        self.page.get_by_role("button", name="Unlock").click()
        expect(self.page.locator("#adminPanel")).to_be_visible()
        for refresh in (True, False):
            self.page.locator("#csvFile").set_input_files({"name": "owned.csv", "mimeType": "text/csv", "buffer": b"name,bgg_id\nCATAN,13\n"})
            self.page.get_by_role("button", name="Import CSV").click()
            expect(self.page.locator("#importStatus")).to_contain_text("Synced 1 owned games")
            if refresh:
                with patch.object(bgg_client.urllib.request, "urlopen", return_value=Response()):
                    self.page.get_by_role("button", name="Refresh BGG Data").click()
                    expect(self.page.locator("#refreshStatus")).to_contain_text("Updated 1 games")
            expect(self.page.locator("#games")).to_contain_text("2.31")
        self.page.get_by_role("button", name="Log out").click()
        expect(self.page.locator("#adminPanel")).to_be_hidden()

    def test_dropdown_layout_desktop_and_mobile(self):
        for width in (1321, 390):
            self.page.set_viewport_size({"width": width, "height": 900})
            for path in ("/index.html", "/randomizer.html"):
                self.page.goto(self.sandbox.url + path)
                expect(self.page.locator(".combo-options").first.locator("button").first).to_be_attached()
                for combo in self.page.locator(".filter-combo").all():
                    combo.locator(".combo-toggle").click()
                    panel = combo.locator(".combo-panel")
                    expect(panel).to_be_visible()
                    self.assertTrue(panel.evaluate("el => { const r = el.getBoundingClientRect(); const x = r.left + r.width / 2; const y = Math.max(0, r.top) + 12; return r.left >= 0 && r.right <= innerWidth && el.contains(document.elementFromPoint(x, y)); }"))
                    self.page.locator("h1").click()
                    expect(panel).to_be_hidden()
