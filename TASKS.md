# MakeShift / CUBE — Task Board

Work breakdown for the CUBE demo (`cube-mvp/`) so teammates and agents can pick up pieces in parallel without stepping on each other. See [`cube-mvp/README.md`](cube-mvp/README.md) for how the app works end to end before picking a task.

## How to pick up a task

1. Claim a task by opening an issue or commenting, so two people don't duplicate work.
2. Branch off `main` (once [PR #1](https://github.com/adipurohit/MakeShift/pull/1) is merged) as `task/<short-name>`, e.g. `task/real-part-photos`.
3. Each task below lists which files it touches — if your task isn't listed as touching `app.js`, don't edit it; flag here instead if you think you need to, so we don't get silent merge conflicts on the biggest file.
4. Open a PR back to `main` when done. Small, reviewable PRs over one giant one.
5. You'll need your own Anthropic API key in `cube-mvp/.env` (copy from `.env.example`) for anything that touches AI features — never commit that file.

---

## Open tasks

### 1. Test the camera scan on a real device
**Why:** Built and tested with a mocked fallback only — live camera + vision identification has never run against a real webcam.
**Do:** Run `cube-mvp/server.py` on a laptop with a working camera, click Scan Material, and actually capture a few real objects. Check: does the camera permission prompt work cleanly, is the AI's name guess usable, does the flash/preview UI feel right, does the manual fallback still work if you deny permission.
**Touches:** `cube-mvp/index.html`, `cube-mvp/style.css`, `cube-mvp/app.js` (scan modal section only), `cube-mvp/server.py` (`identify_material`/`/api/identify-material` only).
**Done when:** A short writeup here (or an issue) of what worked, what didn't, and a PR fixing anything broken.

### 2. Real part icons/photos instead of placeholder initials
**Why:** Every item currently renders as a colored circle with 2-letter initials (`ST`, `PU`, etc.) — real photos of actual scrap would look far more convincing on stage.
**Do:** Either swap in an uploaded-photo-per-item feature (store a thumbnail when a material is added/scanned, show it instead of the initials circle), or just a curated icon set for common material categories.
**Touches:** `cube-mvp/app.js` (`colorForId`/`shortFor` and the rendering functions that build `.item-icon`/`.chip-icon`), `cube-mvp/style.css`.
**Done when:** Items show something more specific than initials, in both the Inventory panel and the 2D/3D viewer.

### 3. 3D models beyond boxes/icosahedrons
**Why:** The 3D viewer currently represents every raw material as a box and every crafted part as an icosahedron — functional but generic.
**Do:** Either load small primitive-based "part-like" shapes per category (motor = cylinder, board = flat box, etc.) or go further with simple glTF models if time allows. Keep performance light — this runs on a laptop, not a render farm.
**Touches:** `cube-mvp/app.js` (`meshGeometryFor` and the 3D render functions only — don't touch the 2D merge logic or the AI/backend code).
**Done when:** At least a few distinct shape categories exist beyond "box vs icosahedron."

### 4. Recipe quality pass — review AI-generated ideas for physical plausibility
**Why:** The AI proposes build ideas and recipes on the fly; nobody's systematically checked a batch of them for "would this actually work/be safe."
**Do:** Run the idea generator against 10-15 varied material lists, read through the generated recipes and assembly steps, flag anything physically implausible, unsafe, or just boring. Tune `IDEA_SYSTEM_PROMPT` / `STEPS_SYSTEM_PROMPT` in `server.py` based on what you find.
**Touches:** `cube-mvp/server.py` (prompts + schemas only).
**Done when:** A short notes doc of before/after examples, plus a prompt-tuning PR if issues were found.

### 5. Automated smoke test
**Why:** Everything so far has been tested by hand in a browser. A basic script would catch regressions as more people touch the code.
**Do:** A small script (Playwright, Puppeteer, or even a shell script hitting the backend endpoints directly) that: starts the server, adds a material, hits `/api/generate-ideas` (or exercises the offline Robot Arm path if no API key), and checks the page doesn't throw console errors.
**Touches:** New files only (e.g. `cube-mvp/tests/`) — shouldn't need to modify existing app code.
**Done when:** `python3 cube-mvp/tests/smoke.py` (or equivalent) runs and reports pass/fail.

### 6. Deploy a shareable hosted version
**Status:** Live on Render at [makeshift-cube-demo.onrender.com](https://makeshift-cube-demo.onrender.com) from `task/deploy-hosted`. The offline demo is verified; AI endpoints remain disabled until a limited `ANTHROPIC_API_KEY` is added directly in Render.

**Why:** Right now this only runs on `localhost` on whoever's laptop has it checked out. A hosted version (even temporary) would let judges/teammates try it without a setup step.
**Do:** Pick a host (Render, Railway, Fly.io, etc. — anything that can run a long-lived Python process and hold an env var for the API key). Note: this means the key leaves your laptop and sits on that host — use a key with a spending cap, not a personal unrestricted one.
**Touches:** New deploy config files only; flag here first if it needs changes to `server.py` (e.g. reading `PORT` from env).
**Done when:** A working public URL, documented here, with the key rotated/capped appropriately.

### 7. Pitch narrative / deck pass
**Why:** The app is built; the story that gets told about it on stage isn't locked yet.
**Do:** Not code — draft the pitch flow (what gets demoed live vs. described, which materials to bring as physical props if any, timing). Use the "Judge-ready pitch" line and north star from the original product doc as a starting point.
**Touches:** Nothing in `cube-mvp/` — this is a separate doc/slides, link it here once started.
**Done when:** A deck or script exists and the team has rehearsed the live-demo portion at least once (ideally against the offline Robot Arm path, since it's guaranteed to work without wifi).

### 8. Accessibility / mobile pass
**Why:** Untested on anything other than a desktop browser at normal zoom. If judges or teammates pull it up on a phone or tablet, the 3-panel layout may not hold up.
**Do:** Check the responsive breakpoint in `cube-mvp/style.css` (`@media (max-width: 980px)`), fix anything broken on a phone-width viewport, and do a basic keyboard/contrast pass.
**Touches:** `cube-mvp/style.css` only, ideally.
**Done when:** The app is at least usable (not necessarily beautiful) at phone width.

---

## Already done (don't duplicate)

- Core 2D/3D crafting sandbox, hologram previews, AI idea generation + on-demand step generation, camera scan with manual fallback, offline Robot Arm guaranteed-demo path. See `cube-mvp/README.md` for the full list of judgment calls already made.
