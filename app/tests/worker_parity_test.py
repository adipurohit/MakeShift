#!/usr/bin/env python3
"""
The Cloudflare Worker (worker/ai.js) must treat AI output exactly like app/server.py.

1. worker/ai-config.json matches what scripts/export-ai-config.py generates from server.py,
   so both back ends send identical prompts and schemas.
2. 500 generated model responses (valid, broken, and hostile) go through server.py's
   validate_and_clean / clean_steps / clean_text and the Worker's JS ports. Outputs must match.

Usage: python3 app/tests/worker_parity_test.py      (needs Node 18+)
Exit code 0 = in sync, 1 = drift found.
"""
import importlib.util
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
import server  # noqa: E402

spec = importlib.util.spec_from_file_location("export_ai_config", ROOT / "scripts" / "export-ai-config.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

MATS = [
    {"id": "m_stepper_motor", "name": "Stepper Motor", "qty": 2},
    {"id": "m_pulley", "name": "Pulley", "qty": 2},
    {"id": "m_zip_tie", "name": "Zip Tie", "qty": 6},
    {"id": "m_cardboard_tube", "name": "Cardboard Tube", "qty": 3},
    {"id": "m_jar", "name": "Glass Jar", "qty": 1},
    {"id": "m_cap", "name": "Large Capacitor", "qty": 2},
]
IDS = [m["id"] for m in MATS]
TEXTS = ["Hand-Crank Winch", "  Desk   Lamp ", "<b>Bold</b> Planter", "Tray <script>x</script>", "", "Fan\x07 Stand",
         "A" * 80, "Jar Light", "jar light", "Robot Hand!!", None, 7,
         "Rubber Band Catapult", "Motorized Spinner", "Night Light Jar", "Stepper Turntable", "Candle Holder",
         "Coaster Set (4 coasters)"]
SHORTS = ["cu", "WINCHX", "", "a", "AB", "x y", None, "Q1", 12]


def gen_idea(rng):
    results = []
    recipes = []
    for _ in range(rng.choice([0, 1, 2, 3, 3, 4, 7])):
        pool = IDS + results + ["ghost_part", None]
        a, b = rng.choice(pool), rng.choice(pool)
        rid = rng.choice([f"r{len(results)}", f"r{len(results)}", "m_jar", "bad id!", "x" * 41, None, f"r{len(results)}"])
        r = {"a": a, "b": b, "result_id": rid, "result_name": rng.choice(TEXTS), "result_short": rng.choice(SHORTS)}
        if rng.random() < 0.05:
            r = "not an object"
        elif rng.random() < 0.05:
            del r["result_short"]
        recipes.append(r)
        if isinstance(rid, str):
            results.append(rid)
    finals = []
    for _ in range(rng.choice([0, 1, 2, 2, 3, 7])):
        finals.append({"id": rng.choice(IDS + results + ["ghost_part"]), "qty": rng.choice([1, 1, 2, 3, 0, 6, -1, "2", True])})
    if results and rng.random() < 0.6:
        finals.append({"id": results[-1], "qty": 1})
    idea = {"title": rng.choice(TEXTS), "pitch": rng.choice(TEXTS[:4] + ["A tabletop winch."]),
            "uses_material_ids": [], "recipes": recipes, "final_requires": finals}
    if rng.random() < 0.8:
        idea["id"] = rng.choice(["Hand Crank!", "lamp", "", None, "___x___", "jar-light"])
    return idea


def gen_valid_idea(rng):
    """A well-formed idea, sometimes with one small flaw, to cover the success path."""
    raw = rng.sample(IDS, rng.choice([2, 3, 4]))
    recipes, prev = [], None
    for i in range(rng.choice([1, 2, 3])):
        a = prev if prev else raw[0]
        b = raw[(i + 1) % len(raw)]
        rid = f"part_{i}"
        recipes.append({"a": a, "b": b, "result_id": rid, "result_name": rng.choice(["Crank Unit", "Base Plate", "Arm <b>Link</b>", "Drive"]),
                        "result_short": rng.choice(["CU", "bp", "", "TOOLONG", "A1"])})
        prev = rid
    finals = [{"id": prev, "qty": rng.choice([1, 1, 2, 3])}]
    if rng.random() < 0.7:
        finals.append({"id": raw[-1], "qty": rng.choice([1, 2])})
    idea = {"id": rng.choice(["Crank Kit", "lamp", "lamp", "", "Desk Lamp!"]), "title": rng.choice(["Crank Kit", "Desk Lamp", "desk lamp", "Bench Hook"]),
            "pitch": "Turns scrap into a handy tool.", "uses_material_ids": ["wrong"], "recipes": recipes, "final_requires": finals}
    flaw = rng.random()
    if flaw < 0.08:
        idea["final_requires"].append(dict(idea["final_requires"][0]))      # listed twice
    elif flaw < 0.16:
        idea["recipes"].append({"a": raw[0], "b": raw[1], "result_id": "orphan", "result_name": "Orphan", "result_short": "OR"})
    elif flaw < 0.22:
        idea["final_requires"][0]["qty"] = 9
    return idea


def build_cases():
    rng = random.Random(4207)
    idea_cases = []
    for _ in range(500):
        ideas = [(gen_valid_idea if rng.random() < 0.6 else gen_idea)(rng) for _ in range(rng.choice([1, 2, 3, 12]))]
        idea_cases.append({"ideas": ideas} if rng.random() > 0.02 else {"ideas": "nope"})
    steps_cases = [
        ["1. Glue the tube.", "Step 2: Tie the pulley", "  - Check it spins", "", "<i>Done</i>", "3) Test gently"],
        ["• Mount the jar", "** Bold step", 5, None] + [f"Step {i}" for i in range(12)],
        "not a list",
    ]
    text_cases = [(t, n) for t in TEXTS + ["  a\tb\nc  ", "<<x>>", "naïve café ✓ ok"] for n in (5, 60)]
    material_cases = [
        [{"id": "m_a", "name": "Thing", "qty": 3}, {"id": "m_b", "name": "Other", "qty": "-2"},
         {"id": "m_c", "name": "Third"}, {"id": "", "name": "x"}, {"id": 5, "name": "Num"}, "junk",
         {"id": "m_d", "name": "<b>Bold</b>", "qty": True}, {"id": "m_e", "name": "Float", "qty": "2.5"}],
    ]
    source_cases = [{"suggestions": [
        {"material": "Cardboard", "places": ["<b>Reuse center</b>", "Reuse center", "Frame shop"],
         "salvage_tip": "Use a <script>bad</script> clean box.", "safety_note": "Ask first."},
        {"material": "Invented", "places": ["Nowhere"], "salvage_tip": "", "safety_note": ""},
    ]}, None, {"suggestions": "nope"}]
    source_material_cases = [[
        {"name": " Cardboard ", "needed": 2, "have": "1", "missing": 1},
        {"name": "<b>Motor</b>", "needed": 1000, "have": -1, "missing": True},
        {"name": "", "needed": 1}, "junk",
    ]]
    return idea_cases, steps_cases, text_cases, material_cases, source_cases, source_material_cases


def python_side(idea_cases, steps_cases, text_cases, source_cases):
    return {
        "ideas": [server.validate_and_clean(c, MATS) for c in idea_cases],
        "steps": [server.clean_steps(c) for c in steps_cases],
        "text": [server.clean_text(t, n) for t, n in text_cases],
        "short": [server.make_short(n) for n in ["Crank Unit", "winch", "", "3D Gear Box"]],
        "sources": [server.clean_source_suggestions(c, ["Cardboard", "Motor"]) for c in source_cases],
    }


def python_materials(materials):
    # the same comprehension server.py's _handle_generate_ideas runs
    out = [
        {"id": server.clean_text(m.get("id"), 60), "name": server.clean_text(m.get("name"), 60),
         "qty": max(0, int(m.get("qty") or 0)) if str(m.get("qty", "")).lstrip("-").isdigit() else 1}
        for m in materials if isinstance(m, dict) and m.get("id") and m.get("name")
    ]
    return [m for m in out if m["id"] and m["name"] and m["qty"] > 0]


NODE = r"""
import fs from "node:fs";
const ai = await import(process.argv[2]);
const c = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = {
  ideas: c.idea_cases.map((d) => ai.validateAndClean(d, c.mats)),
  steps: c.steps_cases.map((s) => ai.cleanSteps(s)),
  text: c.text_cases.map(([t, n]) => ai.cleanText(t, n)),
  short: ["Crank Unit", "winch", "", "3D Gear Box"].map((n) => ai.makeShort(n)),
  materials: c.material_cases.map((m) => ai.cleanMaterials(m)),
  sources: c.source_cases.map((d) => ai.cleanSourceSuggestions(d, c.source_names)),
  source_materials: c.source_material_cases.map((m) => ai.cleanSourceMaterials(m)),
};
process.stdout.write(JSON.stringify(out));
"""


def main():
    ok = True
    current = (ROOT / "worker" / "ai-config.json").read_text()
    if current != export.render():
        print("[FAIL] worker/ai-config.json is out of sync with server.py. Run: python3 scripts/export-ai-config.py")
        ok = False
    else:
        print("[PASS] worker/ai-config.json matches server.py prompts, schemas, and limits")

    app_js = (ROOT / "app" / "app.js").read_text()
    want = "const HAZARDOUS_PART = new RegExp(" + json.dumps(server.PLAUSIBILITY["hazardous_part"]) + ', "i");'
    if want in app_js:
        print("[PASS] app.js hazardous-part warning matches server.py")
    else:
        ok = False
        print("[FAIL] app.js HAZARDOUS_PART is out of sync with server.py PLAUSIBILITY['hazardous_part']")

    idea_cases, steps_cases, text_cases, material_cases, source_cases, source_material_cases = build_cases()
    py = python_side(idea_cases, steps_cases, text_cases, source_cases)
    py["materials"] = [python_materials(m) for m in material_cases]
    py["source_materials"] = [server.clean_source_materials(m) for m in source_material_cases]

    with tempfile.TemporaryDirectory() as tmp:
        cases = Path(tmp) / "cases.json"
        cases.write_text(json.dumps({"idea_cases": idea_cases, "steps_cases": steps_cases, "text_cases": text_cases,
                                     "material_cases": material_cases, "source_cases": source_cases,
                                     "source_material_cases": source_material_cases,
                                     "source_names": ["Cardboard", "Motor"], "mats": MATS}), encoding="utf-8")
        script = Path(tmp) / "run.mjs"
        script.write_text(NODE, encoding="utf-8")
        run = subprocess.run(["node", str(script), (ROOT / "worker" / "ai.js").as_uri(), str(cases)],
                             capture_output=True, text=True, encoding="utf-8")
    if run.returncode:
        print("[FAIL] node run failed:\n" + run.stderr)
        return 1
    js = json.loads(run.stdout)

    kept = sum(len(x) for x in py["ideas"])
    for key in ("ideas", "steps", "text", "short", "materials", "sources", "source_materials"):
        mismatches = [i for i, (a, b) in enumerate(zip(py[key], js[key])) if a != b]
        if len(py[key]) != len(js[key]) or mismatches:
            ok = False
            i = mismatches[0] if mismatches else 0
            print(f"[FAIL] {key}: {len(mismatches)} mismatch(es). First at case {i}:\n  python: {json.dumps(py[key][i])[:400]}\n  worker: {json.dumps(js[key][i])[:400]}")
        else:
            extra = f" ({kept} valid ideas kept across {len(idea_cases)} responses)" if key == "ideas" else ""
            print(f"[PASS] {key}: {len(py[key])} cases identical{extra}")
    print("OK" if ok else "DRIFT FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
