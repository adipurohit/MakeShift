# MakeShift

Turn what you have into what you need.

MakeShift treats broken gear and scrap as a parts inventory. Pick a build, drag parts together to merge them into sub-assemblies, fill the build checklist, then follow a step-by-step assembly guide to make something real.

## What's inside

- **101 offline recipes** across 10 categories: Lighting, Robotics, Garden, Home & Desk, Storage, Sound, Play, Outdoor, Workshop, and Science. Each recipe brings its own parts and works with no API key or wifi.
- **2D and 3D build views.** Merge parts on a 2D bench, or switch to 3D to see each part as a shape.
- **Assembly guide** with checkable steps, a progress photo, a completion badge, and a suggested next upgrade.
- **How-it-works screen** on first visit, reopened any time from the top bar.
- **AI features** (need a Groq API key): scan a material with your camera, and generate new build ideas from your own inventory.

## Run it

You need Python 3.

```bash
git clone https://github.com/adipurohit/MakeShift.git
cd MakeShift/cube-mvp
python3 server.py
```

Open http://localhost:8743 in Chrome. Press Ctrl+C to stop the server.

For the AI features, copy `cube-mvp/.env.example` to `cube-mvp/.env` and add your Groq API key. Never commit that file.

To host MakeShift at adipurohit.com/makeshift on Cloudflare and turn on the AI features there, follow [DEPLOYMENT.md](DEPLOYMENT.md).

## How a build works

1. **Pick a recipe** from the Recipe Catalog. Search by name or filter by category.
2. **Merge parts.** Drag two parts onto the bench. Parts that fit together merge into a new piece, for example Stepper Motor + Pulley makes a Drive Unit.
3. **Fill the checklist.** The bar under the bench turns each requirement green once you have enough. Parts marked **as-is** go straight into the build with no merging, and parts on the bench still count.
4. **Build it.** Press Build It, check off each step, add a photo, and earn a badge.

## Add a recipe

Recipes live in [`cube-mvp/recipes/pack.json`](cube-mvp/recipes/pack.json). See [`cube-mvp/recipes/README.md`](cube-mvp/recipes/README.md) for the format, then check your work:

```bash
python3 cube-mvp/recipes/validate.py
python3 cube-mvp/tests/pack_test.py <recipe_id>
```

## Tests

| Command | Checks |
|---------|--------|
| `python3 cube-mvp/tests/smoke.py` | Server endpoints and the full Robot Arm build in a headless browser |
| `python3 cube-mvp/tests/pack_test.py` | Builds all 100 pack recipes end to end |
| `python3 cube-mvp/tests/bench_count_test.py` | Parts on the bench count toward the checklist, including as-is parts |
| `python3 cube-mvp/tests/test_recipes.py` | AI recipe validation rules |
| `python3 cube-mvp/tests/worker_parity_test.py` | Cloudflare Worker treats AI output exactly like `server.py` |
| `python3 cube-mvp/tests/worker_e2e_test.py` | Cloudflare Worker end to end with a stand-in Groq (needs `wrangler`) |
| `python3 cube-mvp/tests/scan_browser.py` | Camera scan flow with a fake camera |
| `cd cube-mvp && npm i --no-save jsdom && node tests/scan_logic.test.js` | Camera scan permission and timeout paths |
| `python3 cube-mvp/tests/recipe_quality.py --stub` | Recipe quality harness (drop `--stub` to run against the API) |

Browser tests need Playwright: `pip install playwright && python3 -m playwright install chromium`.

## Project docs

- [TASKS.md](TASKS.md): task board and status
- [PITCH.md](PITCH.md): pitch script and live-demo plan
- [DEPLOYMENT.md](DEPLOYMENT.md): hosting on Render
- [cube-mvp/README.md](cube-mvp/README.md): how the app works under the hood
