#!/usr/bin/env python3
"""
With no AI at all, the 101 built-in recipes rank by how many of their parts the user has.

Runs the local server with no API key, adds a few everyday parts (plural, lowercase, as people
type them), and checks the matching recipe rises to the top of Catalog matches and the catalog,
with a parts badge, while the AI panel reports it is off.

Usage: python3 cube-mvp/tests/catalog_match_test.py
Exit code 0 = all checks passed, 1 = at least one failure.
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
PORT = 8743
results = []


def check(ok, name, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def main():
    from playwright.sync_api import sync_playwright

    server = subprocess.Popen([sys.executable, "server.py"], cwd=APP_DIR,
                              env={"PATH": "/usr/bin:/bin", "GEMINI_API_KEY": ""},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            with socket.socket() as s:
                if s.connect_ex(("localhost", PORT)) == 0:
                    break
            time.sleep(0.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://localhost:{PORT}/")
            page.evaluate("localStorage.clear(); localStorage.setItem('makeshift_intro_seen', '1')")
            page.reload()
            page.wait_for_selector("#catalogList .idea-row")
            check(page.locator("#catalogMatches").is_hidden(), "no matches panel before any parts are added")

            for name, qty in (("balloons", 2), ("drinking straws", 5), ("wooden dowel", 2), ("bottle caps", 6), ("plastic bottle", 1)):
                page.fill("#materialNameInput", name)
                page.fill("#materialQtyInput", str(qty))
                page.press("#materialNameInput", "Enter")
                page.wait_for_timeout(120)
            page.wait_for_timeout(3700)  # let the automatic AI refresh run and fail (no key)

            check(page.locator("#generateError").is_visible(), "AI panel says the AI is off", page.inner_text("#generateError")[:80])
            matches = page.locator("#catalogMatchList .idea-row")
            check(matches.count() >= 3, "Catalog matches lists built-in recipes for these parts", matches.count())
            top = matches.first.inner_text().replace("\n", " ")
            check("Balloon Rocket Car" in top and "5/5 parts" in top, "the recipe that uses all five parts ranks first", top)
            first_row = page.locator("#catalogList .idea-row").first.inner_text().replace("\n", " ")
            check("Balloon Rocket Car" in first_row, "the full catalog also sorts by parts you have", first_row[:60])
            badge = page.locator("#catalogList .idea-row", has_text="Bottle Bowling").locator(".idea-badge")
            check(badge.count() == 1 and badge.inner_text() == "1/3 parts", "other recipes show how many of their parts you have",
                  badge.inner_text() if badge.count() else "-")

            matches.first.click()
            check("Building: Balloon Rocket Car" in page.inner_text("#activeRecipeLabel"), "a match opens straight into its build")
            check(not errors, "no page errors", "; ".join(errors))
            browser.close()
    finally:
        server.terminate()
    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
