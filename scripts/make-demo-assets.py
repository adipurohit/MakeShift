#!/usr/bin/env python3
"""
Regenerate the README screenshots and the fallback demo video from the real app.

Runs cube-mvp/server.py locally with AI off (the demo path that never needs Wi-Fi), then drives a
headless browser through the how-it-works screen, a full Robot Arm build, the 3D view, the assembly
guide, and catalog matching for a typed-in inventory. Writes:

    docs/screenshots/*.png   stills for the README
    docs/demo.mp4            about 60 s screen recording, the fallback video for demo day
    docs/demo.gif            short, small loop for the README

Usage: python3 scripts/make-demo-assets.py     (needs Playwright with Chromium, and ffmpeg)
"""
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "cube-mvp"
DOCS = ROOT / "docs"
SHOTS = DOCS / "screenshots"
PORT = 8743
BASE = f"http://localhost:{PORT}/"
W, H = 1280, 800

CRAFT_PLAN = [  # Robot Arm, in build order (mirrors tests/smoke.py)
    ("Stepper Motor", "Pulley"), ("Drive Unit", "Timing Belt"),
    ("Stepper Motor", "Pulley"), ("Drive Unit", "Timing Belt"),
    ("Al. Extrusion", "Smooth Rod"), ("Rail", "Linear Bearing"),
    ("Al. Extrusion", "Smooth Rod"), ("Rail", "Linear Bearing"),
    ("Bed Clip", "Zip Tie"),
]


def main():
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen([sys.executable, "server.py"], cwd=APP, env={"PATH": "/usr/bin:/bin"},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    video_dir = Path(tempfile.mkdtemp())
    try:
        for _ in range(50):
            with socket.socket() as s:
                if s.connect_ex(("localhost", PORT)) == 0:
                    break
            time.sleep(0.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": W, "height": H}, color_scheme="light",
                                      record_video_dir=str(video_dir), record_video_size={"width": W, "height": H})
            page = ctx.new_page()
            page.goto(BASE)
            page.evaluate("localStorage.clear()")
            page.reload()
            page.wait_for_selector("#introModal.visible")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(SHOTS / "01-how-it-works.png"))

            page.click("#introDemoBtn")
            page.wait_for_timeout(1200)
            page.screenshot(path=str(SHOTS / "02-robot-arm-parts.png"))

            bench = page.locator("#bench").bounding_box()
            center = (bench["x"] + bench["width"] / 2, bench["y"] + bench["height"] / 2)

            def drag(name):
                chip = page.locator("#paletteList .chip:not(.disabled)", has_text=name).first
                chip.scroll_into_view_if_needed()
                box = chip.bounding_box()
                page.mouse.move(box["x"] + 20, box["y"] + box["height"] / 2)
                page.mouse.down()
                page.mouse.move(center[0], center[1], steps=18)
                page.mouse.up()
                page.wait_for_timeout(450)

            for i, (a, b) in enumerate(CRAFT_PLAN):
                drag(a)
                drag(b)
                page.wait_for_timeout(500)
                if i == 3:
                    page.screenshot(path=str(SHOTS / "03-merging-with-guide.png"))

            page.get_by_role("button", name="3D").click()
            page.wait_for_timeout(2500)
            page.screenshot(path=str(SHOTS / "04-3d-view.png"))
            page.get_by_role("button", name="2D").click()
            page.wait_for_timeout(600)

            page.click("#buildBtn")
            page.wait_for_selector("#assemblyModal.visible")
            page.wait_for_timeout(1200)
            boxes = page.locator("#stepsList input[type=checkbox]")
            for i in range(boxes.count()):
                boxes.nth(i).check()
                page.wait_for_timeout(250)
            page.screenshot(path=str(SHOTS / "05-assembly-guide.png"))
            photo = video_dir / "progress.png"
            page.screenshot(path=str(photo), clip={"x": 0, "y": 0, "width": 400, "height": 300})
            page.set_input_files("#photoInput", str(photo))
            page.wait_for_timeout(800)
            page.click("#completeBtn")
            page.wait_for_selector("#completeModal.visible")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(SHOTS / "06-build-complete.png"))
            page.click("#closeCompleteBtn")
            page.wait_for_timeout(600)

            for name, qty in (("plastic bottle", 3), ("rubber bands", 10), ("cardboard box", 2), ("wooden dowel", 2)):
                page.fill("#materialNameInput", name)
                page.fill("#materialQtyInput", str(qty))
                page.press("#materialNameInput", "Enter")
                page.wait_for_timeout(500)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOTS / "07-catalog-matches.png"))
            page.wait_for_timeout(1500)
            video = page.video.path()
            ctx.close()

            phone = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark", device_scale_factor=2)
            p2 = phone.new_page()
            p2.goto(BASE)
            p2.evaluate("localStorage.setItem('makeshift_intro_seen', '1')")
            p2.reload()
            p2.wait_for_timeout(1000)
            p2.screenshot(path=str(SHOTS / "08-phone-dark.png"))
            phone.close()
            browser.close()

        ff = shutil.which("ffmpeg")
        if not ff:
            print("ffmpeg not found: screenshots written, video skipped")
            return 0
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(video), "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(DOCS / "demo.mp4")], check=True)
        # short README loop: the merges and the 3D view, small and slow enough to read
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "4", "-t", "24", "-i", str(video), "-vf",
                        "fps=8,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer",
                        str(DOCS / "demo.gif")], check=True)
    finally:
        server.terminate()
    for f in sorted(SHOTS.glob("*.png")) + [DOCS / "demo.mp4", DOCS / "demo.gif"]:
        if f.exists():
            print(f"{f.relative_to(ROOT)}  {f.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
