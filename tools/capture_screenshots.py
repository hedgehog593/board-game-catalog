"""Capture README screenshots using sample games and a disposable service."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from support import PASSWORD, Sandbox, catalog_db
from playwright.sync_api import expect, sync_playwright


def main():
    output = ROOT / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with Sandbox() as sandbox, sync_playwright() as playwright:
        catalog_db.replace_games(catalog_db.load_seed_games())
        count = len(catalog_db.query_games())
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page.goto(sandbox.url)
            expect(page.locator("#resultCount")).to_have_text(f"{count} games")
            page.screenshot(path=str(output / "finder.png"), full_page=True)

            page.goto(sandbox.url + "/randomizer.html")
            expect(page.locator("#candidateCount")).to_have_text(f"{count} games")
            combo = page.locator('[data-filter-combo="genres"]')
            combo.locator(".combo-toggle").click()
            combo.locator('.combo-option[data-value="Tile Placement"]').click()
            page.locator("h1").click()
            expect(page.locator("#candidateCount")).to_have_text("1 game")
            page.get_by_role("button", name="Pull the randomizer handle").click()
            expect(page.locator("#winnerCard")).to_be_visible(timeout=10000)
            page.screenshot(path=str(output / "randomizer.png"), full_page=True)

            page.goto(sandbox.url + "/admin.html")
            page.locator("#password").fill(PASSWORD)
            page.get_by_role("button", name="Unlock").click()
            expect(page.locator("#adminPanel")).to_be_visible()
            expect(page.locator("#resultCount")).to_have_text(f"{count} games")
            expect(page.locator("#password")).to_have_value("")
            page.screenshot(path=str(output / "admin.png"), full_page=True)
        finally:
            browser.close()
    print(f"Saved three sample-data screenshots to {output}")


if __name__ == "__main__":
    main()
