#!/usr/bin/env python3
"""
Instructions panel in a real browser, with the AI endpoints stubbed (no key needed).

Checks that:
- picking a built-in recipe shows its steps at once, with no AI call,
- Hide / Instructions toggles the list,
- picking an AI idea makes no AI call; the Instructions button asks once, shows a wait message,
  then shows and saves the steps,
- Build It reuses the saved steps instead of asking again,
- a failed request shows the error and a Try again button, and nothing is saved.

Usage: python3 app/tests/instructions_test.py
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


def check(ok, name, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


B, R, D = "m_cardboard_box", "m_rubber_bands", "m_wooden_dowel"
IDEAS = [
    {"id": "frame_kit", "title": "Frame Kit", "pitch": "A sturdy frame.", "uses_material_ids": [B, D, R],
     "recipes": [{"a": B, "b": D, "result_id": "panel", "result_name": "Panel", "result_short": "PA"},
                 {"a": "panel", "b": R, "result_id": "frame", "result_name": "Frame", "result_short": "FR"}],
     "final_requires": [{"id": "frame", "qty": 1}]},
    {"id": "band_rack", "title": "Band Rack", "pitch": "Holds bands.", "uses_material_ids": [B, R],
     "recipes": [{"a": B, "b": R, "result_id": "rack", "result_name": "Rack", "result_short": "RK"}],
     "final_requires": [{"id": "rack", "qty": 1}]},
]
STEPS = ["Cut the box into a flat panel.", "Tape the dowel along one edge.", "Wrap rubber bands around the frame."]


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
            step_calls = []
            mode = {"fail": False, "hold": False}
            held = []

            page.route("**/api/generate-ideas", lambda r: r.fulfill(
                status=200, content_type="application/json", body=json.dumps({"ideas": IDEAS})))

            def steps(route):
                step_calls.append(json.loads(route.request.post_data)["idea"]["title"])
                if mode["hold"]:
                    held.append(route)  # answered later, so the page shows its waiting state
                    return
                answer(route)

            def answer(route):
                if mode["fail"]:
                    route.fulfill(status=503, content_type="application/json",
                                  body=json.dumps({"error": "ai_busy", "message": "The AI service is overloaded right now."}))
                else:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"assembly_steps": STEPS}))
            page.route("**/api/generate-steps", steps)

            page.goto(f"http://localhost:{PORT}/")
            page.evaluate("localStorage.clear(); localStorage.setItem('makeshift_intro_seen', '1')")
            page.reload()
            page.wait_for_selector("#catalogList .idea-row")

            # Built-in recipe: steps at once, no AI.
            page.locator("#catalogList .idea-row", has_text="Robot Arm").first.click()
            items = page.locator("#instructionsList li")
            check(page.is_visible("#instructionsList") and items.count() == 9,
                  "Robot Arm shows its 9 built-in steps on selection", items.count())
            check(page.inner_text("#instructionsBtn") == "Hide", "button offers to hide the steps")
            page.click("#instructionsBtn")
            check(page.is_hidden("#instructionsList") and "Built in" in page.inner_text("#instructionsHint"),
                  "Hide collapses the list and notes no AI is needed", page.inner_text("#instructionsHint"))
            page.click("#instructionsBtn")
            check(page.is_visible("#instructionsList"), "Instructions opens the list again")

            pack = page.locator("#catalogList .idea-row").nth(3)
            pack.click()
            check(page.locator("#instructionsList li").count() >= 3, "a pack recipe shows its steps on selection",
                  page.locator("#instructionsList li").count())

            # AI idea: no call on selection.
            for name, qty in (("cardboard box", 3), ("rubber bands", 10), ("wooden dowel", 2)):
                page.fill("#materialNameInput", name)
                page.fill("#materialQtyInput", str(qty))
                page.press("#materialNameInput", "Enter")
                page.wait_for_timeout(150)
            page.wait_for_selector("#buildableNowList .idea-row", timeout=8000)
            page.locator("#buildableNowList .idea-row", has_text="Frame Kit").click()
            page.wait_for_timeout(500)
            check(step_calls == [], "selecting an AI idea makes no AI call")
            check(page.is_hidden("#instructionsList") and page.inner_text("#instructionsBtn") == "Instructions",
                  "AI idea shows an Instructions button instead of steps")

            mode["hold"] = True
            page.click("#instructionsBtn")
            page.wait_for_timeout(300)
            check(page.is_disabled("#instructionsBtn") and "20 seconds" in page.inner_text("#instructionsHint"),
                  "while waiting the button is disabled and the wait is explained", page.inner_text("#instructionsHint"))
            mode["hold"] = False
            for route in held:
                answer(route)
            page.wait_for_selector("#instructionsList li", timeout=5000)
            check([t.strip() for t in page.locator("#instructionsList li").all_inner_texts()] == STEPS,
                  "AI steps appear in the panel")
            check(step_calls == ["Frame Kit"], "one AI call for the steps", step_calls)

            # Saved: switching away and back, then Build It, makes no new call.
            page.locator("#catalogList .idea-row", has_text="Robot Arm").first.click()
            page.locator("#buildableNowList .idea-row", has_text="Frame Kit").click()
            check(page.locator("#instructionsList li").count() == 3, "steps are still there after switching back")

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
            drag(B); drag(D); drag(R); drag("frame_kit__panel")
            page.click("#buildBtn")
            page.wait_for_selector("#assemblyModal.visible")
            page.wait_for_selector("#stepsList .step-item")
            check(page.locator("#stepsList .step-item").count() == 3 and step_calls == ["Frame Kit"],
                  "Build It reuses the saved steps with no new call", step_calls)
            page.click("#closeModalBtn")

            # Failure: error shown, Try again offered, nothing saved.
            mode["fail"] = True
            page.locator("#buildableNowList .idea-row", has_text="Band Rack").click()
            page.click("#instructionsBtn")
            page.wait_for_selector("#instructionsHint.error", timeout=5000)
            check(page.inner_text("#instructionsBtn") == "Try again" and "overloaded" in page.inner_text("#instructionsHint"),
                  "a failed request shows the error and Try again", page.inner_text("#instructionsHint"))
            saved = page.evaluate("JSON.parse(localStorage.getItem('makeshift_state_v5')).assemblySteps")
            check("band_rack" not in saved, "a failed request saves nothing")
            mode["fail"] = False
            page.click("#instructionsBtn")
            page.wait_for_selector("#instructionsList li", timeout=5000)
            check(page.locator("#instructionsList li").count() == 3, "Try again gets the steps")

            check(not errors, "no page errors", "; ".join(errors)[:200])
            browser.close()
    finally:
        server.terminate()
    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
