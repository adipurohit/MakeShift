#!/usr/bin/env python3
"""
CUBE backend: serves the static demo files and exposes the AI endpoints, so the
Anthropic API key never reaches the browser.

  POST /api/generate-ideas    materials -> a catalog of buildable project ideas (no steps yet)
  POST /api/generate-steps    one chosen idea -> assembly steps, generated on demand
  POST /api/identify-material photo -> a guessed material name (camera scan)

Run: python3 server.py   (reads ANTHROPIC_API_KEY from the environment or a local .env)
"""
import base64
import json
import os
import re
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = 8743
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

MODEL = "claude-opus-5-5"

MAX_BODY_BYTES = 8 * 1024 * 1024        # reject absurd request bodies
MAX_IMAGE_B64_CHARS = 6 * 1024 * 1024   # API image limit is 5 MB of raw bytes (~6.7M base64 chars)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def api_schema(schema):
    """Copy of a JSON schema that structured outputs will accept.

    Decoding-level enforcement only supports minItems of 0 or 1 and no maxItems, so those bounds are
    moved into the field description (the model still sees them) and are enforced server-side in
    validate_and_clean() instead.
    """
    if isinstance(schema, list):
        return [api_schema(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: api_schema(v) for k, v in schema.items()}
    hints = []
    if out.get("minItems", 0) > 1:
        hints.append(f"at least {out.pop('minItems')} items")
    if "maxItems" in out:
        hints.append(f"at most {out.pop('maxItems')} items")
    if hints:
        out["description"] = (out.get("description", "") + " Provide " + " and ".join(hints) + ".").strip()
    return out


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
            "minItems": 6,
            "maxItems": 10,
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

IDEA_SYSTEM_PROMPT = """You are the idea engine inside CUBE, a scrap-to-creation sandbox for makers.
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
- If the only way to make an idea interesting is to break one of these rules, drop the idea.

Quality:
- Give genuine variety: different functions and different material mixes, not six versions of one organizer.
- Titles are punchy and specific. The pitch is one or two sentences that say what it does and why it is
  satisfying, and it must match the recipes.
- Order ideas with the best material match / most immediately buildable first. Before ordering, count the
  raw units each idea needs against the quantities given.
- If the materials are too limited for a good idea, return fewer, honest ideas instead of padding.
"""


def generate_ideas(materials):
    import anthropic

    client = anthropic.Anthropic()
    materials_json = json.dumps(materials, indent=2)
    user_prompt = (
        "Materials on hand (id, name, quantity):\n"
        f"{materials_json}\n\n"
        "Propose a catalog of buildable project ideas using these materials, following the schema."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=IDEA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_config={
            "format": {"type": "json_schema", "schema": api_schema(IDEA_SCHEMA)},
        },
    )
    data = json.loads(first_text(response))
    return validate_and_clean(data, materials)


def first_text(response):
    """Text of the first text block, with a readable error for refusals / empty responses."""
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("The model declined this request.")
    for b in response.content:
        if b.type == "text" and b.text.strip():
            return b.text
    raise RuntimeError("The model returned an empty response. Try again.")


MAX_IDEAS = 10
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
    for n, r in enumerate(recipes_in, 1):
        if not isinstance(r, dict):
            problems.append(f"recipe {n} is not an object")
            continue
        a, b, rid = r.get("a"), r.get("b"), r.get("result_id")
        rname = clean_text(r.get("result_name"), 40)
        for side in (a, b):
            if side not in known:
                problems.append(f"recipe {n} uses unknown id {side!r}")
            elif side in results:
                used_results.add(side)
            else:
                used_raw.add(side)
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


def validate_and_clean(data, materials, rejected=None):
    """Keep only ideas that are structurally sound. `rejected` (a list) collects (title, problems)."""
    material_ids = {m["id"] for m in materials}
    clean_ideas = []
    seen_ids, seen_titles = set(), set()
    raw_ideas = data.get("ideas") if isinstance(data, dict) else None
    for raw in raw_ideas if isinstance(raw_ideas, list) else []:
        idea, problems = validate_idea(raw, material_ids)
        if idea is not None:
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

STEPS_SYSTEM_PROMPT = """You write physical assembly instructions for CUBE, a scrap-to-creation sandbox.
Given one project (name, pitch, the sub-assemblies it is built from, and the final parts list), write 4-9
short, concrete steps in plain imperative language, in the order a maker would really do them.

- Build the sub-assemblies first (each sub-assembly gets its own step), then combine them into the final
  project. Do not start with the finished object.
- Use only the parts named in the brief, plus ordinary hand tools and consumables (tape, glue, string,
  screws). Do not introduce new parts, electronics or materials. If a step cannot be done with those, leave
  it out rather than inventing something.
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
    import anthropic

    client = anthropic.Anthropic()
    user_prompt = (
        "Project:\n" + json.dumps(idea_brief, indent=2) + "\n\n"
        "Write the assembly steps, following the schema."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=STEPS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_config={
            "format": {"type": "json_schema", "schema": api_schema(STEPS_SCHEMA)},
        },
    )
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
        raise ValueError("Unsupported image type. Use JPEG, PNG, GIF or WebP.")
    if len(image_data) > MAX_IMAGE_B64_CHARS:
        raise ValueError("That photo is too large. Try again with a smaller capture.")

    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=IDENTIFY_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": "What is this?"},
            ],
        }],
        output_config={
            "format": {"type": "json_schema", "schema": api_schema(IDENTIFY_SCHEMA)},
        },
    )
    data = json.loads(first_text(response))
    name = clean_text(data.get("name"), 60) or "unclear item"
    confidence = data.get("confidence") if data.get("confidence") in ("low", "medium", "high") else "low"
    return {"name": name, "confidence": confidence}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR), **kwargs)

    def log_message(self, fmt, *args):
        print("[server]", fmt % args)

    def do_POST(self):
        routes = {
            "/api/generate-ideas": self._handle_generate_ideas,
            "/api/generate-steps": self._handle_generate_steps,
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

        if not os.environ.get("ANTHROPIC_API_KEY"):
            self._send_json(503, {
                "error": "no_api_key",
                "message": "No ANTHROPIC_API_KEY configured on the server. Set it in cube-mvp/.env and restart the server, or use the offline example idea instead.",
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
        materials = [m for m in materials if m["id"] and m["name"]]
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
        try:
            import anthropic
        except ImportError:
            return "The 'anthropic' Python package isn't installed. Run: pip install anthropic  (then restart the server)."
        if isinstance(e, anthropic.AuthenticationError):
            return "The API key was rejected. Check ANTHROPIC_API_KEY in cube-mvp/.env."
        if isinstance(e, anthropic.RateLimitError):
            return "Rate limited by the API. Wait a moment and try again."
        if isinstance(e, anthropic.APIConnectionError):
            return "Couldn't reach the Claude API. Check your internet connection."
        if isinstance(e, anthropic.APIStatusError):
            return f"API error ({e.status_code}): {e.message}"
        return f"Unexpected error: {e}"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"CUBE server on http://localhost:{PORT}  (ANTHROPIC_API_KEY {'found' if has_key else 'NOT found — AI features will be unavailable, offline example still works'})")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
