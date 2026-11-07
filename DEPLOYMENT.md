# Deploy MakeShift on Render

The repository includes a Render Blueprint for a single Python web service. It serves the frontend and the three optional Anthropic-backed API endpoints from one origin.

## Current deployment

- URL: [https://makeshift-cube-demo.onrender.com](https://makeshift-cube-demo.onrender.com)
- Render service: `makeshift-cube-demo`
- Deploy branch: `main`
- Verified 2026-11-07 at commit `b945f83`: `python cube-mvp/tests/smoke.py --base-url https://makeshift-cube-demo.onrender.com` passed all 23 checks, including the 100-recipe pack plus Robot Arm, the complete build flow, 3D, mobile width, and console-error checks. The automated Robot Arm stage path completed in 6.3 seconds before narration.
- `ANTHROPIC_API_KEY` is not configured in Render. The offline catalog and Robot Arm work publicly; camera identification and generated ideas/steps correctly return the no-key fallback until a dedicated capped key is added.

## Create the service

1. Merge this branch into the branch Render will deploy.
2. In the Render Dashboard, choose **New → Blueprint**.
3. Connect `https://github.com/adipurohit/MakeShift`.
4. Select the branch containing `render.yaml` and create the Blueprint.
5. When prompted for `ANTHROPIC_API_KEY`, enter a dedicated project key with an appropriate spending limit. Never commit the key or paste it into an issue, pull request, or chat.
6. Wait for the service health check at `/` to pass, then copy the generated `https://…onrender.com` URL.

Render builds from `cube-mvp/`, installs the pinned Python SDK, starts `server.py`, and supplies the public listening port through the `PORT` environment variable.

## Verify the deployment

Open the public URL in a private browser window and verify:

- The MakeShift workspace, local Three.js assets, and offline Robot Arm recipe load without console errors.
- The 2D and 3D controls work.
- Reset restores the deterministic offline state.
- With the hosted key enabled, **Buildable Now** generates ideas and assembly steps.
- Denying camera permission exposes the manual-entry fallback.
- No API key or secret appears in page source, browser requests, repository files, or error messages.

The offline Robot Arm remains usable when the API key is absent or the Anthropic API is unavailable.

## Rotate or remove the key

After the event or demo window:

1. Remove `ANTHROPIC_API_KEY` from the Render service or suspend the service.
2. Revoke the deployed key in the Anthropic console.
3. Create a new limited key before any future hosted demo instead of reusing the old one.

## Local behavior

Local startup is unchanged:

```bash
cd cube-mvp
python3 server.py
```

Without `PORT`, the server continues to listen on port `8743`.
