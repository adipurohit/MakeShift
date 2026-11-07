#!/usr/bin/env python3
"""
AI ideas flow in a real browser, with /api/generate-ideas stubbed (no key needed).

Checks that ideas:
- are requested only with the parts in the user's inventory (no catalog parts at 0 qty),
- refresh on their own a moment after the inventory changes, once per pause,
- list 10+ options with Ready or Need N more badges, ready ones first,
- come with a merge guide that walks the build and ticks off as you merge,
- keep the idea being built when a refresh drops it, and don't refresh during merges.

Usage: python3 app/tests/ai_flow_test.py
Exit code 0 = all checks passed, 1 = at least one failure.
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
PORT = 8743
results = []
calls = []


def check(ok, name, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def ideas_for(ids, include_frame=True):
    b, r, d = "m_cardboard_box", "m_rubber_bands", "m_wooden_dowel"
    out = []
    if include_frame:
        out.append({"id": "frame_kit", "title": "Frame Kit", "pitch": "A sturdy frame.", "uses_material_ids": [b, d, r],
                    "recipes": [{"a": b, "b": d, "result_id": "panel", "result_name": "Panel", "result_short": "PA"},
                                {"a": "panel", "b": r, "result_id": "frame", "result_name": "Frame", "result_short": "FR"}],
                    "final_requires": [{"id": "frame", "qty": 1}]})
    out.append({"id": "big_rack", "title": "Big Rack", "pitch": "Needs more parts.", "uses_material_ids": [b, d],
                "recipes": [{"a": b, "b": d, "result_id": "rack", "result_name": "Rack Unit", "result_short": "RU"}],
                "final_requires": [{"id": "rack", "qty": 5}]})
    for n in range(3, 12):
        out.append({"id": f"idea_{n}", "title": f"Idea {n}", "pitch": "Filler.", "uses_material_ids": [b, r],
                    "recipes": [{"a": b, "b": r, "result_id": f"thing{n}", "result_name": f"Thing {n}", "result_short": "TH"}],
                    "final_requires": [{"id": f"thing{n}", "qty": 1}]})
    return out


def main():
    from playwright.sync_api import sync_playwright

    server = subprocess.Popen([sys.executable, "server.py"], cwd=APP_DIR,
                              env={"PATH": "/usr/bin:/bin", "GEMINI_API_KEY": "stub"},
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

            def handle(route):
                body = json.loads(route.request.post_data)
                calls.append(body["materials"])
                ideas = ideas_for([m["id"] for m in body["materials"]], include_frame=len(calls) == 1)
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"ideas": ideas}))
            page.route("**/api/generate-ideas", handle)

            page.goto(f"http://localhost:{PORT}/")
            page.evaluate("localStorage.clear(); localStorage.setItem('makeshift_intro_seen', '1')")
            page.reload()
            page.wait_for_selector("#catalogList .idea-row")
            # open a catalog recipe first, so its parts get registered like they do for real users
            page.locator("#catalogList .idea-row", has_text="Robot Arm").first.click()

            for name, qty in (("cardboard box", 3), ("rubber bands", 10), ("wooden dowel", 2)):
                page.fill("#materialNameInput", name)
                page.fill("#materialQtyInput", str(qty))
                page.press("#materialNameInput", "Enter")
                page.wait_for_timeout(200)
            page.wait_for_timeout(3800)

            check(len(calls) == 1, "three quick edits trigger one automatic refresh", f"{len(calls)} call(s)")
            sent = {m["id"]: m["qty"] for m in calls[0]} if calls else {}
            check(sent == {"m_cardboard_box": 3, "m_rubber_bands": 10, "m_wooden_dowel": 2},
                  "only the user's own parts are sent to the AI", json.dumps(sent))

            rows = page.locator("#buildableNowList .idea-row")
            check(rows.count() == 11, "AI Ideas lists all 11 ideas", rows.count())
            check("10 of 11 ready" in page.inner_text("#ideasCount"), "count shows how many are ready", page.inner_text("#ideasCount"))
            last = rows.nth(rows.count() - 1).inner_text()
            check("Big Rack" in last and "Need 5 more" in last, "an idea short of parts sorts last with Need N more", last.replace("\n", " "))
            check(page.locator("#buildableNowList .idea-row", has_text="Robot Arm").count() == 0, "catalog recipes stay out of AI Ideas")

            page.locator("#buildableNowList .idea-row", has_text="Frame Kit").click()
            steps = page.locator("#mergeGuide .merge-step")
            check(steps.count() == 2, "merge guide lists both merges for Frame Kit", steps.count())
            check("cardboard box + wooden dowel → Panel" in steps.nth(0).inner_text().replace("\n", " "),
                  "guide names the parts to merge", steps.nth(0).inner_text().replace("\n", " "))

            bench = page.locator("#bench").bounding_box()
            spot = (bench["x"] + bench["width"] / 2, bench["y"] + bench["height"] / 2)

            def drag(item_id):
                chip = page.locator(f'#paletteList .chip[data-id="{item_id}"]:not(.disabled)').first
                box = chip.bounding_box()
                page.mouse.move(box["x"] + 20, box["y"] + box["height"] / 2)
                page.mouse.down()
                page.mouse.move(*spot, steps=4)
                page.mouse.up()
                page.wait_for_timeout(100)

            drag("m_cardboard_box"); drag("m_wooden_dowel")
            check("done" in (steps.nth(0).get_attribute("class") or ""), "step 1 ticks off after merging Panel")
            drag("m_rubber_bands"); drag("frame_kit__panel")
            check(page.locator("#mergeGuide .merge-step.done").count() == 2, "both steps done after the second merge")
            check(page.locator("#buildBtn").is_enabled(), "Build is enabled after following the guide")
            page.wait_for_timeout(3600)
            check(len(calls) == 1, "merging parts does not trigger a refresh", f"{len(calls)} call(s)")

            page.locator(".qty-btn[data-op='inc'][data-id='m_wooden_dowel']").click()
            page.wait_for_timeout(3800)
            check(len(calls) == 2, "changing a quantity refreshes the ideas", f"{len(calls)} call(s)")
            check(page.locator("#buildableNowList .idea-row", has_text="Frame Kit").count() == 1,
                  "the idea being built stays after a refresh drops it")
            check("Building: Frame Kit" in page.inner_text("#activeRecipeLabel"), "the build in progress stays selected")
            check(not errors, "no page errors", "; ".join(errors))
            browser.close()
    finally:
        server.terminate()
    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
