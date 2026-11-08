# Deploy MakeShift

MakeShift runs at **adipurohit.com/makeshift** on Cloudflare. That is the only public URL; the old Render copy redirects to it.

## Cloudflare (adipurohit.com/makeshift)

A Cloudflare Worker named `makeshift` serves the app. The config lives in [`wrangler.jsonc`](wrangler.jsonc):

- **Static app**: `scripts/build-web.sh` copies only the browser files into `dist/makeshift/`.
- **AI endpoints**: [`worker/`](worker/) answers `/makeshift/api/generate-ideas`, `generate-steps`, `suggest-sources`, and `identify-material` (the camera scan), the same four endpoints `server.py` answers locally. Prompts and schemas come from `server.py` through `worker/ai-config.json`.
- **Route**: `adipurohit.com/makeshift*`. A route takes priority over the portfolio Worker for those paths only, so the rest of adipurohit.com is untouched.
- **Rate limit**: about 20 AI calls per visitor per minute, so a public page can't drain the key. Requests from other websites are refused.

### First-time setup

1. In the Cloudflare dashboard, go to **Workers & Pages → Create → Connect GitHub**, and give the Cloudflare app access to `adipurohit/MakeShift`.
2. Pick the repo. Keep the Worker name `makeshift`, which must match `wrangler.jsonc`. Keep the default deploy command `npx wrangler deploy`. Deploy.
3. Every push to `main` redeploys.

### Turn on the AI features (camera scan, AI ideas, AI steps)

The AI runs on Gemini. Add your Gemini key as an encrypted secret, never in the repo:

1. **Workers & Pages → makeshift → Settings → Variables and Secrets → Add**.
2. Type: **Secret**. Name: `GEMINI_API_KEY`. Value: your Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
3. Select **Deploy**. The secret takes effect right away, with no code change.

Without the secret, the catalog recipes work and the AI features show a short notice.

Set a spending limit on the key in the Google AI Studio. Anyone who opens the site uses your key through the Worker, within the rate limit above.

### Rate limited? Change the model

Gemini enforces limits **per project and per model**: a second API key in the same project adds nothing, but each different model has its own allowance. Requests per day reset at midnight Pacific time. Google lists the limits in its [rate-limits documentation](https://ai.google.dev/gemini-api/docs/rate-limits), and AI Studio shows your project's actual usage. Lite variants of a model have generally allowed more requests per minute than the full model.

The model is a Worker variable, not a setting in the web app: every visitor shares your key and your quota, so a model picker in the page would let anyone spend it on whichever model they like, and a different choice would not add capacity anyway.

**Workers & Pages → makeshift → Settings → Variables and Secrets → Add** (type **Text**), then **Deploy**. It takes effect right away, with no code change:

| Variable | What it does | Default |
|---|---|---|
| `GEMINI_TEXT_MODEL` | Model for ideas, steps and sourcing | `gemini-3.8-flash` |
| `GEMINI_VISION_MODEL` | Model for photo scans | same as the text model |
| `GEMINI_FALLBACK_MODEL` | Models to try, in order, when the one above is rate limited, overloaded or not found. **Comma-separated**, e.g. `gemini-3.6-flash, gemini-3.1-flash-lite`. `off` disables fallbacks | `gemini-3.6-flash` |
| `GEMINI_THINKING_LEVEL` | `low` (default) or `off` to send no thinking setting | `low` |

Model IDs come from the [model list](https://ai.google.dev/gemini-api/docs/models). A `models/` prefix and extra spaces are fine. Defaults live in `app/server.py`.

How it behaves: a model that answers 429, 503, 404 or times out is skipped for 2 minutes, so the next requests go straight to the next model in the list instead of waiting out another failure. If every model fails, the page shows a plain "AI is busy" message and the catalog recipes keep working. A misspelled model name falls through to the next model rather than breaking the AI, and the error message names the variables to fix if none of them exist.

To see what happened, open the Worker's **Logs** (Observability) tab: lines starting with `[ai]` say which model was skipped and when a fallback answered. The JSON reply of each AI call also has a `model` field naming the model that answered.

`wrangler.jsonc` sets `keep_vars: true`, so variables you add in the dashboard survive the redeploy that follows every push to `main`. For local runs, set the same names in `app/.env`.

### Change a prompt

Edit the prompt in `app/server.py`, then run:

```bash
python3 scripts/export-ai-config.py
```

`app/tests/worker_parity_test.py` fails if you forget, and checks the Worker and `server.py` treat AI output identically.

### Test the Worker locally

```bash
python3 app/tests/worker_e2e_test.py
```

Runs the Worker with `wrangler dev` against a stand-in Gemini server: page load, camera scan in a browser, ideas, steps, and the guards. No real key needed.

### Rotate or remove the key

Delete or replace the `GEMINI_API_KEY` secret in the Worker settings, then revoke the old key in the Google AI Studio.

## Render (retired)

The old Render service, makeshift-cube-demo.onrender.com, still tracks `main`, but `server.py` now redirects every request there to adipurohit.com/makeshift (Render sets `RENDER=true`, which turns the redirect on). One canonical URL means a judge can't land on a copy with no AI and a cold start. Delete the service in the Render dashboard whenever convenient; nothing depends on it.

## Run locally

```bash
cd app
python3 server.py              # http://localhost:8743, Python server
```

Or run the exact production code with Wrangler (needs Node 18+):

```bash
npm install
npm run dev                    # http://localhost:8787/makeshift/
```

For AI locally, put `GEMINI_API_KEY=...` in `app/.env` for the Python server, or in `.dev.vars` at the repo root for Wrangler. Never commit either file.
