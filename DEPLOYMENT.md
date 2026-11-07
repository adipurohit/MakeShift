# Deploy CUBE on Render

The repository includes a Render Blueprint for a single Python web service. It serves the frontend and the three optional Anthropic-backed API endpoints from one origin.

## Current deployment

- **Public URL:** [https://makeshift-cube-demo.onrender.com](https://makeshift-cube-demo.onrender.com)
- **Host:** Render free web service
- **Source branch:** `task/deploy-hosted`
- **Verified commit:** `f5f546a`
- **AI status:** No hosted Anthropic key is configured. The offline Robot Arm works; AI generation and vision endpoints return a safe unavailable response until a limited key is added directly in Render.

After a free instance has been idle, its first request can take longer while Render starts it again.

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

- The CUBE workspace, local Three.js assets, and offline Robot Arm recipe load without console errors.
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
