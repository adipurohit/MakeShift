#!/usr/bin/env python3
"""
MakeShift smoke test.

Starts server.py, checks the HTTP endpoints, then drives the page in a
headless browser through the offline Robot Arm demo path (no API key needed):
select recipe, craft every sub-assembly in the 2D bench, Build, check off
steps, upload a photo, mark complete. Fails on any page console error.

Usage (from the repo root or cube-mvp/):
    python3 cube-mvp/tests/smoke.py            # offline mode, key forced off
    python3 cube-mvp/tests/smoke.py --with-ai  # also call /api/generate-ideas with your real key
    python3 cube-mvp/tests/smoke.py --headed   # watch the browser
    python3 cube-mvp/tests/smoke.py --base-url https://example.onrender.com  # test a deployment

Needs: pip install playwright && python3 -m playwright install chromium
(If Playwright is missing, the HTTP checks still run and browser checks are skipped.)

Exit code 0 = all checks passed, 1 = at least one failure.
"""
import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("CUBE_TEST_PORT", "8743"))
BASE = f"http://localhost:{PORT}"

# Offline Robot Arm recipe graph, in crafting order: (a, b) -> result name.
# Mirrors OFFLINE_IDEA in app.js. If that changes, update this list.
CRAFT_PLAN = [
    ("Stepper Motor", "Pulley", "Drive Unit"),
    ("Drive Unit", "Timing Belt", "Motorized Joint"),
    ("Stepper Motor", "Pulley", "Drive Unit"),
    ("Drive Unit", "Timing Belt", "Motorized Joint"),
    ("Al. Extrusion", "Smooth Rod", "Rail"),
    ("Rail", "Linear Bearing", "Arm Segment"),
    ("Al. Extrusion", "Smooth Rod", "Rail"),
    ("Rail", "Linear Bearing", "Arm Segment"),
    ("Dead Nozzle", "Zip Tie", "Gripper Claw"),
]

# 1x1 PNG for the progress-photo upload step.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

results = []  # (status, name, detail)


def record(ok, name, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((status, name, detail))
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return ok


def warn(name, detail=""):
    results.append(("WARN", name, detail))
    print(f"[WARN] {name}" + (f"  ({detail})" if detail else ""), flush=True)


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def http(method, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def start_server(with_ai):
    if port_in_use(PORT):
        print(f"Port {PORT} is already in use. Stop the other MakeShift server first.", file=sys.stderr)
        sys.exit(1)
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    if not with_ai:
        # An empty value wins over cube-mvp/.env (load_dotenv skips keys already set),
        # so the server runs in no-key mode without touching your .env.
        env["GROQ_API_KEY"] = ""
    proc = subprocess.Popen(
        [sys.executable, str(APP_DIR / "server.py")],
        cwd=str(APP_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for _ in range(50):
        if proc.poll() is not None:
            print(proc.stdout.read(), file=sys.stderr)
            print("server.py exited during startup", file=sys.stderr)
            sys.exit(1)
        if port_in_use(PORT):
            return proc
        time.sleep(0.2)
    proc.kill()
    print("server.py did not start listening within 10s", file=sys.stderr)
    sys.exit(1)


def http_checks(with_ai):
    for path in ["/", "/app.js", "/style.css", "/vendor/three.module.js", "/vendor/OrbitControls.js"]:
        status, _ = http("GET", path)
        record(status == 200, f"GET {path} returns 200", f"got {status}")

    status, _ = http("POST", "/api/does-not-exist", body={})
    record(status == 404, "Unknown API route returns 404", f"got {status}")

    status, _ = http("POST", "/api/generate-ideas", raw=b"{not json")
    record(status == 400, "Malformed JSON returns 400", f"got {status}")

    materials = [
        {"id": "m_cardboard", "name": "Cardboard", "qty": 5},
        {"id": "m_binder_clips", "name": "Binder Clips", "qty": 3},
        {"id": "m_wood_dowel", "name": "Wood Dowel", "qty": 2},
    ]
    if not with_ai:
        status, body = http("POST", "/api/generate-ideas", body={"materials": materials})
        err = json.loads(body or b"{}").get("error")
        record(status == 503 and err == "no_api_key", "No-key mode: generate-ideas returns 503 no_api_key",
               f"got {status} {err}")
        status, body = http("POST", "/api/suggest-sources", body={
            "project": "Desk organizer",
            "materials": [{"name": "Cardboard", "needed": 2, "have": 1, "missing": 1}],
        })
        data = json.loads(body or b"{}")
        record(status == 200 and data.get("fallback") is True and data.get("suggestions") == [],
               "No-key mode: source suggestions advertise the offline fallback", f"got {status} {data}")
        return

    status, body = http("POST", "/api/generate-ideas", body={"materials": materials})
    if not record(status == 200, "generate-ideas returns 200 with a real key", f"got {status}"):
        print(body[:400])
        return
    ideas = json.loads(body).get("ideas", [])
    record(len(ideas) > 0, "generate-ideas returns at least one validated idea", f"{len(ideas)} ideas")
    if ideas:
        idea = ideas[0]
        brief = {
            "title": idea["title"], "pitch": idea["pitch"],
            "recipe_graph": [{"a": r["a"], "b": r["b"], "result": r["result_name"]}
                             for r in idea["recipes"]],
            "sub_assemblies": [r["result_name"] for r in idea["recipes"]],
            "final_parts": [f"{f['id']} x{f['qty']}" for f in idea["final_requires"]],
        }
        status, body = http("POST", "/api/generate-steps", body={"idea": brief})
        steps = json.loads(body or b"{}").get("assembly_steps", [])
        record(status == 200 and len(steps) >= 4, "generate-steps returns 4+ steps", f"got {status}, {len(steps)} steps")


def browser_checks(headed):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        warn("Browser checks skipped", "pip install playwright && python3 -m playwright install chromium")
        return

    console_errors = []
    with sync_playwright() as p:
        launch_args = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        try:
            browser = p.chromium.launch(headless=not headed, args=launch_args)
        except Exception:
            # Fall back to an installed Chrome if Playwright's bundled Chromium isn't downloaded.
            browser = p.chromium.launch(headless=not headed, args=launch_args, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        page.goto(BASE)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector("#catalogList .idea-row")
        if page.locator("#introModal.visible").count():
            page.click("#introStartBtn")  # dismiss the how-it-works screen
        record(True, "Page loads and renders the recipe catalog")
        catalog_rows = page.locator("#catalogList .idea-row").count()
        record(catalog_rows >= 101, "Offline recipe pack loads", f"{catalog_rows} catalog rows")

        # --- select the offline Robot Arm ---
        demo_started = time.perf_counter()
        page.locator("#catalogList .idea-row", has_text="Robot Arm").click()
        record(page.locator("#requirementsActive").is_visible(), "Selecting Robot Arm shows its requirements")
        record(page.locator("#buildBtn").is_disabled(), "Build button starts disabled")
        record(page.locator("#hologramRow .final-hologram-card", has_text="Robot Arm").count() == 1,
               "Hologram names and previews the final product")
        page.click("#findSourcesBtn")
        page.wait_for_selector("#sourceSuggestions:not([hidden]) .source-card")
        record(page.locator("#sourceSuggestions .source-card").count() >= 6,
               "Material sourcing guide works without an API key")

        # --- craft every sub-assembly by dragging chips onto the 2D bench ---
        bench = page.locator("#bench").bounding_box()
        target = (bench["x"] + bench["width"] / 2, bench["y"] + bench["height"] / 2)

        def drag_chip(name):
            chip = page.locator("#paletteList .chip:not(.disabled)", has_text=name).first
            if chip.count() == 0:
                return False
            chip.scroll_into_view_if_needed()
            box = chip.bounding_box()
            page.mouse.move(box["x"] + 20, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(target[0], target[1], steps=8)
            page.mouse.up()
            return True

        def palette_qty(name):
            chip = page.locator("#paletteList .chip", has_text=name)
            if chip.count() == 0:
                return 0
            return int(chip.first.locator(".chip-qty").inner_text())

        craft_ok = True
        for a, b, result in CRAFT_PLAN:
            before = palette_qty(result)
            if not (drag_chip(a) and drag_chip(b)):
                craft_ok = record(False, f"Craft {result}", f"no available '{a}' or '{b}' in palette")
                page.click("#clearBenchBtn")
                continue
            page.wait_for_timeout(150)
            after = palette_qty(result)
            if after != before + 1:
                craft_ok = record(False, f"Craft {result}", f"{a} + {b} did not merge (qty {before} -> {after})")
                page.click("#clearBenchBtn")
        if craft_ok:
            record(True, "Crafted every offline sub-assembly via 2D drag-and-merge")

        reqs = page.locator("#reqList .req-item.red").all_inner_texts()
        record(len(reqs) == 0, "All Robot Arm requirements turn green", "still red: " + "; ".join(reqs) if reqs else "")
        build_enabled = page.locator("#buildBtn").is_enabled()
        record(build_enabled, "Build button enables once requirements are met")

        # --- assembly guide ---
        if build_enabled:
            page.click("#buildBtn")
            page.wait_for_selector("#assemblyModal.visible")
            boxes = page.locator("#stepsList input[type=checkbox]")
            n = boxes.count()
            record(n == 7, "Assembly guide shows 7 offline steps", f"got {n}")
            for i in range(n):
                boxes.nth(i).check()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(TINY_PNG)
            page.set_input_files("#photoInput", f.name)
            page.wait_for_selector("#photoPreview:not([hidden])")
            page.wait_for_timeout(300)  # let the preview image load before the temp file goes away
            os.unlink(f.name)
            record(page.locator("#completeBtn").is_enabled(), "Complete button enables after steps + photo")
            page.click("#completeBtn")
            page.wait_for_selector("#completeModal.visible")
            record(page.locator("#badgeRow .badge-pill", has_text="Robot Arm").count() == 1,
                   "Completion awards a Robot Arm badge")
            demo_seconds = time.perf_counter() - demo_started
            record(demo_seconds < 210, "Automated demo path finishes under 3:30", f"{demo_seconds:.1f}s")
            page.click("#closeCompleteBtn")

        # --- 2D bench state survives a reload, and new tokens still merge afterwards ---
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector("#catalogList .idea-row")
        if page.locator("#introModal.visible").count():
            page.click("#introStartBtn")
        page.locator("#catalogList .idea-row", has_text="Robot Arm").click()
        bench = page.locator("#bench").bounding_box()
        target = (bench["x"] + bench["width"] / 2, bench["y"] + bench["height"] / 2)
        drag_chip("Stepper Motor")
        page.reload()
        page.wait_for_selector("#catalogList .idea-row")
        bench = page.locator("#bench").bounding_box()
        target = (bench["x"] + bench["width"] / 2, bench["y"] + bench["height"] / 2)
        before = palette_qty("Drive Unit")
        drag_chip("Pulley")
        page.wait_for_timeout(150)
        record(palette_qty("Drive Unit") == before + 1, "Merge still works after a reload with parts on the bench",
               "token uid collision after reload" if palette_qty("Drive Unit") != before + 1 else "")
        page.click("#clearBenchBtn")

        # --- 3D view opens and renders ---
        page.click(".view-toggle-btn[data-view='3d']")
        page.wait_for_timeout(500)
        size = page.evaluate("(() => { const c = document.getElementById('threeCanvas'); return [c.width, c.height]; })()")
        record(page.locator("#viewer3d").is_visible() and size[0] > 0 and size[1] > 0,
               "3D view opens with a sized canvas", f"canvas {size[0]}x{size[1]}")
        record(page.locator("#threeCanvas").get_attribute("data-final-preview") == "Robot Arm",
               "3D hologram includes a final-product model")
        category_examples = [
            "Jar Lantern", "Self-Watering Planter", "Cardboard Phone Stand", "Jar Lid Spice Rack",
            "Bluetooth Speaker Revival", "Marble Run", "Camp Lantern", "Magnetic Parts Tray",
            "Electromagnet",
        ]
        category_models_ok = True
        for title in category_examples:
            page.locator("#catalogList .idea-row", has_text=title).first.click()
            page.wait_for_timeout(40)
            if page.locator("#threeCanvas").get_attribute("data-final-preview") != title:
                category_models_ok = False
                break
        record(category_models_ok, "3D final-product models render across all project categories")

        # --- phone width: no horizontal page scroll ---
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(200)
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if overflow > 0:
            warn("Horizontal overflow at 390px phone width", f"{overflow}px")
        else:
            record(True, "No horizontal overflow at 390px phone width")

        record(not console_errors, "No console errors during the run", " | ".join(console_errors[:5]))
        browser.close()


def main():
    global BASE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--with-ai", action="store_true", help="use the real API key and exercise AI endpoints")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--base-url", help="test an already-running local or hosted deployment instead of starting server.py")
    args = ap.parse_args()
    if args.base_url:
        BASE = args.base_url.rstrip("/")

    server = None if args.base_url else start_server(args.with_ai)
    try:
        http_checks(args.with_ai)
        browser_checks(args.headed)
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()

    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print(f"\n{len(results) - len(fails) - len(warns)} passed, {len(fails)} failed, {len(warns)} warnings")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
