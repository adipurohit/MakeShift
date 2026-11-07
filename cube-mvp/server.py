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

MODEL = "claude-opus-5-5"

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
Given a list of raw materials someone has on hand, propose a broad CATALOG of distinct, physically
buildable projects that make creative use of what they have — a mix of projects they can fully build
right now, and more ambitious ones that would need a bit more material, so there's something to work
toward.

Hard rules:
- Every "a" / "b" in a recipe, and every "id" in final_requires, must be either one of the
  given material ids, or a result_id you defined in an earlier recipe in the SAME idea
  (recipes combine two inputs into one named result; a result can feed into a later recipe).
  Never invent a material id that wasn't provided.
- Each idea should use between 2 and 8 of the provided materials.
- Keep each idea to 2-6 recipes and 2-6 final_requires line items, with small quantities (1-3).
- Do NOT write assembly steps — those come later. Only the recipe graph and final requirements.
- result_short is a 2-3 letter uppercase abbreviation (for a UI icon).
- Projects must be safe for a general audience to physically build: no weapons, no mains/high-voltage
  wiring, no hazardous chemicals, nothing that requires professional tools or certification.
- Order ideas with the best material match / most immediately buildable first.
- Titles should be punchy and specific (not "Cool Gadget").
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
            "format": {"type": "json_schema", "schema": IDEA_SCHEMA},
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return validate_and_clean(data, materials)


def validate_and_clean(data, materials):
    material_ids = {m["id"] for m in materials}
    clean_ideas = []
    for idea in data.get("ideas", []):
        known_ids = set(material_ids)
        valid = True
        for r in idea.get("recipes", []):
            if r["a"] not in known_ids or r["b"] not in known_ids:
                valid = False
                break
            known_ids.add(r["result_id"])
        if not valid:
            continue
        for req in idea.get("final_requires", []):
            if req["id"] not in known_ids:
                valid = False
                break
        if not valid:
            continue
        if not idea.get("recipes") or not idea.get("final_requires"):
            continue
        clean_ideas.append(idea)
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
Given one specific project (its name, pitch, the sub-assemblies it's built from, and the final parts
list), write 4-9 short, concrete, numbered assembly steps in plain imperative language, in the order
a maker would actually do them. Reference the named parts naturally. Safe for a general audience: no
mains/high-voltage wiring, no hazardous chemicals, no professional-only tools or certification steps.
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
            "format": {"type": "json_schema", "schema": STEPS_SCHEMA},
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return data.get("assembly_steps", [])


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
3-6 word phrase suitable for an inventory list (e.g. "broken stepper motor", "cardboard tube",
"bundle of zip ties", "cracked phone screen"). Prefer naming what it's made of or its function if
the exact object is unclear. Always give your best guess rather than refusing, and set confidence
to "low" if you're genuinely unsure what it is.
"""

DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/.+-]+);base64,(?P<data>.+)$", re.DOTALL)


def identify_material(data_url):
    import anthropic

    m = DATA_URL_RE.match(data_url or "")
    if not m:
        raise ValueError("Image must be a base64 data URL.")
    media_type = m.group("mime")
    image_data = m.group("data")

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
            "format": {"type": "json_schema", "schema": IDENTIFY_SCHEMA},
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


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

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "bad_request", "message": "Invalid JSON body."})
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
        materials = [
            {"id": m.get("id", ""), "name": m.get("name", ""), "qty": int(m.get("qty", 0))}
            for m in materials
            if m.get("id") and m.get("name")
        ]
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
        import anthropic
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
