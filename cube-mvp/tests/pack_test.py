#!/usr/bin/env python3
"""
Play every recipe in cube-mvp/recipes/pack.json in a headless browser.

For each recipe: pick it from the catalog, craft every sub-assembly by
dragging parts onto the 2D bench, check all requirements turn green, open
Build, and check the assembly guide shows the recipe's steps.

Usage:
    python3 cube-mvp/tests/pack_test.py              # all recipes
    python3 cube-mvp/tests/pack_test.py jar_lantern  # one or more recipe ids

Needs: pip install playwright && python3 -m playwright install chromium
Exit code 0 = every recipe built, 1 = at least one failure.
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("CUBE_TEST_PORT", "8743"))
BASE = f"http://localhost:{PORT}"


def craft_counts(recipe):
    """How many times each merge must run to cover the final requirements."""
    makes = {r["result_id"]: r for r in recipe["recipes"]}
    count = Counter()

    def need(item, q):
        if item in makes:
            count[item] += q
            need(makes[item]["a"], q)
            need(makes[item]["b"], q)

    for f in recipe["final_requires"]:
        need(f["id"], f["qty"])
    return [(r, count[r["result_id"]]) for r in recipe["recipes"]]


def wait_for_port(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("localhost", PORT)) == 0:
                return True
        time.sleep(0.2)
    return False


def main():
    from playwright.sync_api import sync_playwright

    pack = json.loads((APP_DIR / "recipes" / "pack.json").read_text())["recipes"]
    only = set(sys.argv[1:])
    if only:
        pack = [r for r in pack if r["id"] in only]

    server = subprocess.Popen([sys.executable, "server.py"], cwd=APP_DIR,
                              env={**os.environ, "PORT": str(PORT), "ANTHROPIC_API_KEY": ""},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    failures = []
    try:
        if not wait_for_port():
            print("[FAIL] server did not start")
            return 1
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE)
            page.evaluate("localStorage.clear()")
            page.reload()
            page.wait_for_selector("#catalogList .idea-row")
            if page.locator("#introModal.visible").count():
                page.click("#introStartBtn")  # dismiss the how-it-works screen

            shown = page.locator("#catalogList .idea-row").count()
            if shown < len(pack) + 1 and not only:
                failures.append(f"catalog shows {shown} rows, expected at least {len(pack) + 1}")

            bench = page.locator("#bench").bounding_box()
            target = (bench["x"] + bench["width"] / 2, bench["y"] + bench["height"] / 2)

            def drag(item_id):
                chip = page.locator(f'#paletteList .chip[data-id="{item_id}"]:not(.disabled)')
                if chip.count() == 0:
                    return False
                chip.first.scroll_into_view_if_needed()
                box = chip.first.bounding_box()
                page.mouse.move(box["x"] + 20, box["y"] + box["height"] / 2)
                page.mouse.down()
                page.mouse.move(target[0], target[1], steps=4)
                page.mouse.up()
                return True

            def palette_qty(item_id):
                chip = page.locator(f'#paletteList .chip[data-id="{item_id}"] .chip-qty')
                return int(chip.first.inner_text()) if chip.count() else 0

            raw_ids_by_recipe = {r["id"]: {m["id"] for m in r["rawMaterials"]} for r in pack}
            for recipe in pack:
                rid = recipe["id"]
                raw_ids = raw_ids_by_recipe[rid]
                ns = lambda x: x if x in raw_ids else f"{rid}__{x}"
                page.fill("#catalogSearch", recipe["title"])
                row = page.locator("#catalogList .idea-row").filter(
                    has=page.locator(".idea-row-title", has_text=re.compile("^" + re.escape(recipe["title"]) + "$")))
                if row.count() != 1:
                    failures.append(f"{rid}: found {row.count()} catalog rows for '{recipe['title']}'")
                    continue
                row.first.click()
                page.fill("#catalogSearch", "")

                ok = True
                for r, times in craft_counts(recipe):
                    result = ns(r["result_id"])
                    for _ in range(times):
                        before = palette_qty(result)
                        if not (drag(ns(r["a"])) and drag(ns(r["b"]))):
                            failures.append(f"{rid}: no '{r['a']}' or '{r['b']}' left to make {r['result_name']}")
                            ok = False
                            break
                        page.wait_for_timeout(60)
                        if palette_qty(result) != before + 1:
                            failures.append(f"{rid}: {r['a']} + {r['b']} did not merge into {r['result_name']}")
                            ok = False
                            break
                    if not ok:
                        page.click("#clearBenchBtn")
                        break
                if not ok:
                    continue

                red = page.locator("#reqList .req-item.red").all_inner_texts()
                if red:
                    failures.append(f"{rid}: requirements still red: {'; '.join(red)}")
                    continue
                if not page.locator("#buildBtn").is_enabled():
                    failures.append(f"{rid}: Build button stayed disabled")
                    continue
                page.click("#buildBtn")
                page.wait_for_selector("#assemblyModal.visible")
                n = page.locator("#stepsList input[type=checkbox]").count()
                if n != len(recipe["assembly_steps"]):
                    failures.append(f"{rid}: guide shows {n} steps, expected {len(recipe['assembly_steps'])}")
                page.click("#closeModalBtn")
                print(f"[PASS] {rid}")

            if errors:
                failures.append("console errors: " + " | ".join(errors[:5]))
            browser.close()
    finally:
        server.terminate()

    for f in failures:
        print(f"[FAIL] {f}")
    print(f"{len(pack) - len([f for f in failures if not f.startswith(('console', 'catalog'))])} of {len(pack)} recipes built")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
