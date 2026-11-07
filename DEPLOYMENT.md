# Deploy MakeShift

MakeShift is set up to run at **adipurohit.com/makeshift** on Cloudflare. A Render setup for the Python server also exists, at the end of this file.

## Cloudflare (adipurohit.com/makeshift)

A Cloudflare Worker named `makeshift` serves the app. The config lives in [`wrangler.jsonc`](wrangler.jsonc):

- **Static app**: `scripts/build-web.sh` copies only the browser files into `dist/makeshift/`.
- **AI endpoints**: [`worker/`](worker/) answers `/makeshift/api/generate-ideas`, `generate-steps`, and `identify-material` (the camera scan), the same three endpoints `server.py` answers locally. Prompts and schemas come from `server.py` through `worker/ai-config.json`.
- **Route**: `adipurohit.com/makeshift*`. A route takes priority over the portfolio Worker for those paths only, so the rest of adipurohit.com is untouched.
- **Rate limit**: about 20 AI calls per visitor per minute, so a public page can't drain the key. Requests from other websites are refused.

### First-time setup

1. In the Cloudflare dashboard, go to **Workers & Pages → Create → Connect GitHub**, and give the Cloudflare app access to `adipurohit/MakeShift`.
2. Pick the repo. Keep the Worker name `makeshift`, which must match `wrangler.jsonc`. Keep the default deploy command `npx wrangler deploy`. Deploy.
3. Every push to `main` redeploys.

### Turn on the AI features (camera scan, AI ideas, AI steps)

The AI runs on Groq. Add your Groq key as an encrypted secret, never in the repo:

1. **Workers & Pages → makeshift → Settings → Variables and Secrets → Add**.
2. Type: **Secret**. Name: `GROQ_API_KEY`. Value: your Groq key (starts with `gsk_`).
3. Select **Deploy**. The secret takes effect right away, with no code change.

Without the secret, the catalog recipes work and the AI features show a short notice.

Set a spending limit on the key in the Groq console. Anyone who opens the site uses your key through the Worker, within the rate limit above.

Optional variables (type **Text**): `GROQ_TEXT_MODEL` and `GROQ_VISION_MODEL` override the models, same as in `cube-mvp/.env`.

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

Runs the Worker with `wrangler dev` against a stand-in Groq server: page load, camera scan in a browser, ideas, steps, and the guards. No real key needed.

### Rotate or remove the key

Delete or replace the `GROQ_API_KEY` secret in the Worker settings, then revoke the old key in the Groq console.

## Render (Python server)

[`render.yaml`](render.yaml) runs `cube-mvp/server.py` as one web service.

1. In the Render Dashboard, choose **New → Blueprint** and connect `adipurohit/MakeShift`.
2. When prompted for `GROQ_API_KEY`, enter a dedicated key with a spending limit.
3. Wait for the health check at `/` to pass.

Render supplies the listening port through `PORT`. Locally, without `PORT`, the server listens on 8743:

```bash
cd cube-mvp
python3 server.py
```
