#!/usr/bin/env python3
"""
Camera-scan test in a REAL headless Chromium using its synthetic camera
(--use-fake-device-for-media-stream). Exercises real getUserMedia, a real <video>, canvas capture and JPEG
encoding. The /api/identify-material reply is stubbed, so no API key is needed.

This is not a physical-webcam test (no real lens, lighting or OS permission prompt), but it proves the
whole front-end path works against a genuine MediaStream.

    python3 cube-mvp/tests/scan_browser.py
"""
import base64, json, subprocess, sys, time, urllib.request, os
from pathlib import Path
from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parent.parent
PORT = 8751
fails = []

def check(ok, name, detail=""):
    print(("PASS" if ok else "FAIL"), name, detail)
    if not ok: fails.append(name)

srv = subprocess.Popen([sys.executable, "-c", f"import server;server.PORT={PORT};server.ThreadingHTTPServer(('',{PORT}),server.Handler).serve_forever()"],
                       cwd=APP, env={**os.environ, "GROQ_API_KEY": "stub"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try: urllib.request.urlopen(f"http://localhost:{PORT}/", timeout=1); break
        except Exception: time.sleep(0.25)

    with sync_playwright() as p:
        args = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
        try: browser = p.chromium.launch(headless=True, args=args)
        except Exception: browser = p.chromium.launch(headless=True, args=args, channel="chrome")
        ctx = browser.new_context(permissions=["camera"], viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # "Failed to load resource" is Chromium logging our own deliberately aborted request in the last step.
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        sent = {}
        def identify(route):
            sent["body"] = json.loads(route.request.post_data)
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"name": "broken stepper motor", "confidence": "high"}))
        page.route("**/api/identify-material", identify)
        page.goto(f"http://localhost:{PORT}/")
        page.evaluate("localStorage.clear()"); page.reload()
        page.evaluate("localStorage.setItem('makeshift_intro_seen', '1')"); page.reload()  # skip the how-it-works screen

        page.click("#scanBtn")
        page.wait_for_function("document.getElementById('scanVideo').videoWidth > 0", timeout=8000)
        vw = page.evaluate("document.getElementById('scanVideo').videoWidth")
        check(vw > 0, "live video frames arrive from getUserMedia", f"({vw}px wide)")
        check(page.evaluate("document.getElementById('scanStatus').textContent").startswith("Point"), "status prompts the user to capture")

        page.click("#captureBtn")
        page.wait_for_selector("#scanResult:not([hidden])", timeout=5000)
        img = sent["body"]["image"]
        check(img.startswith("data:image/jpeg;base64,"), "capture sends a JPEG data URL")
        raw = base64.b64decode(img.split(",", 1)[1])
        check(raw[:2] == b"\xff\xd8" and len(raw) > 1000, "JPEG is a real, non-trivial image", f"({len(raw)//1024} KB)")
        dims = page.evaluate("[document.getElementById('scanCanvas').width, document.getElementById('scanCanvas').height]")
        check(max(dims) <= 1024, "frame downscaled to <=1024px", str(dims))
        check(page.input_value("#scanNameInput") == "broken stepper motor", "AI name fills the editable field")

        page.click("#scanRetryBtn")
        page.wait_for_selector("#scanCameraWrap:not([hidden])")
        check(page.evaluate("document.getElementById('scanVideo').videoWidth") > 0, "Retake shows live video again")

        page.keyboard.press("Escape")
        live = page.evaluate("(document.getElementById('scanVideo').srcObject||{getTracks:()=>[]}).getTracks().filter(t=>t.readyState==='live').length")
        check(not page.evaluate("document.getElementById('scanModal').classList.contains('visible')") and live == 0, "Esc closes the modal and releases the camera")

        page.click("#scanBtn"); page.wait_for_function("document.getElementById('scanVideo').videoWidth > 0")
        page.click("#captureBtn"); page.wait_for_selector("#scanResult:not([hidden])")
        page.click("#scanConfirmBtn")
        check("broken stepper motor" in page.inner_text("#inventoryList") if page.query_selector("#inventoryList") else "broken stepper motor" in page.content().lower(), "confirmed item lands in the inventory")

        page.route("**/api/identify-material", lambda r: r.abort())
        page.click("#scanBtn"); page.wait_for_function("document.getElementById('scanVideo').videoWidth > 0")
        page.click("#captureBtn"); page.wait_for_selector("#manualAddPanel:not([hidden])", timeout=5000)
        check("reach the MakeShift server" in page.inner_text("#scanStatus"), "unreachable server falls back to manual entry with a clear message")
        check(not errors, "no console/page errors", "; ".join(errors)[:200])
        browser.close()
finally:
    srv.terminate()

print(f"\n{'ALL PASSED' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
