#!/usr/bin/env python3
"""
MakeShift backend: serves the static demo files and exposes the AI endpoints, so the
Gemini API key never reaches the browser.

  POST /api/generate-ideas    materials -> a catalog of buildable project ideas (no steps yet)
  POST /api/generate-steps    one chosen idea -> assembly steps, generated on demand
  POST /api/suggest-sources   needed materials -> safe places to look for them
  POST /api/identify-material photo -> a guessed material name (camera scan)

Run: python3 server.py   (reads GEMINI_API_KEY from the environment or a local .env)
"""
import base64
import json
import os
import re
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = int(os.environ.get("PORT", "8743"))
DIR = Path(__file__).parent

# ---- tiny .env loader (no python-dotenv dependency) ----
def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

load_dotenv(DIR / ".env")

# ---- Gemini (Google AI Studio) ----
# Override either model from .env without touching code. Keep model IDs current:
# https://ai.google.dev/gemini-api/docs/models
TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", TEXT_MODEL)
# Gemini 3 Flash thinks at "medium" by default, which took 100+ s per request on the live site.
# "low" is the floor for gemini-3.8-flash. Set GEMINI_THINKING_LEVEL=off to send no thinking setting.
THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "low")
# When the main model is overloaded, rate limited or not found, try these next, in order. Comma-separated, e.g.
# "gemini-3.6-flash,gemini-3.1-flash-lite". Gemini quotas are per project AND per model, so each extra model in the
# list is extra capacity. "off" disables fallbacks. (Gemini answered "503: high demand" during testing.)
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.6-flash")


def normalize_model(name):
    """Accept "models/gemini-x" and stray spaces, so a value pasted from AI Studio still works."""
    name = str(name or "").strip()
    return name[len("models/"):] if name.lower().startswith("models/") else name


def parse_model_list(value):
    return [m for m in (normalize_model(x) for x in str(value or "").split(",")) if m and m.lower() != "off"]


def model_chain(model=None):
    """Models to try in order: the requested/main model, then each fallback (same rule as worker/ai.js)."""
    primary = normalize_model(model or TEXT_MODEL) or normalize_model("gemini-3.8-flash")
    return list(dict.fromkeys([primary, *parse_model_list(FALLBACK_MODEL)]))


def gemini_client():
    from google import genai  # imported lazily so offline mode works without the SDK
    # Pass the key explicitly; this avoids GOOGLE_API_KEY taking precedence unexpectedly.
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def chat_json(system, user, name, schema, max_tokens, model=None):
    """Call Gemini's generateContent API and request a schema-constrained JSON response."""
    from google.genai import types

    contents = user
    if isinstance(user, list):
        # Convert our compact internal image/text parts into the current google-genai Part API.
        parts = []
        for part in user:
            if part.get("type") == "text":
                parts.append(types.Part.from_text(text=part["text"]))
            elif part.get("type") == "image":
                parts.append(types.Part.from_bytes(
                    data=base64.b64decode(part["data"]), mime_type=part["mime_type"]
                ))
        contents = [types.Content(role="user", parts=parts)]

    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
        response_json_schema=api_schema(schema),
        **thinking_config(types),
    )
    chain = model_chain(model)
    for i, m in enumerate(chain):
        try:
            return gemini_client().models.generate_content(model=m, contents=contents, config=config)
        except Exception as e:
            # Same rule as the Worker: an overloaded, rate-limited or unknown model hands over to the next one.
            if getattr(e, "code", None) not in (429, 503, 404) or i == len(chain) - 1:
                raise
            print(f"[ai] model {m} unavailable ({getattr(e, 'code', '?')}); trying {chain[i + 1]}", file=sys.stderr)


def thinking_config(types):
    """thinking_config for the SDK, or nothing when it's off or the installed SDK predates thinking_level."""
    if not THINKING_LEVEL or THINKING_LEVEL == "off":
        return {}
    try:
        return {"thinking_config": types.ThinkingConfig(thinking_level=THINKING_LEVEL)}
    except Exception:
        return {}

MAX_BODY_BYTES = 8 * 1024 * 1024        # reject absurd request bodies
MAX_IMAGE_B64_CHARS = 6 * 1024 * 1024   # keep camera captures comfortably below request limits
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def api_schema(schema):
    """Return a JSON-schema copy for Gemini structured output."""
    if isinstance(schema, list):
        return [api_schema(item) for item in schema]
    if isinstance(schema, dict):
        return {key: api_schema(value) for key, value in schema.items()}
    return schema


_TAG_RE = re.compile(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_text(value, limit):
    """The front end renders these strings with innerHTML, so strip markup characters here."""
    if not isinstance(value, str):
        return ""
    value = re.sub(r"<[^>]*>", "", value)  # whole tags first, then any stray < or >
    return re.sub(r"\s+", " ", _TAG_RE.sub("", value)).strip()[:limit]


def make_short(name):
    letters = re.findall(r"[A-Za-z0-9]+", name)
    if len(letters) >= 2:
        return (letters[0][0] + letters[1][0]).upper()
    return (letters[0][:2] if letters else "??").upper()

# ---------------------------------------------------------------
# Phase 1: idea catalog (no assembly steps — those are generated
# on demand in phase 2, once the user actually picks a recipe).
# ---------------------------------------------------------------
IDEA_SCHEMA = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "minItems": 1,
            "maxItems": 14,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "pitch": {"type": "string"},
                    "uses_material_ids": {"type": "array", "items": {"type": "string"}},
                    "recipes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "string"},
                                "b": {"type": "string"},
                                "result_id": {"type": "string"},
                                "result_name": {"type": "string"},
                                "result_short": {"type": "string"},
                            },
                            "required": ["a", "b", "result_id", "result_name", "result_short"],
                            "additionalProperties": False,
                        },
                    },
                    "final_requires": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "qty": {"type": "integer"},
                            },
                            "required": ["id", "qty"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "title", "pitch", "uses_material_ids", "recipes", "final_requires"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["ideas"],
    "additionalProperties": False,
}

IDEA_SYSTEM_PROMPT = """You are the idea engine inside MakeShift, a scrap-to-creation sandbox for makers.
Given the raw materials someone has on hand, propose a CATALOG of distinct projects a person could
really build from them using ordinary hand tools (scissors, craft knife, screwdriver, pliers) and common
consumables (tape, glue, string, screws). Those tools and consumables are ALWAYS assumed to be available;
never list them as materials. Mix projects they can build right now with some that need a larger quantity
of the same materials, so there is something to work toward.

How the data works:
- A recipe merges exactly TWO inputs into ONE result, consuming one unit of each input. If final_requires
  asks for qty 2 of a crafted item, that item must be crafted twice (so its inputs are consumed twice).
- An input ("a" / "b") or a final_requires "id" must be a given material id, or a result_id defined by an
  EARLIER recipe in the SAME idea. Never invent a raw material id. Because you cannot invent materials,
  an "ambitious" idea can only be one that needs more units of the same materials than the person has.
- result_id: short snake_case, unique within the idea, and never equal to any given material id.
  result_name is the user-facing name. result_short is 2-3 uppercase letters.
- Every result_id must be used: it must feed a later recipe or appear in final_requires. No dead-end recipes.
- No two recipes in one idea may merge the same pair of inputs (order does not matter).
- Each idea uses 2-8 of the given materials, has 2-6 recipes and 2-6 final_requires lines, with quantities 1-3.
- Do NOT write assembly steps; only the recipe graph and final requirements. No HTML or markdown in any string.

Physical plausibility (this is where most bad ideas come from):
- Every merge must be something a person can physically do (glue, tie, tape, screw, slot, wrap, stack) and
  the result must honestly be the thing you name. Do not name a merge after a capability the parts do not give
  you ("battery + cardboard = power source" is not a recipe).
- Respect condition words. Parts described as broken, dead, cracked, jammed, stripped, etc. may be used for
  structure, weight, shape or decoration, never as working electrical, optical or mechanical components.
- Do not promise functions the materials cannot deliver: no Wi-Fi, sensors, motors-that-run, solar power or
  lighting unless the given materials include a working version of that part and the idea only wires/mounts it
  at hobby-kit level. Prefer honest, achievable functions: holders, stands, organizers, hand-powered
  mechanisms, linkages, toys, tools, planters, display pieces.
- Scale must make sense: the size, strength and number of the parts must be able to produce the result.
- The a/b pair in a recipe should be a natural pairing, not an arbitrary one.

Safety (general audience, possibly children nearby):
- No weapons or launchers, nothing that fires, pressurizes, burns or heats; no mains or high-voltage wiring;
  no opening or reusing power supplies, microwave/CRT/flash-camera parts or large capacitors.
- No damaged, swollen or salvaged lithium batteries; no hazardous chemicals, fuels or solvents.
- Nothing a person's safety depends on: no ladders, climbing or weight-bearing seats, helmets or protective
  gear, child-restraint or medical items, locks or alarms. No sharp blades or exposed spinning parts on
  anything meant for kids.
- No candles, flames or anything that throws, launches or fires objects (no catapults, slingshots, launchers).
- If the only way to make an idea interesting is to break one of these rules, drop the idea.

Power and motion (the most common mistake):
- A motor only runs if the materials include a power source (battery, power bank, USB cable, adapter). A
  stepper motor also needs a driver or control board. Without those, use a motor only as a hand-turned part,
  a weight or a display piece, and never call the build powered, motorized or automatic.
- Something only lights up if the materials include a light source (LED, bulb, working lamp).

Quality:
- Aim for 10-14 ideas. Give genuine variety: different functions and different material mixes, not ten
  versions of one organizer.
- Most ideas should chain at least two merges, so the build has real sub-assemblies, not one merge and done.
- Titles and result names never include counts or parentheses. Counts must add up: merging two "pair" items
  makes something that holds 4, not 3.
- Titles are punchy and specific. The pitch is one or two sentences that say what it does and why it is
  satisfying, and it must match the recipes.
- Order ideas with the best material match / most immediately buildable first. Before ordering, count the
  raw units each idea needs against the quantities given.
- The user message says how many ideas to aim for. If the materials are too limited, return fewer, honest
  ideas instead of padding with trivial ones (a pencil stuck in a rubber band is not a project).
"""


def raw_ideas(data):
    ideas = data.get("ideas") if isinstance(data, dict) else None
    return ideas if isinstance(ideas, list) else []


def generate_ideas(materials):
    materials_json = json.dumps(materials, indent=2)
    target = idea_target(materials)
    user_prompt = (
        "Materials on hand (id, name, quantity):\n"
        f"{materials_json}\n\n"
        f"Propose a catalog of about {target} buildable project ideas using these materials, following the schema."
    )

    response = chat_json(IDEA_SYSTEM_PROMPT, user_prompt, "ideas", IDEA_SCHEMA, 6144)
    first = raw_ideas(json.loads(first_text(response)))
    ideas = validate_and_clean({"ideas": first}, materials)
    if len(ideas) >= target:
        return ideas

    # Validation drops weak ideas, so ask once more for different ones to reach the target.
    taken = "; ".join(i["title"] for i in ideas) or "none yet"
    topup_prompt = (
        user_prompt + "\n\nThese ideas are already in the catalog: " + taken + ". Propose "
        f"{target - len(ideas) + 2} or more DIFFERENT ideas, with different titles and functions."
    )
    try:
        response = chat_json(IDEA_SYSTEM_PROMPT, topup_prompt, "ideas", IDEA_SCHEMA, 6144)
        second = raw_ideas(json.loads(first_text(response)))
    except Exception:
        return ideas  # keep the first batch if the top-up call fails
    return validate_and_clean({"ideas": first + second}, materials)


def first_text(response):
    """Text of Gemini's response, with a readable error for truncated / empty responses."""
    candidates = getattr(response, "candidates", None) or []
    if candidates and str(getattr(candidates[0], "finish_reason", "")).upper().endswith("MAX_TOKENS"):
        raise RuntimeError("The model ran out of room before finishing. Try again.")
    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise RuntimeError("The model returned an empty response. Try again.")
    return text


MIN_IDEAS = 10  # target for a full inventory: below the target, generate_ideas() makes one top-up call
IDEAS_PER_PART = 2  # a short list gets a smaller target, so the model doesn't pad it with trivial ideas


def idea_target(materials):
    """How many ideas to ask for: 10 for a full inventory, 2 per distinct part + 1 for a short one."""
    return max(1, min(MIN_IDEAS, IDEAS_PER_PART * len(materials) + 1))

MAX_IDEAS = 14
MAX_RECIPES = 6
MAX_FINAL = 6
MAX_QTY = 5   # prompt asks for 1-3; allow some slack before rejecting


def validate_idea(idea, material_ids):
    """Returns (cleaned_idea, problems). cleaned_idea is None when problems is non-empty."""
    problems = []
    if not isinstance(idea, dict):
        return None, ["not an object"]

    title = clean_text(idea.get("title"), 60)
    pitch = clean_text(idea.get("pitch"), 280)
    if not title:
        problems.append("missing title")
    if not pitch:
        problems.append("missing pitch")

    recipes_in = idea.get("recipes") or []
    final_in = idea.get("final_requires") or []
    if not recipes_in:
        problems.append("no recipes")
    if not final_in:
        problems.append("no final_requires")
    if len(recipes_in) > MAX_RECIPES:
        problems.append(f"{len(recipes_in)} recipes (max {MAX_RECIPES})")
    if len(final_in) > MAX_FINAL:
        problems.append(f"{len(final_in)} final_requires lines (max {MAX_FINAL})")
    if problems:
        return None, problems

    known = set(material_ids)
    results = {}          # result_id -> result_name (in definition order)
    used_results = set()
    used_raw = set()
    recipes = []
    seen_pairs = set()
    for n, r in enumerate(recipes_in, 1):
        if not isinstance(r, dict):
            problems.append(f"recipe {n} is not an object")
            continue
        a, b, rid = r.get("a"), r.get("b"), r.get("result_id")
        rname = clean_text(re.sub(r"\s*\([^)]*\)", "", r.get("result_name") or "") if isinstance(r.get("result_name"), str) else None, 40)
        for side in (a, b):
            if side not in known:
                problems.append(f"recipe {n} uses unknown id {side!r}")
            elif side in results:
                used_results.add(side)
            else:
                used_raw.add(side)
        # app.js findRecipe() matches the unordered pair with .find(), so a repeated pair makes the
        # second result unreachable and the idea unbuildable (recipes/validate.py enforces the same).
        pair = frozenset((a, b))
        if pair in seen_pairs:
            problems.append(f"recipe {n} repeats the pair {a!r} + {b!r}")
            continue
        seen_pairs.add(pair)
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,40}", rid or ""):
            problems.append(f"recipe {n} has an invalid result_id {rid!r}")
            continue
        if rid in known:
            problems.append(f"recipe {n} result_id {rid!r} collides with an existing id")
            continue
        if not rname:
            problems.append(f"recipe {n} has no result_name")
            continue
        short = re.sub(r"[^A-Z0-9]", "", str(r.get("result_short", "")).upper())
        if not 2 <= len(short) <= 3:
            short = make_short(rname)
        known.add(rid)
        results[rid] = rname
        recipes.append({"a": a, "b": b, "result_id": rid, "result_name": rname, "result_short": short})

    finals = []
    seen_final = set()
    for n, f in enumerate(final_in, 1):
        fid = f.get("id") if isinstance(f, dict) else None
        qty = f.get("qty") if isinstance(f, dict) else None
        if fid not in known:
            problems.append(f"final_requires {n} uses unknown id {fid!r}")
            continue
        if fid in seen_final:
            problems.append(f"final_requires lists {fid!r} twice")
            continue
        if not isinstance(qty, int) or isinstance(qty, bool) or not 1 <= qty <= MAX_QTY:
            problems.append(f"final_requires {n} has qty {qty!r} (must be 1-{MAX_QTY})")
            continue
        seen_final.add(fid)
        if fid in results:
            used_results.add(fid)
        else:
            used_raw.add(fid)
        finals.append({"id": fid, "qty": qty})

    orphans = [rid for rid in results if rid not in used_results]
    if orphans:
        problems.append("dead-end recipe result(s): " + ", ".join(orphans))
    if not used_raw:
        problems.append("uses no raw materials")
    if len(used_raw) > 8:
        problems.append(f"uses {len(used_raw)} raw materials (max 8)")
    if problems:
        return None, problems

    idea_id = re.sub(r"[^a-z0-9_]+", "_", str(idea.get("id", "")).lower()).strip("_")[:40] or re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
    # uses_material_ids is recomputed from the recipe graph: the front end uses it to decide which
    # ids are raw inventory, so trusting the model's own list can silently break an idea.
    return {
        "id": idea_id,
        "title": title,
        "pitch": pitch,
        "uses_material_ids": sorted(used_raw),
        "recipes": recipes,
        "final_requires": finals,
    }, []


# ---------------------------------------------------------------
# Plausibility and safety checks on top of the structural ones. Written after reading real
# gpt-oss-120b output: it proposed catapults and candle lanterns despite the prompt, "stepper-powered"
# builds with no power source or driver, and lamps with no light source. The Worker uses the same
# patterns (exported to worker/ai-config.json), so both back ends reject the same ideas.
# ---------------------------------------------------------------
PLAUSIBILITY = {
    # anything that throws, fires, burns or heats is out, whatever the prompt said
    "hazard": r"\b(catapult|trebuchet|launcher|sling ?shot|crossbow|blowgun|blaster|gun|cannon|weapon|dart|spear|candle|flame|fire|burn|torch|heater|boil|smoke|lighter|explos|firework|taser|stun|mains|high[- ]?voltage|shard)",
    # parts no idea may use at all, even as a weight or a shelf: they can shock, burn or cut
    "hazardous_part": r"microwave|capacitor|swollen|lithium|\bcrt\b|transformer|power supply unit|\bpsu\b|car battery|mains|broken glass|cracked glass|glass shard|(broken|cracked|shattered) (phone |tablet |laptop )?screen",
    # claims of powered motion need a power source among the parts used
    # (balloon-, rubber-band- and hand-powered are fine; only electric power needs a source)
    "motion_claim": r"\b(motori[sz]ed|motor[- ]?driven|electric|automatic|(stepper|motor|electric|battery|usb|solar)[- ]?powered|self[- ]?(spinning|moving|winding))",
    "power_source": r"battery|batteries|power ?bank|usb|adapter|charger|solar|power supply|psu",
    # a stepper motor only moves with a driver or control board
    "stepper": r"stepper",
    "stepper_motion": r"\b(powered|motori[sz]ed|driven|drive[sn]?|turntable|lift|winds?|winding|rotat|spin|actuat|moves?|moving)",
    "controller": r"board|driver|controller|arduino|esp32|raspberry|microcontroller",
    # light needs a light source
    "light_claim": r"\b(lamp|lantern|night ?light|glow|illuminat|lights? up)",
    "light_source": r"\bled|bulb|lamp|light|flashlight|glow|solar",
    # broken parts can be structure, never the working part
    "broken": r"\b(broken|dead|cracked|swollen|rusty|jammed|stripped|burnt|blown)\b",
    "functional": r"\b(motor|drive|pump|light|lamp|sensor|power|generator|engine|circuit|charger|speaker|screen|display)\b",
    # Added after the live Gemini run (docs/recipe-quality.md): ideas that passed every check above but
    # would hurt someone. Hot items on parts that melt, scrap that bears a person's weight or swings
    # overhead, solder near food, scrap pretending to be a lock or alarm, and controls for shop machines.
    "hot_use": r"\b(trivet|hot ?pads?|pot ?holders?|hot (pan|pot|dish|plate)s?|oven|stove|kettle|iron rest|heat[- ]?(proof|resistant))",
    "melts": r"rubber|elastic|inner ?tube|plastic|foam|vinyl|nylon|\bbands?\b|bottle|straw|tape",
    "body_load": r"\b(fitness|exercise|workout|resistance band|gym|pull[- ]?ups?|swings?\b|climbing|harness|ladder|step ?stool)",
    "overhead": r"\b(overhead|ceiling|pot ?rack|pan ?rack|(pot|pan|cookware) (hanger|rack)|hanging (pot|pan|cookware))",
    "food_use": r"\b(mugs?|cups?|coasters?|plates?|bowls?|cutting board|utensils?|food|snacks?|drinks?|lunch)\b",
    "leaded_part": r"circuit ?board|\bpcb\b|motherboard|solder|\blead\b",
    "security": r"\b(locks?|locking|security|alarms?|intruder|burglar|baby ?gate|child[- ]?(proof|safe)|gate latch|door alert)",
    "machinery": r"\b(machinery|power tools?|table saw|drill press|lathe|grinder|foot pedal|treadle)",
}
_P = {k: re.compile(v, re.I) for k, v in PLAUSIBILITY.items()}


def plausibility_problems(idea, names):
    """Problems that make a structurally valid idea unsafe or physically dishonest. `names` maps id -> name."""
    used_raw = [names.get(i, "") for i in idea["uses_material_ids"]]
    parts = " ".join(used_raw)
    text = " ".join([idea["title"], idea["pitch"]] + [r["result_name"] for r in idea["recipes"]])
    problems = []
    for name in used_raw:
        if _P["hazardous_part"].search(name):
            problems.append(f"uses a hazardous part: {name}")
    if _P["hazard"].search(text):
        problems.append("hazard: " + _P["hazard"].search(text).group(0))
    if _P["motion_claim"].search(text) and not _P["power_source"].search(parts):
        problems.append("claims powered motion with no power source")
    if _P["stepper"].search(parts) and _P["stepper_motion"].search(text) and not (
            _P["controller"].search(parts) and _P["power_source"].search(parts)):
        problems.append("stepper motion with no driver and power")
    if _P["light_claim"].search(text) and not _P["light_source"].search(parts):
        problems.append("claims light with no light source")
    if _P["hot_use"].search(text) and _P["melts"].search(parts):
        problems.append("hot items on parts that melt")
    for key, why in (("body_load", "bears a person's weight or force"), ("overhead", "hangs weight overhead"),
                     ("security", "stands in for a lock or alarm"), ("machinery", "controls shop machinery")):
        if _P[key].search(text):
            problems.append(f"{why}: {_P[key].search(text).group(0)}")
    if _P["food_use"].search(text) and _P["leaded_part"].search(parts):
        problems.append("circuit board or solder near food or drink")
    for r in idea["recipes"]:
        inputs = [names.get(r["a"], ""), names.get(r["b"], "")]
        if any(_P["broken"].search(n) for n in inputs) and _P["functional"].search(r["result_name"]):
            problems.append(f"broken part used as working {r['result_name']}")
    return problems


def validate_and_clean(data, materials, rejected=None):
    """Keep only ideas that are structurally sound. `rejected` (a list) collects (title, problems)."""
    material_ids = {m["id"] for m in materials}
    clean_ideas = []
    seen_ids, seen_titles = set(), set()
    raw_ideas = data.get("ideas") if isinstance(data, dict) else None
    for raw in raw_ideas if isinstance(raw_ideas, list) else []:
        idea, problems = validate_idea(raw, material_ids)
        if idea is not None:
            names = {m["id"]: m["name"] for m in materials}
            names.update({r["result_id"]: r["result_name"] for r in idea["recipes"]})
            problems = plausibility_problems(idea, names)
        if idea is not None and not problems:
            if idea["title"].casefold() in seen_titles:
                problems = ["duplicate title"]
            else:
                base, k = idea["id"], 2
                while idea["id"] in seen_ids:
                    idea["id"] = f"{base}_{k}"
                    k += 1
        if problems:
            if rejected is not None:
                rejected.append((clean_text(raw.get("title"), 60) if isinstance(raw, dict) else "?", problems))
            continue
        seen_ids.add(idea["id"])
        seen_titles.add(idea["title"].casefold())
        clean_ideas.append(idea)
        if len(clean_ideas) >= MAX_IDEAS:
            break
    return clean_ideas


# ---------------------------------------------------------------
# Phase 2: assembly steps for one chosen idea, generated on demand.
# ---------------------------------------------------------------
STEPS_SCHEMA = {
    "type": "object",
    "properties": {
        "assembly_steps": {
            "type": "array",
            "minItems": 4,
            "maxItems": 9,
            "items": {"type": "string"},
        }
    },
    "required": ["assembly_steps"],
    "additionalProperties": False,
}

STEPS_SYSTEM_PROMPT = """You write physical assembly instructions for MakeShift, a scrap-to-creation sandbox.
Given one project (name, pitch, its ordered recipe graph, sub-assemblies, and final parts list), write 4-9
short, concrete steps in plain imperative language, in the order a maker would really do them.

- Follow the ordered recipe graph: each `a + b -> result` merge must happen only after both inputs exist.
  Build the sub-assemblies first (each merge gets its own step), then combine them into the final project.
  Do not start with the finished object or describe a result before its inputs have been joined.
- Use only the parts listed in the brief (raw_materials, sub_assemblies, final_parts), plus ordinary hand tools
  and consumables (tape, glue, string, screws). Never mention a part that is not listed: no base plates,
  brackets, planks, dowels, set screws, idler pulleys or frames unless the brief lists them. If a step cannot be
  done with the listed parts, leave it out rather than inventing something.
- Say how two parts are joined (glue, tie, tape, screw, slot) and what to check (alignment, square, firm
  grip). Where a part is broken or sharp, say to handle it carefully or blunt/cover the edge.
- Be honest about what the result does. End with a gentle test or fit check, never a claim that it
  definitely works.
- Safe for a general audience: no mains or high-voltage wiring, no heat, flame, pressure, hazardous
  chemicals or salvaged lithium batteries, no professional-only tools. If the brief seems to require one of
  those, replace it with a safe alternative or skip that step and say so in one step.
- Each step is one plain sentence or two. Do NOT number the steps or add "Step 1:" (the app numbers them),
  and do not use markdown or HTML.
"""


def generate_steps(idea_brief):
    user_prompt = (
        "Project:\n" + json.dumps(idea_brief, indent=2) + "\n\n"
        "Write the assembly steps, following the schema."
    )
    response = chat_json(STEPS_SYSTEM_PROMPT, user_prompt, "steps", STEPS_SCHEMA, 3072)
    data = json.loads(first_text(response))
    return clean_steps(data.get("assembly_steps", []))


_NUMBERING_RE = re.compile(r"^\s*(?:step\s*)?\d+\s*[.):\-]\s*", re.I)


def clean_steps(steps):
    """Strip model-added numbering (the UI numbers steps) and markup; cap at 9 steps."""
    out = []
    for step in steps if isinstance(steps, list) else []:
        text = clean_text(step, 400)
        text = _NUMBERING_RE.sub("", text).lstrip("*-• ").strip()
        if text:
            out.append(text)
    return out[:9]


# ---------------------------------------------------------------
# Material sourcing: safe, realistic places to find needed parts.
# ---------------------------------------------------------------
SOURCES_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "material": {"type": "string"},
                    "places": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                    "salvage_tip": {"type": "string"},
                    "safety_note": {"type": "string"},
                },
                "required": ["material", "places", "salvage_tip", "safety_note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}

SOURCES_SYSTEM_PROMPT = """You are the material-sourcing guide inside MakeShift, a scrap-to-creation app.
For each requested material, suggest realistic, low-cost places a maker could look locally. Prefer reuse:
their own recycling, repair shops, community reuse centers, e-waste programs, thrift stores, maker spaces,
schools or businesses that may give away clean offcuts. Hardware or craft stores are a last resort.

- Lead with donor objects: the specific discarded things that usually contain this exact part, and where those
  turn up. Good: "Dead flatbed scanner (stepper motor plus smooth rod), e-waste drop-off". Bad: "Thrift store".
- Give place categories, not invented business names, addresses, live inventory, prices or availability claims.
- Copy each input material name exactly into the corresponding `material` field.
- Keep each place to a short phrase and give 2-4 distinct options where possible.
- The salvage tip says how to get the part out of the donor object (which screws, which connector) and what
  condition to check (rust, cracked housing, stiff bearings).
- The app already reminds people to ask permission, once, at the top. Leave safety_note empty unless this part
  has its own risk, like springs under tension, sharp sheet metal, or glass. Never recommend trespassing, taking
  from private bins, unsafe roadside scavenging, or opening mains power supplies, microwaves, CRTs, swollen
  batteries, pressurized containers, or hazardous equipment.
- Use the supplied project and quantities for context. No markdown or HTML in any string.
"""


def clean_source_suggestions(data, requested_names):
    """Sanitize source suggestions and keep only materials the caller requested."""
    allowed = {name.casefold(): name for name in requested_names}
    out = []
    rows = data.get("suggestions", []) if isinstance(data, dict) else []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        raw_name = clean_text(row.get("material"), 60)
        canonical = allowed.get(raw_name.casefold())
        if not canonical:
            continue
        places = []
        for place in row.get("places", []) if isinstance(row.get("places"), list) else []:
            place = clean_text(place, 100)
            if place and place.casefold() not in {p.casefold() for p in places}:
                places.append(place)
            if len(places) >= 4:
                break
        tip = clean_text(row.get("salvage_tip"), 240)
        safety = clean_text(row.get("safety_note"), 180)
        if places:
            out.append({
                "material": canonical,
                "places": places,
                "salvage_tip": tip,
                "safety_note": safety,
            })
        if len(out) >= 12:
            break
    return out


def generate_source_suggestions(project, materials):
    brief = {"project": clean_text(project, 80), "materials": materials}
    response = chat_json(
        SOURCES_SYSTEM_PROMPT,
        "Suggest safe places to find these materials:\n" + json.dumps(brief, indent=2),
        "sources", SOURCES_SCHEMA, 4096,
    )
    data = json.loads(first_text(response))
    return clean_source_suggestions(data, [m["name"] for m in materials])


def clean_source_materials(incoming):
    """Normalize the sourcing request identically in Python and the Worker."""
    if not isinstance(incoming, list):
        return []
    materials = []
    for material in incoming[:12]:
        if not isinstance(material, dict):
            continue
        name = clean_text(material.get("name"), 60)
        if not name:
            continue

        def safe_qty(field):
            value = material.get(field, 0)
            return min(99, max(0, int(value))) if str(value).isdigit() else 0

        materials.append({
            "name": name,
            "needed": safe_qty("needed"),
            "have": safe_qty("have"),
            "missing": safe_qty("missing"),
        })
    return materials


# ---------------------------------------------------------------
# Camera scan: identify a material from a photo.
# ---------------------------------------------------------------
IDENTIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["name", "confidence"],
    "additionalProperties": False,
}

IDENTIFY_SYSTEM_PROMPT = """You help identify scrap materials and parts for a maker inventory app.
Look at the photo and name the single most prominent physical object or material in it, as a short
2-5 word phrase suitable for an inventory list (e.g. "broken stepper motor", "cardboard tube",
"bundle of zip ties", "cracked phone screen"). Name the object itself, not the surface it sits on, and not a
person's hand or face. If several objects are in frame, pick the one nearest the center. Prefer naming what
it is made of or its function if the exact object is unclear. Describe visible condition only when obvious
(broken, rusty, cracked). Always give your best guess rather than refusing. If the image is dark, blurry,
blank or you cannot tell what the object is, use the name "unclear item" and confidence "low". Set
confidence to "low" whenever you are genuinely unsure.
"""

DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/.+-]+);base64,(?P<data>.+)$", re.DOTALL)


def identify_material(data_url):
    m = DATA_URL_RE.match(data_url if isinstance(data_url, str) else "")
    if not m:
        raise ValueError("Image must be a base64 data URL.")
    media_type = m.group("mime").lower()
    image_data = m.group("data")
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Unsupported image type. Use JPEG, PNG, WebP, HEIC or HEIF.")
    if len(image_data) > MAX_IMAGE_B64_CHARS:
        raise ValueError("That photo is too large. Try again with a smaller capture.")

    response = chat_json(
        IDENTIFY_SYSTEM_PROMPT,
        [
            {"type": "text", "text": "What is this?"},
            {"type": "image", "data": image_data, "mime_type": media_type},
        ],
        "material", IDENTIFY_SCHEMA, 512, model=VISION_MODEL,
    )
    data = json.loads(first_text(response))
    name = clean_text(data.get("name"), 60) or "unclear item"
    confidence = data.get("confidence") if data.get("confidence") in ("low", "medium", "high") else "low"
    return {"name": name, "confidence": confidence}


# One canonical public URL. On Render (which sets RENDER=true on every service) the old
# makeshift-cube-demo.onrender.com copy redirects every request to the Cloudflare site, so a judge can't
# land on a copy with no AI and a cold start. CANONICAL_URL overrides the target; set it empty to serve.
CANONICAL_URL = os.environ.get(
    "CANONICAL_URL", "https://adipurohit.com/makeshift/" if os.environ.get("RENDER") else "").rstrip("/")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR), **kwargs)

    def log_message(self, fmt, *args):
        print("[server]", fmt % args)

    def _redirect_to_canonical(self):
        if self.path == "/healthz":  # host health checks get a plain 200, never the redirect
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return True
        if not CANONICAL_URL:
            return False
        # 308 keeps the method, so a stray POST to /api/... lands on the same endpoint there
        self.send_response(308 if self.command == "POST" else 301)
        self.send_header("Location", CANONICAL_URL + self.path)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def do_GET(self):
        if not self._redirect_to_canonical():
            super().do_GET()

    def do_HEAD(self):
        if not self._redirect_to_canonical():
            super().do_HEAD()

    def do_POST(self):
        if self._redirect_to_canonical():
            return
        routes = {
            "/api/generate-ideas": self._handle_generate_ideas,
            "/api/generate-steps": self._handle_generate_steps,
            "/api/suggest-sources": self._handle_suggest_sources,
            "/api/identify-material": self._handle_identify_material,
        }
        handler = routes.get(self.path)
        if not handler:
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if length < 0:
            self._send_json(400, {"error": "bad_request", "message": "Bad Content-Length."})
            return
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "too_large", "message": "Request is too large."})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "bad_request", "message": "Invalid JSON body."})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"error": "bad_request", "message": "Expected a JSON object."})
            return

        if not os.environ.get("GEMINI_API_KEY"):
            # Sourcing has a useful client-side category fallback. Return a
            # quiet capability signal instead of logging a failed resource in
            # the browser console; the other routes still require AI.
            if self.path == "/api/suggest-sources":
                self._send_json(200, {"suggestions": [], "fallback": True})
                return
            self._send_json(503, {
                "error": "no_api_key",
                "message": "No GEMINI_API_KEY configured on the server. Set it in app/.env and restart the server, or use the offline example idea instead.",
            })
            return

        handler(body)

    def _handle_generate_ideas(self, body):
        materials = body.get("materials", [])
        if not isinstance(materials, list):
            materials = []
        materials = [
            {"id": clean_text(m.get("id"), 60), "name": clean_text(m.get("name"), 60), "qty": max(0, int(m.get("qty") or 0)) if str(m.get("qty", "")).lstrip("-").isdigit() else 1}
            for m in materials
            if isinstance(m, dict) and m.get("id") and m.get("name")
        ]
        materials = [m for m in materials if m["id"] and m["name"] and m["qty"] > 0]  # only parts the user has
        if not materials:
            self._send_json(400, {"error": "no_materials", "message": "Add at least one material first."})
            return
        try:
            ideas = generate_ideas(materials)
        except Exception as e:
            self._send_json(502, {"error": "generation_failed", "message": self._friendly_error(e)})
            return
        if not ideas:
            self._send_json(502, {
                "error": "no_valid_ideas",
                "message": "The model's response didn't validate cleanly. Try again, or use the offline example idea.",
            })
            return
        self._send_json(200, {"ideas": ideas})

    def _handle_generate_steps(self, body):
        idea_brief = body.get("idea")
        if not idea_brief or not isinstance(idea_brief, dict):
            self._send_json(400, {"error": "bad_request", "message": "Missing idea details."})
            return
        try:
            steps = generate_steps(idea_brief)
        except Exception as e:
            self._send_json(502, {"error": "generation_failed", "message": self._friendly_error(e)})
            return
        if not steps:
            self._send_json(502, {"error": "no_steps", "message": "Couldn't generate assembly steps. Try again."})
            return
        self._send_json(200, {"assembly_steps": steps})

    def _handle_suggest_sources(self, body):
        project = clean_text(body.get("project"), 80)
        materials = clean_source_materials(body.get("materials", []))
        if not materials:
            self._send_json(400, {"error": "no_materials", "message": "No needed materials were provided."})
            return
        try:
            suggestions = generate_source_suggestions(project, materials)
        except Exception as e:
            self._send_json(502, {"error": "generation_failed", "message": self._friendly_error(e)})
            return
        if not suggestions:
            self._send_json(502, {"error": "no_suggestions", "message": "Couldn't generate sourcing suggestions. Try again."})
            return
        self._send_json(200, {"suggestions": suggestions})

    def _handle_identify_material(self, body):
        image = body.get("image")
        if not image:
            self._send_json(400, {"error": "bad_request", "message": "No image provided."})
            return
        try:
            result = identify_material(image)
        except ValueError as e:
            self._send_json(400, {"error": "bad_image", "message": str(e)})
            return
        except Exception as e:
            self._send_json(502, {"error": "generation_failed", "message": self._friendly_error(e)})
            return
        self._send_json(200, result)

    def _friendly_error(self, e):
        if isinstance(e, ImportError):
            return "The 'google-genai' Python package isn't installed. Run: pip install -r requirements.txt (then restart the server)."
        code = getattr(e, "code", None) or getattr(e, "status_code", None)
        detail = str(getattr(e, "message", None) or e)
        if callable(code):
            try:
                code = code()
            except Exception:
                code = None
        if code == 429:
            return "Rate limited by the Gemini API. Wait a moment and try again."
        if code in (401, 403) or (code == 400 and "api key" in detail.lower()):
            return "The API key was rejected. Check GEMINI_API_KEY in app/.env."
        if code == 404:
            return f"Gemini model not found ({detail}). Set GEMINI_TEXT_MODEL or GEMINI_VISION_MODEL to a current model."
        if isinstance(code, int):
            return f"Gemini API error ({code}): {detail}"
        if any(word in type(e).__name__.lower() for word in ("connect", "timeout", "network")):
            return "Couldn't reach the Gemini API. Check your internet connection."
        return f"Gemini request failed: {detail}"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    print(f"MakeShift server on http://localhost:{PORT}  (GEMINI_API_KEY {'found' if has_key else 'NOT found — AI features will be unavailable, offline example still works'})")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
