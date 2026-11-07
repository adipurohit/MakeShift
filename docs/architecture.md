# Architecture

## One app, two back ends

The browser app (`index.html`, `app.js`, `parts.js`, `style.css`, `recipes/pack.json`) is plain static files. All 101 built-in recipes, catalog matching, merging, the 3D view, and the assembly guide run in the browser with no server.

Only the AI features need a back end: camera scan, AI ideas, AI steps, and AI sourcing. Two back ends answer the same four endpoints:

| | Cloudflare Worker (`worker/`) | Python server (`app/server.py`) |
|---|---|---|
| Used for | The public site, adipurohit.com/makeshift | Local development, with no Cloudflare account |
| Key lives in | Worker secret `GEMINI_API_KEY` | `app/.env` |
| Extras | Idea cache, per-session and per-network rate limits, origin check | None |

## Why the logic exists twice, and how it stays in sync

This is duplicated logic, on purpose. Cloudflare Workers run JavaScript, not Python, and the team prototypes in Python, so both exist. Three things keep them from drifting:

1. **One source for prompts and schemas.** `server.py` owns every prompt, schema, and limit. `scripts/export-ai-config.py` writes them to `worker/ai-config.json`, which the Worker imports. Nobody edits the JSON by hand.
2. **A parity test.** `tests/worker_parity_test.py` fails if the JSON is out of date, and feeds 500 generated model responses through both validators, requiring identical output.
3. **An end-to-end test of the Worker.** `tests/worker_e2e_test.py` runs the real Worker with `wrangler dev` against a stand-in Gemini that rejects malformed requests the way the real API does.

What the parity test does not cover: the HTTP call to Gemini differs (the Python SDK versus a raw `fetch`). That gap caused one live outage: the Worker sent the schema in a field Gemini rejects. The stand-in Gemini now checks for it.

**If you only change one thing:** to retire the duplication, run the Worker locally with `npx wrangler dev` and delete the AI code from `server.py`, keeping it as a static file server. The team kept both for now because `server.py` needs no Node or Cloudflare login.

## What the 3D view is, and isn't

The 3D view shows each part as a simple shape picked from its category (a cylinder for a motor, a flat box for a board), and the finished build as a rough silhouette. It's a visual aid for the crafting game. It is **not** CAD: no real dimensions, no fit or clearance checks, no strength or electrical analysis. The built-in recipes were written and reviewed by people, not engineered. Treat every build as a starting point to check with your own hands.

## AI safety checks

The model's ideas pass through `validate_idea` before the app sees them. Beyond structure (every merge uses real parts, no dead ends), it rejects ideas that use hazardous parts (capacitors, transformers, power supplies, broken glass, swollen batteries), fire or launch anything, put hot items on rubber or plastic, bear a person's weight, hang weight overhead, put solder near food, stand in for a lock or alarm, control shop machinery, claim motion or light without a power or light source, or treat broken parts as working ones. See `docs/recipe-quality.md` for how often each check fires on real model output.
