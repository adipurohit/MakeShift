# AI recipe quality: real-model run, 2026-11-07

**Question:** Are the AI recipes any good? Until this run, every AI test used a stand-in server, so nobody knew.

**Method:** The 12 material lists in `cube-mvp/tests/recipe_quality.py` ran through the live site (adipurohit.com/makeshift), so through the real Groq model (`openai/gpt-oss-120b`) with the production prompts. The run produced 120 ideas plus step guides for 4 of them. Groq's free tier refused about half the first attempts with its own rate limit, so the run paced the remaining lists a minute apart. One reviewer (Claude) read every idea.

## Results

| | Before this change | After |
|---|---|---|
| Ideas the validator kept | 120 of 120 | 95 of 120 |
| Kept ideas with a known safety problem | 14 | 0 |
| Kept ideas claiming motion or light they can't produce | 9 | 0 |

### What the new checks reject (25 ideas)

| Problem | Count | Examples from the run |
|---|---|---|
| Uses a hazardous part, even as decoration | 11 | All 10 ideas for the "Tempting & hazardous" list: capacitor bookends, a transformer shelf, a PSU guard. Large capacitors can hold a dangerous charge. Also a photo frame backed with a broken phone screen. |
| Stepper motor "moves" with no driver or power | 5 | Stepper-Powered Lift, Dual-Motor Turntable, Two-Axis Gantry |
| Light claimed with no light source | 4 | Hanging Cardboard Tube Lantern, Bottle-Bottom Lamp Shade |
| Projectile or flame | 3 | Rubber Band Catapult, Bolt-Spring Launcher, Tin-Can Lantern "with a candle" |
| Glass shards | 1 | Screen Mosaic Wall Art ("cut the screen into small shards") |
| Broken part named as a working part | 1 | "Screen Frame" from a broken screen (a false positive: the screen is only structure) |

The prompt already forbade all of these. The model ignored the prompt, so the checks now run on every response in `server.py` and the Worker, with the same patterns.

### What still passes (95 ideas, one reviewer's read)

| Verdict | About | Examples |
|---|---|---|
| Plausible and useful | 55 | All 10 wood-offcut ideas (coasters, tool caddy, key holder), all 10 fabric ideas, umbrella canopy to shade sail, spring-hinge bookstand |
| Plausible but trivial | 25 | Rubber band pencil grip, binder clip bag fastener, spoke sculpture |
| Physically doubtful | 15 | Cork "stress ball" (cork doesn't squeeze), cardboard-tube gear wheel, kaleidoscope with no mirrors, bike chain "bracelet" |

The checks catch safety and false function claims. They can't catch "this won't work well" or "this is boring". Those still need human review, or a second model pass as judge.

### Step guides

All 4 step guides invented parts that weren't in the build: "set screw", "idler pulley", "base plate", "M3 screws", "thin wooden plank", "cardboard hinge". Cause: the step request never told the model which raw parts exist. The app now sends the exact `raw_materials` list, and the steps prompt names the invented parts as forbidden. **Not yet re-measured** after the fix.

### Other findings

- **Counts don't add up.** "Spoon-Clip Pair + Spoon-Clip Pair = Three-Spoon Rack". The prompt now asks for consistent counts. Counts in names, like "Coaster Set (4 coasters)", are stripped.
- **Free-tier quota is the real demo risk.** One idea refresh uses most of a minute's tokens. The Worker now caches ideas per inventory for 6 hours and retries once on a Groq rate limit. Pre-warm the demo inventory before judging (see PITCH.md).

## Rerun

With a Groq key on your machine:

```bash
export GROQ_API_KEY=gsk_...
python3 cube-mvp/tests/recipe_quality.py --steps
```

Without the key (it lives only in Cloudflare): open adipurohit.com/makeshift, open the browser console, paste `scripts/quality-in-browser.js`, and wait about 15 minutes. It paces calls a minute apart to stay inside the free tier.
