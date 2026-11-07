# CUBE — Pitch Script & Demo Plan

(TASKS.md #7 — pitch narrative. Not code; this is the talking track and live-demo plan for presenting `cube-mvp/`.)

## The one-liner

> **CUBE turns discarded materials into a playable engineering inventory. Scan what you have, combine parts to discover ideas, and follow an interactive assembly guide to build something real. It makes reuse easier, more creative, and more accessible.**

North star: **physical builds, not just digital crafting.** Everything in the demo exists to get someone from "pile of scrap" to "thing they actually made."

## The hook (30 seconds)

Open with the problem, not the product:

> "Everyone has a drawer of dead electronics, scrap wood, broken parts — stuff that's clearly *useful*, but you have no idea what to build with it, and no idea where to start. CUBE is a scrap-to-creation sandbox that scans what you have, tells you what you can build, and walks you through actually building it."

Don't lead with "it's an AI app" — lead with the drawer of junk everyone in the room already owns. The AI is how it works, not what it's for.

## Live demo script (~3 minutes)

Run this against the **real** app (`cube-mvp/`), not slides — it's interactive enough to be worth doing live. Rehearse the full path at least twice before presenting.

| Step | What you do | What you say |
|---|---|---|
| 1 | Click **Scan Material**, capture or type in 2-3 real items you brought (or use the ones already in your bag) | "I'm not going to pretend — here's actual stuff from my backpack." |
| 2 | Hit generate on **Buildable Now** | "CUBE looks at exactly what I have and proposes real projects — not a fixed catalog, it's reasoning about *my* materials." |
| 3 | Pick a recipe from the catalog on the right | "Every recipe shows red and green — what I have versus what I need. This one's mostly green already." |
| 4 | Switch to the **3D view**, drag two parts together to merge | "This isn't just a checklist — it's a sandbox. You physically combine parts, like a crafting game, except it maps to a real recipe graph." |
| 5 | Point at a hologram ghost in the 3D view | "That translucent part up there? That's what's still missing. It solidifies as you craft the real thing — so you always know what to build next." |
| 6 | Click **Build It** → assembly guide appears | "Once everything's green, CUBE writes the actual assembly steps on the fly — specific to what you just built, not a generic manual." |
| 7 | Check off steps, upload a photo, **Mark Build Complete** | "And you get a record of it — a photo, a completion badge, something to show you actually made it." |

**If anything about the live AI path hesitates, breaks, or the venue wifi is bad:** switch to the pinned **"Robot Arm (offline)"** recipe in the catalog instead. It needs zero network calls and runs the identical merge → hologram → build → assembly flow — nobody in the audience can tell the difference unless you say so. Always have this as your named fallback, never improvise one live.

## Why this, why now (differentiation)

- **Not a shopping list app.** It doesn't tell you to buy parts — it works with what's already in front of you.
- **Not a fixed tutorial library.** The recipes aren't pre-written for your exact materials; they're generated against your actual inventory, every time.
- **Makes the physical build the point.** Lots of "AI project idea" tools stop at a text description. CUBE's loop ends in an assembly guide and a completion record, not a suggestion.
- **Degrades gracefully.** No internet, no API key, bad lighting for the camera scan — there's always a path that still works. That's a deliberate reliability choice, not an accident (see the offline Robot Arm example).

## Audience framing (who's this for, if asked)

Three audiences from the original concept, worth having one line each ready:

- **Makers** — turn a scrap pile into a weekend project instead of a guilt pile.
- **Schools / makerspaces** — shared inventory, guided builds, a low-stakes way to teach assembly and design thinking.
- **Companies / sustainability teams** — standardize what gets reused instead of thrown out.

Keep this light in a 3-minute pitch — one sentence, don't build a slide for it unless asked.

## If judges ask...

- **"Is the AI actually doing anything, or is this scripted?"** → Show the materials you scanned aren't in any fixed list — type something unusual live and regenerate ideas in front of them.
- **"What happens with no internet?"** → Switch to the offline Robot Arm recipe, same UI, zero network calls.
- **"Is this safe? What stops it from suggesting something dangerous?"** → The idea-generation prompt explicitly excludes weapons, high-voltage wiring, hazardous chemicals, and anything needing professional tools/certification — mention this is enforced in the system prompt, not just a suggestion.
- **"What's not built yet?"** → Be honest: single-browser local storage (no shared team inventory yet), no deployed hosted version yet, 3D parts are simple shapes not real models. See `TASKS.md` for the active list — it's a feature that the roadmap is visible, not a weakness.

## Pre-demo checklist

- [ ] `cube-mvp/.env` has a real, working API key (not the placeholder) — test the AI idea generation at least once in the hour before presenting
- [ ] Run through the full live-demo script end to end at least twice
- [ ] Confirm the offline Robot Arm fallback path still works (it should need zero setup)
- [ ] Bring 2-3 real small objects to scan live — more convincing than typing in fake materials
- [ ] Know who's driving the laptop/keyboard during the demo vs. who's talking — decide this in advance, don't improvise on stage
- [ ] Charge the laptop; don't depend on venue wifi being fast (confirm the backend runs on `localhost`, not a hosted URL, unless TASKS.md #6 ships a stable one before showtime)

## Timing budget (if given a strict slot)

- Hook: 0:00–0:30
- Live demo: 0:30–3:30
- Differentiation / why-now: 3:30–4:00
- Close on the judge-ready line (repeat the one-liner) + ask for questions: 4:00–4:30

Cut the audience-framing section first if you're over time — the live demo is what sells it.
