#!/usr/bin/env python3
"""
Parts on the bench still count toward the build checklist.

Reproduces the "bare ingredient" case: in Jar Lantern, String goes into the
build as-is. A player who drops String and the Glow Jar on the bench to try
combining them should still see both requirements green, get a hint that
String goes in as-is, and be able to press Build, which uses up the bench parts.

Usage: python3 cube-mvp/tests/bench_count_test.py
Exit code 0 = all checks passed, 1 = at least one failure.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("CUBE_TEST_PORT", "8743"))
BASE = f"http://localhost:{PORT}"
results = []


def check(ok, name, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def main():
    from playwright.sync_api import sync_playwright

    server = subprocess.Popen([sys.executable, "server.py"], cwd=APP_DIR,
                              env={**os.environ, "PORT": str(PORT), "GEMINI_API_KEY": ""},
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
            page.goto(BASE)
            page.evaluate("localStorage.clear(); localStorage.setItem('makeshift_intro_seen', '1')")
            page.reload()
            page.wait_for_selector("#catalogList .idea-row")

            bench = page.locator("#bench").bounding_box()
            spot = lambda dx: (bench["x"] + bench["width"] / 2 + dx, bench["y"] + bench["height"] / 2)

            def drag(item_id, to):
                chip = page.locator(f'#paletteList .chip[data-id="{item_id}"]:not(.disabled)').first
                box = chip.bounding_box()
                page.mouse.move(box["x"] + 20, box["y"] + box["height"] / 2)
                page.mouse.down()
                page.mouse.move(to[0], to[1], steps=4)
                page.mouse.up()
                page.wait_for_timeout(80)

            def req(name):
                row = page.locator("#reqList .req-item", has_text=name).first
                return row.get_attribute("class"), row.locator(".req-count").inner_text()

            page.fill("#catalogSearch", "Jar Lantern")
            page.locator("#catalogList .idea-row", has_text="Jar Lantern").first.click()

            # craft LED Pod, then Glow Jar
            drag("led", spot(0)); drag("coin", spot(0))
            drag("jar", spot(0)); drag("jar_lantern__ledpod", spot(0))
            cls, count = req("Glow Jar")
            check("green" in cls, "Glow Jar crafted and counted", count)

            check(page.locator("#reqList .req-item", has_text="String").locator(".req-asis").count() == 1,
                  "String is tagged as-is in the checklist")

            # the bare-ingredient case: put String and Glow Jar on the bench together
            drag("string", spot(120))
            drag("jar_lantern__glowjar", spot(120))
            toast = page.locator("#toast").inner_text()
            check("as-is" in toast, "failed merge explains String goes in as-is", toast)
            check(page.locator(".bench-token").count() == 2, "both parts stay on the bench")
            for name in ("String", "Glow Jar"):
                cls, count = req(name)
                check("green" in cls and count.startswith("1"), f"{name} on the bench still counts", count)
            check(page.locator("#buildBtn").is_enabled(), "Build is enabled with parts on the bench")

            page.click("#buildBtn")
            page.wait_for_selector("#assemblyModal.visible")
            check(page.locator(".bench-token").count() == 0, "Build uses up the parts on the bench")
            page.click("#closeModalBtn")

            # Robot Arm: a raw final part dropped alone still counts
            page.fill("#catalogSearch", "")
            page.locator("#catalogList .idea-row", has_text="Robot Arm").first.click()
            drag("board", spot(0))
            cls, count = req("Control Board")
            check("green" in cls, "Robot Arm Control Board on the bench still counts", count)

            check(not errors, "no page errors", "; ".join(errors))
            browser.close()
    finally:
        server.terminate()
    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
