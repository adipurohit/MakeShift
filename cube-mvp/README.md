# MakeShift — Fusion-style scrap-to-creation demo (MVP)

"Turn what you have into what you need." Scan or type in materials, get AI-generated build ideas, then craft one in a CAD-inspired workspace — a 2D bubble-merge canvas or a real 3D viewer, your choice, with a recipe catalog and live red/green requirements always visible.

## Layout (inspired by Fusion 360)

- **Top bar** — camera Scan button, badges, Reset.
- **Left panel** — your Inventory (add/scan materials, +/- quantities) and **Buildable Now**: ideas the AI thinks you can start with exactly what you've got.
- **Center** — the viewer. Toggle **2D** (drag-to-merge bubble canvas) or **3D** (real Three.js scene: orbit the camera, drag parts around a staging area, drop new parts in from the palette, merge by proximity). Below it, the active recipe's red/green requirements and the **Build It** button.
- **Right panel** — the full **Recipe Catalog**: every idea MakeShift knows about, ready or not, so there's always something to work toward.

Selecting a recipe (left, right, or the pinned offline example) sets it as the active blueprint: its missing sub-assemblies appear as **holograms** — dashed ghost chips in 2D, translucent wireframe shapes floating above the 3D staging area — that fill in solid as you craft the right parts.

## One-time setup: your API key

```bash
cd cube-mvp
cp .env.example .env
open -e .env
```

Paste your real Groq key over the placeholder, save, close. Do this yourself in Terminal — never paste a key into a chat with Claude. `.env` is git-ignored.

**No key? Everything still works.** The pinned "Robot Arm (offline)" recipe needs zero network calls — AI idea generation, step generation, and camera-vision scanning all degrade gracefully to manual alternatives if the key is missing or a call fails.

## Run it

```bash
cd cube-mvp
python3 server.py
```

Open **http://localhost:8743**. Install the SDK first with `pip install -r requirements.txt` (it installs the `groq` package).

The 3D viewer uses Three.js, downloaded once into `vendor/` during development — it's served locally, not fetched from a live CDN, so the demo doesn't need internet just to open (only AI features do).

## How crafting works under the hood

- **One shared sandbox** for everything you scan/type + every AI-generated idea: raw materials and crafted sub-assemblies are pooled, because your real materials genuinely are shared across whatever you choose to build. Switching which recipe is "active" just changes which recipe graph is live for merging and which holograms show — it doesn't reset your bench or inventory.
- **The offline Robot Arm example is isolated** from that shared pool (its own pretend inventory), so it's always available as a guaranteed, zero-dependency fallback demo path — rehearse it at least once.
- **Assembly steps are generated on demand** — not upfront for every idea in the catalog (expensive and slow), but only when you actually click Build on a specific recipe. The offline example skips this entirely (hardcoded steps, no AI call needed).

## Camera scan

Click **Scan Material** → camera opens → **Capture** → the photo is sent to a Groq vision model, which guesses a material name you can edit before adding it to Inventory. If the camera is unavailable (permissions, no device, bad lighting) or vision identification fails, it falls back to a plain "type it in" form automatically — tested and confirmed working in this build.

## Judgment calls made without asking (flag if you want these changed)

- **Rebuilt around your Fusion-360 description**: 3-panel layout, 2D/3D toggle, hologram previews, camera scan with AI vision + manual fallback (per your choice), on-demand step generation, broader recipe catalog.
- **3D is a simplified staging viewer, not parametric CAD** — orbit/zoom/pan camera, drag parts on a ground plane, proximity-based merge, wireframe→solid hologram ghosts. No real physics, snapping, or part geometry beyond colored boxes/icosahedrons — matches your "don't need a full parametric modeling tool" note.
- **Recipe catalog generates 6-10 ideas per call** (not 4) so there's a genuine "long list," mixing immediately-buildable and aspirational projects.
- **Two-phase AI calls**: idea catalog first (no steps), assembly steps only once you click Build on a specific recipe — faster, cheaper, and matches your "on the fly" ask.
- Found and fixed two real bugs while testing this build: a stale in-memory cache meant the offline idea's item names broke after clicking Reset (fixed — now recomputed every time), and the scan modal's manual-entry fallback had a leftover visible "Capture" button due to a CSS specificity issue with the `hidden` attribute (fixed with a standard `[hidden] { display: none !important; }` override).

## Known limitations

- Single-player, single-browser — progress lives in `localStorage`, not a real backend/database.
- 3D object geometry is a simple shape rule (box for raw materials, icosahedron for crafted sub-assemblies) with a text-sprite label, not real part models.
- The photo-upload step in the assembly guide just previews the image locally; nothing is uploaded or stored anywhere.
- AI-generated ideas and assembly steps aren't guaranteed physically sound — sanity-check before presenting them as real engineering advice.
- Camera scan needs a working webcam and browser permission; it was tested end-to-end via its manual-fallback path (this sandbox's browser blocks camera access), not via a live camera capture — worth a real test on your actual presenting device before the pitch.
