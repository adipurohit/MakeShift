# MakeShift — Pitch and Live Demo Runbook

## Core story

**North star:** Turn what you have into what you need.

**Judge-ready pitch:** MakeShift turns discarded materials into a playable engineering inventory. Scan what you have, combine parts to discover ideas, and follow an interactive assembly guide to build something real.

**One-sentence version:** MakeShift is a scrap-to-creation workspace that recognizes the parts people already have, proposes useful builds, and guides them from loose materials to a finished project.

Lead with the familiar drawer of dead electronics, scrap wood, and broken parts—not with “this is an AI app.” The physical build is the point; AI is how MakeShift helps a maker get there.

The live demo should prove one idea, not tour every feature: a pile of parts from two broken 3D printers can become a working robot-arm plan. The offline Robot Arm recipe is the stage path because it is deterministic and does not need Wi-Fi or an API key. Describe the generative catalog and camera vision after the successful build instead of making the live result depend on either service.

## 3:30 live pitch

| Time | Screen/action | Speaker script |
| --- | --- | --- |
| 0:00–0:20 | Hold up a stepper motor, timing belt, and dead nozzle. Keep the app visible behind them. | “These look like leftovers from broken 3D printers. In most workshops they become clutter or e-waste. But they are still motors, rails, bearings, and control electronics. The problem is not that we have nothing—it is that we cannot see what these parts could become.” |
| 0:20–0:40 | Put the parts down. Point to the MakeShift tagline. | “MakeShift’s north star is simple: **turn what you have into what you need**. It converts discarded parts into a playable engineering inventory, then gives you a path from inventory to a real build.” |
| 0:40–0:58 | Select **Robot Arm** from the Recipe Catalog. Point to the available-parts palette, holograms, and red requirements. | “Here is a guaranteed offline example built from two stripped printers. MakeShift maps the available parts into a recipe graph. Red requirements show what is still missing, and these holograms show the subassemblies we are working toward.” |
| 0:58–1:45 | In 2D, merge parts. First demonstrate `Stepper Motor + Pulley → Drive Unit`, then complete the remaining robot-arm subassemblies. Narrate only the first and most meaningful merges. | “Instead of asking someone to begin with a blank CAD file, MakeShift makes fabrication exploratory. A stepper motor and pulley become a drive unit. Add a timing belt and that becomes a motorized joint. The same pattern turns rails and bearings into arm segments—and even dead nozzle tips and zip ties into a gripper claw.” |
| 1:45–2:02 | Briefly switch to 3D and orbit once. Point to the now-solid holograms and green requirements; return to 2D only if needed. | “The 2D workspace makes the logic easy to learn; the 3D workspace lets a maker stage and inspect the same build spatially. As parts are crafted, the holograms become solid and the build moves from red to green.” |
| 2:02–2:42 | Click **Build It**. Check the assembly steps and upload the prepared progress photo. Click **Mark Build Complete**. | “Once the recipe is ready, MakeShift turns the design into an ordered assembly guide. The builder checks off physical progress and records a photo, so the workflow ends with something made—not just something generated.” |
| 2:42–2:55 | Let the completion badge and confetti land. Stop interacting with the UI. | “That is the loop: see value in what you have, discover what it can become, and build it.” |
| 2:55–3:22 | Keep the completed screen visible. Describe, do not live-demo, camera scanning and AI ideas. | “The Robot Arm path works entirely offline. With connectivity, a maker can photograph an unfamiliar part, let vision suggest an editable inventory name, and generate a broader catalog of immediately buildable and aspirational projects. Assembly instructions are generated only for the project they choose, which keeps the experience focused and efficient.” |
| 3:22–3:30 | Hold up the physical parts again. | “MakeShift does not start by asking what you want to buy. It starts by asking what you already have—and helps you turn it into what you need.” |

## What is live versus described

### Live—the proof

- Select the pinned offline Robot Arm recipe.
- Show the available-parts palette, red/green requirements, and hologram target state.
- Demonstrate at least one understandable merge in 2D.
- Complete the deterministic recipe, open its seven-step guide, attach the prepared photo, and reach the completion badge.
- Switch to 3D only for one short orbit after the parts are ready. The story matters more than a long camera-controls demonstration.

### Describe—the expansion

- Camera capture and Claude vision identification.
- Manual entry when camera access or vision fails.
- AI-generated catalog of 6–10 build ideas based on the user's inventory.
- On-demand AI assembly steps for a selected generated idea.
- Future real geometry, parametric constraints, shared team inventories, and safety/feasibility validation.

Do not make the judged demo depend on Wi-Fi, an Anthropic API key, a live camera permission prompt, or a newly generated recipe.

## Physical props and files

Bring clean, safe parts that map directly to the on-screen recipe:

- One stepper motor.
- One pulley and timing belt.
- One short aluminum extrusion or smooth rod.
- One dead nozzle and one zip tie for the memorable “scrap becomes a gripper” beat.
- Optional: a control board, clearly disconnected from power.
- One preselected progress photo saved locally as `cube-progress.jpg` in an easy-to-find folder.

Avoid exposed mains wiring, sharp unprotected edges, leaking batteries, resin, solvents, or anything that creates a safety distraction.

## Stage preflight

### Repository and browser

- Ensure `task/fix-offline-demo` is merged. The offline recipe otherwise starts with only one timing belt and cannot be completed; that branch also fixes duplicate bench-token IDs after reload.
- Include the mobile/accessibility and smoke-test branches if they have passed review, but neither is required for the desktop stage path.
- Start from a clean checkout and run `python3 cube-mvp/server.py` from the repository root.
- Open `http://localhost:8743` in the presentation browser.
- Use the offline Robot Arm recipe even if an API key is configured.
- Set browser zoom to 100%, close unrelated tabs, disable notifications, and prevent the laptop from sleeping.
- Click **Reset Demo** twice immediately before presenting.
- Confirm that the palette contains two Timing Belts, the Robot Arm can reach all-green requirements, and the prepared photo can be selected.
- Keep a second browser tab open at the app URL as a recovery option, but remember that both tabs share local storage.

### Thirty-second recovery plan

If the live state becomes confused:

1. Say, “The important part is the transformation graph; I’m resetting the deterministic demo state.”
2. Click **Reset Demo** twice.
3. Select Robot Arm again and demonstrate only `Stepper Motor + Pulley → Drive Unit`.
4. Move directly to the product explanation and close with the core loop. Do not spend stage time debugging.

If 3D rendering fails, stay in 2D. If the photo picker stalls, close the assembly modal and explain the last verification step without claiming the build was completed. If the server stops, restart it from the prepared terminal and refresh the page.

## Rehearsal checklist

Run the full offline path at least twice on the actual presentation laptop:

- [ ] Reset produces a clean deterministic state.
- [ ] Robot Arm appears in both Buildable Now and the Recipe Catalog.
- [ ] Two Drive Units and two Motorized Joints can be crafted.
- [ ] Two Rails and two Arm Segments can be crafted.
- [ ] One Gripper Claw can be crafted.
- [ ] All six final requirement lines turn green.
- [ ] **Build It** enables and opens seven assembly steps.
- [ ] The prepared photo previews successfully.
- [ ] Checking all steps enables **Mark Build Complete**.
- [ ] Completion badge and confetti appear.
- [ ] The run finishes in under 3:30 without using the network.
- [ ] A second presenter can execute the recovery plan without coaching.

### Rehearsal record

- **2026-11-07, automated local + hosted rehearsal (`main` hosted at `b945f83`):** The complete Robot Arm interaction passed from recipe selection through all nine crafting merges, all-green requirements, seven assembly steps, photo preview, completion badge, 3D canvas, and mobile-width check with no console errors. The interaction path took 6.3 seconds locally and 6.3 seconds on the public Render deployment before narration. This verifies the technical stage path; presenters still need to rehearse the spoken 3:30 script with physical props on the presentation laptop.
- **2026-11-07, `add-cube-mvp-demo` at `f42bc8d`:** The app loaded locally, the offline Robot Arm recipe selected correctly, and its palette, holograms, and six requirement lines rendered as documented. The base branch supplied only one Timing Belt, confirming that the build cannot reach completion there. Complete the full timed rehearsal after `task/fix-offline-demo` is merged; that branch changes the starting quantity to two and fixes persisted bench-token IDs.

## Differentiation and audience

- **Not a shopping list:** MakeShift begins with parts the user already owns.
- **Not a fixed tutorial library:** Connected mode generates recipes against the actual inventory.
- **Not ideas that end as text:** The core loop ends in assembly guidance and a completion record.
- **Designed to degrade gracefully:** Manual inventory entry and the offline Robot Arm keep the core experience usable when camera access, AI, or venue Wi-Fi fails.

The first audiences are makers turning a “guilt pile” into a weekend project, schools and makerspaces teaching assembly and design thinking, and sustainability teams trying to standardize reuse instead of disposal.

## Likely judge questions

**What is AI doing here?**

Vision suggests an editable inventory label from a photo. The idea engine turns a user's material IDs and quantities into validated recipe graphs, and assembly steps are generated only after a project is selected. The offline Robot Arm is intentionally pinned so the core experience remains demonstrable without an API call.

**Is this really CAD?**

This MVP is a CAD-inspired planning and staging workspace, not a parametric mechanical solver. It proves the interaction loop—inventory, recipe graph, spatial staging, requirements, and assembly guidance. Parametric constraints and part-accurate models are later engineering work.

**How do you prevent unsafe or impossible recommendations?**

The current prompts prohibit weapons, hazardous chemicals, mains or high-voltage work, and professional-only procedures. That is a first guardrail, not a certification system. A production version needs deterministic safety rules, feasibility checks, confidence labels, and human review for higher-risk builds.

**Who is it for?**

The first users are makerspaces, school labs, repair cafés, and hardware teams that accumulate useful parts but lack a fast way to catalog and repurpose them.

**What comes next?**

Part-specific geometry, constraint-aware fit checks, shared inventories, build history, sourcing for genuinely missing parts, and evaluation data that scores generated recipes for feasibility, safety, cost, and waste diverted.

## Honest MVP boundaries

- The app is single-player and stores progress in the browser's local storage.
- The 3D viewer uses simplified primitive geometry rather than exact scanned models.
- Generated ideas and instructions are not engineering certification.
- Photo evidence is previewed locally and is not uploaded or retained.
- The live camera path still needs verification on the actual presentation device.

These boundaries should be stated plainly if asked. The pitch is strongest when it proves the core interaction and treats the remaining work as a credible roadmap rather than pretending the prototype already solves fabrication end to end.
