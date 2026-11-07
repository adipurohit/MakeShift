# MakeShift — Robot Arm demo (MVP)

"Turn what you have into what you need." Scrap-to-creation sandbox: turn broken 3D printers into a robot arm.

No build step, no install, no internet required. Three files: `index.html`, `style.css`, `app.js`.

## Run it

```bash
cd cube-mvp
python3 -m http.server 8743
```

Then open **http://localhost:8743** in a browser. (Plain `file://` double-click does *not* work — the browser blocks the page from loading `style.css`/`app.js` as local files, which is why this needs a tiny local server. Any static server works; Python's is just preinstalled on macOS.)

State (inventory, discovered recipes, badges, in-progress bench) is saved to the browser's `localStorage`, so progress survives a reload — but it's per-browser-profile, not shared across machines. If the demo laptop switches browsers or goes incognito, it starts fresh.

## The demo loop (~3 min)

1. **Inventory tab** — scavenged parts from broken 3D printers, manually confirmed counts. Note **Timing Belt only shows 1**, not 2 — that's intentional, see below.
2. **Merge Lab tab** — drag a part onto the bench, then drag a second part onto the first to try a merge. Five discoverable recipes:
   - Stepper Motor + Pulley → Drive Unit
   - Drive Unit + Timing Belt → **Motorized Joint**
   - Al. Extrusion + Smooth Rod → Rail
   - Rail + Linear Bearing → **Arm Segment**
   - Dead Nozzle + Zip Tie → **Gripper Claw** (the broken nozzle tips become the gripper's pincers — the "turn what you have into what you need" beat)
3. Craft 2 Motorized Joints — on the second one you'll come up **1 Timing Belt short**. Go back to the **Inventory tab** and hit **"Scan more parts"** — it finds one more belt (simulates confirming a second stripped printer). This is the deliberate RED→GREEN moment.
4. **Build Robot Arm tab** — shows the final recipe: 2 Motorized Joints, 2 Arm Segments, 1 Gripper Claw, Control Board, Power Supply, Limit Switch, each red/green against current inventory. Mouse-move over the exploded diagram tilts it (cheap stand-in for the "rotate exploded 3D view" feature). When everything's green, **Build Robot Arm** is enabled.
5. Click it → assembly guide modal: 7 numbered steps, check each off, upload a photo (any image), **Mark Build Complete** → confetti, badge, pitch line.
6. **Reset Demo** (top right) — click twice within ~4s to confirm — resets everything to starting inventory for the next run-through.

## Judgment calls made without asking (flag if you want these changed)

- **Timing Belt starts at 1, not 2** — deliberately short, so the demo has one real RED→GREEN beat instead of starting fully green. Change `belt: { ... start: 1 }` to `2` in `app.js` if you'd rather it start ready.
- **No CDN, no external fonts/libraries** — everything (including confetti) is hand-rolled vanilla JS so the demo can't break on bad venue WiFi.
- **Exploded view is a static labeled SVG with a mouse-tilt effect**, not a real 3D model — matches the doc's BUILD NOW scope (real 3D rotation/scan is listed as NEXT/LATER tier).
- **Drag-and-drop uses pointer events, not native HTML5 drag-and-drop** — more reliable across trackpads/touchscreens and avoids native-DnD quirks during a live demo.
- **AI substitution tip** is a single hardcoded suggestion (rubber bands for the missing belt), not a real AI call — demos the *feature* described in the doc without needing a real model integration in 12 hours.

## Known limitations (be aware, don't need to fix before pitching)

- If you reload the page with a half-finished merge on the Merge Lab bench, that in-progress state now persists correctly (fixed during testing) — but closing/reopening in a different browser or clearing site data loses all progress.
- There's no server/backend — this is a single-player, single-browser demo. Good enough for a pitch; would need real state sync for the "Teams" tier described in the doc.
- The file-photo-upload step accepts any image and just previews it locally — nothing is uploaded anywhere.

## If you want to extend before the pitch

- Swap the placeholder icon circles (`ST`, `PU`, etc. in `app.js`'s `ITEMS` object) for real photos of your actual scavenged parts — more convincing on stage than initials-in-a-circle.
- Add a real photo of your physical (if you built one) robot arm as the completion-screen image instead of the trophy emoji.
