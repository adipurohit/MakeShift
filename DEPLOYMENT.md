# Deploy MakeShift

MakeShift is set up to run at **adipurohit.com/makeshift** on Cloudflare. A Render setup for the Python server also exists, at the end of this file.

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

Optional variables (type **Text**): `GEMINI_TEXT_MODEL` and `GEMINI_VISION_MODEL` override the models, same as in `cube-mvp/.env`.

### Change a prompt

Edit the prompt in `cube-mvp/server.py`, then run:

```bash
python3 scripts/export-ai-config.py
```

`cube-mvp/tests/worker_parity_test.py` fails if you forget, and checks the Worker and `server.py` treat AI output identically.

### Test the Worker locally

```bash
python3 cube-mvp/tests/worker_e2e_test.py
```

Runs the Worker with `wrangler dev` against a stand-in Gemini server: page load, camera scan in a browser, ideas, steps, and the guards. No real key needed.

### Rotate or remove the key

Delete or replace the `GEMINI_API_KEY` secret in the Worker settings, then revoke the old key in the Google AI Studio.

## Render (Python server)

[`render.yaml`](render.yaml) runs `cube-mvp/server.py` as one web service.

The existing Render deployment is [https://makeshift-cube-demo.onrender.com](https://makeshift-cube-demo.onrender.com), service `makeshift-cube-demo`, tracking `main`. It was last fully smoke-tested at commit `b945f83`; rerun the hosted smoke suite after merging this branch.

1. In the Render Dashboard, choose **New → Blueprint** and connect `adipurohit/MakeShift`.
2. When prompted for `GEMINI_API_KEY`, enter a dedicated key with a spending limit.
3. Wait for the health check at `/` to pass.

Render supplies the listening port through `PORT`. Locally, without `PORT`, the server listens on 8743:

```bash
cd cube-mvp
python3 server.py
```
