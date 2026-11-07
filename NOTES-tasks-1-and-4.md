# Tasks 1 & 4: camera-scan test and recipe-quality pass

Commands below run from the repo root, matching `recipes/README.md` and `TASKS.md`. Code lives in `cube-mvp/`; this doc sits at the root next to `PITCH.md` and `DEPLOYMENT.md`.

**Status: code audit + fixes + test tooling are done. The two things that need real hardware / a real API key are NOT done.**
This was worked in a sandbox with no camera, no browser and no `ANTHROPIC_API_KEY`, so nothing below claims a live
camera capture or a real model output was observed.

Follow-up verification on 2026-11-07 ran all 11 scan-state tests, all 10 synthetic-camera browser checks, and the full 12-scenario stub quality harness. A visible-browser attempt reached the correct manual fallback but reported that no physical camera was available. The harness also needed an explicit UTF-8 report encoding on Windows; that is now fixed. Step-generation briefs now include the ordered recipe graph, closing the previously documented build-order gap.

## Not done (needs you)

| | What | How |
|---|---|---|
| Task 1 | Live camera + vision test on a real device | Checklist at the bottom. ~10 minutes. |
| Task 4 | Run the generator on real material lists and read the output | `python3 cube-mvp/tests/recipe_quality.py --steps`, then read `cube-mvp/tests/recipe_quality_report.md` and tick the verdict boxes. Before/after prompt comparison needs this run (git-stash the prompt change to get the "before"). |

## Task 1: camera scan

Verified here: (a) the scan state machine against a mocked camera/fetch in jsdom (`cd cube-mvp && npm i --no-save jsdom && node tests/scan_logic.test.js`, 11 tests); (b) the full flow in a real headless Chromium using its synthetic camera (`python3 cube-mvp/tests/scan_browser.py`: real `getUserMedia`, real frames, JPEG capture, downscale, retake, Esc/release, fallback). Neither is a physical webcam.
Run against the *old* `app.js` these tests fail 8 of 11; against the new code all pass.

Bugs found by reading the code and fixed (`app.js` scan section, `server.py` identify endpoint):

1. **Camera left on.** Closing the modal while the permission prompt was open let the late stream attach and never stop (camera light stays on).
2. **Dead "back to camera".** After a denied permission, "back" showed a blank video; Capture then uploaded a black frame. Now it re-requests the camera, and falls back to the manual form with a reason if it still fails.
3. **Double-click on Scan** opened two streams.
4. **Black-frame upload** if Capture was pressed before the video had frames. Now refused with "still warming up".
5. **Full-resolution upload.** Frames are now downscaled to 1024px longest side (a 4K webcam frame is multi-MB base64).
6. **No timeout / no unreachable-server handling.** 45s abort, and a readable message for "server not running".
7. **Late responses** from a closed or superseded scan could overwrite a newer one. Guarded with a session counter.
8. **Insecure context.** Visiting `http://<LAN IP>:8743` from a phone has no `navigator.mediaDevices`; the error was a raw `TypeError`. Now says to use localhost or https. (Relevant for demoing on a phone.)
9. Permission/not-found/in-use errors now have distinct messages; Enter confirms, Esc closes.
10. **Server crash path:** `_friendly_error` re-imported `anthropic` inside the error handler, so with the package missing the request thread died and the browser saw a dropped connection. README claims it "auto-installs"; no such code exists. Now returns a clear "pip install anthropic" message. (Also: oversized/odd bodies, non-JSON bodies, non-image data URLs now get 4xx instead of a stack trace; empty/refused model responses give a readable error.)

Not changed, worth knowing: `scanBtn`'s camera preview isn't mirrored (fine for a rear camera, slightly odd on a laptop webcam).

## Task 4: recipe quality

Method (static, since no key): read the prompts and schemas against how `app.js` consumes the output.
Findings, each grounded in the code, not in observed model output:

- **Prompt contradiction.** "More ambitious ones that would need a bit more material" conflicts with "never invent a material id". Ideas can only ask for *more units of the same materials*. Prompt now says so.
- **Schema bounds not enforced.** `minItems: 6` / `maxItems` aren't enforced by constrained decoding (only minItems 0/1 is), and may be rejected outright depending on SDK handling. They are now moved into the field description (`api_schema()`) and enforced server-side.
- **Validator trusted the model too much.** It didn't check: repeated merge pairs (`app.js` `findRecipe` uses `.find()` on the unordered pair, so a repeat makes the second result unreachable; `recipes/validate.py` already enforces this for the offline pack), result ids colliding with material ids or each other (silently overwrites an item), dead-end recipes, quantities, duplicate ids/titles, recipe/line-item counts. `uses_material_ids` is used by `app.js` (`rawIdsForIdea`) to decide which ids are raw inventory, so one omission by the model would mis-namespace a raw material and break that idea. It is now recomputed from the recipe graph.
- **Model text goes into `innerHTML`** in `app.js` (pitch, step text, item names). Server now strips markup from all model strings. (`app.js` itself still uses `innerHTML`; separate cleanup.)
- **Steps prompt asked for "numbered" steps** but the UI numbers them → likely "1. 1. Glue…". Prompt now forbids numbering and the server strips it.
- **Plausibility/safety gaps in the prompts:** no rule about broken parts ("Dead Nozzle" used as a working component), capabilities the parts can't provide (wifi, motors, light), salvaged lithium cells / PSUs / capacitors / microwave parts, load-bearing or safety items, or variety (six variants of one organizer). All added. Padding to 6 ideas when materials are scarce is now discouraged (server accepts fewer).
- **Steps phase was blind to the recipe graph.** `app.js` now sends an ordered, human-readable `recipe_graph` with each steps request, and the steps prompt explicitly follows that graph so results are not described before their inputs exist.

Tests: `python3 cube-mvp/tests/test_recipes.py` (16 offline tests for the validator, sanitizer, schema stripping, input checks).
Harness: `cube-mvp/tests/recipe_quality.py`: 12 scenarios built to stress different failure modes (hazardous parts, nearly-empty inventory, broken parts, etc.), heuristic flags, reviewer checkboxes.

Risk to watch on first real run: tighter prompts + stricter validation could lower the number of ideas that survive. The report prints returned vs. kept and every rejection reason so you can see if validation is too strict.

## Real-device camera checklist (Task 1)

On the laptop/phone you'll present from, with a real key in `.env`:
- [ ] Click Scan → permission prompt appears once; Allow → live video, no black/frozen frame.
- [ ] Capture a mug, a zip tie, a motor, a blurry/dark shot → name is usable; dark shot says "Not sure".
- [ ] Camera light turns off after Add, after Close, after Esc.
- [ ] Deny permission → manual form with a clear message; "Back" re-prompts.
- [ ] Block the camera in browser settings, other app holding camera → distinct messages.
- [ ] Stop the server mid-scan → "Couldn't reach the MakeShift server".
- [ ] Phone on LAN IP over http → expected "secure page" message (use localhost/https/tunnel to demo on a phone).
- [ ] Safari/iOS: video appears (needs `playsinline`, already set) and rear camera is chosen.
