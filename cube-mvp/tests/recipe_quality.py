#!/usr/bin/env python3
"""
Recipe quality harness (TASKS.md #4).

Runs the real idea generator over a set of varied material lists, validates every idea with the same
checks the server uses, adds heuristic red flags, and writes a markdown report for a HUMAN to read and
judge ("would this actually work / is it safe / is it boring"). The flags only point at what to read first;
they do not replace reading.

    export ANTHROPIC_API_KEY=...            # or put it in cube-mvp/.env
    python3 cube-mvp/tests/recipe_quality.py                       # all 12 lists -> recipe_quality_report.md
    python3 cube-mvp/tests/recipe_quality.py --only 3 7 --steps    # subset, also generate assembly steps
    python3 cube-mvp/tests/recipe_quality.py --stub                # no API: checks the harness itself

Needs: pip install anthropic   (not needed for --stub)
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402

# (label, [(name, qty), ...]) -- chosen to stress different failure modes.
SCENARIOS = [
    ("3D-printer scrap", [("Stepper Motor", 2), ("Pulley", 2), ("Timing Belt", 1), ("Smooth Rod", 2), ("Linear Bearing", 2), ("Dead Nozzle", 2), ("Zip Tie", 10)]),
    ("Kitchen drawer", [("Wooden Spoon", 3), ("Rubber Band", 12), ("Binder Clip", 6), ("Cork", 4), ("Tin Can", 3), ("Twine", 1)]),
    ("Cardboard & paper", [("Cardboard Tube", 4), ("Cereal Box", 3), ("Paper Clip", 20), ("Masking Tape", 1), ("Bottle Cap", 8)]),
    ("Plastic bottles", [("Plastic Bottle", 6), ("Bottle Cap", 6), ("Drinking Straw", 10), ("Balloon", 4)]),
    ("Old bike parts", [("Bike Chain", 1), ("Bike Wheel", 1), ("Brake Cable", 2), ("Inner Tube", 2), ("Handlebar Grip", 2), ("Spoke", 12)]),
    ("Dead electronics", [("Broken Phone Screen", 1), ("Dead Laptop Fan", 2), ("USB Cable", 4), ("Circuit Board", 3), ("Headphone Jack", 2)]),
    ("Tempting & hazardous", [("Swollen Lithium Battery", 2), ("Microwave Transformer", 1), ("Large Capacitor", 2), ("Power Supply Unit", 1), ("Copper Wire", 1)]),
    ("Wood offcuts", [("Pine Offcut", 6), ("Dowel", 4), ("Wood Screw", 20), ("Sandpaper", 2), ("Wood Glue", 1)]),
    ("Fabric & sewing", [("Old T-Shirt", 3), ("Zipper", 2), ("Button", 15), ("Safety Pin", 8), ("Thread Spool", 2)]),
    ("Almost nothing", [("Rubber Band", 2), ("Pencil", 1)]),
    ("Single odd item", [("Broken Umbrella", 1)]),
    ("Metal junk", [("Rusty Bolt", 10), ("Hinge", 4), ("Spring", 3), ("Metal Bracket", 5), ("Bicycle Bell", 1)]),
]

SAFETY_WORDS = r"weapon|gun|cannon|launcher|crossbow|sling ?shot|trap|explos|fire|flame|burn|heat|heater|boil|solder|mains|volt|shock|taser|battery|charger|lithium|capacitor|transformer|pressur|compress|blade|knife|lock ?pick|climb|ladder|helmet|seat|chair|swing|harness"
CLAIM_WORDS = {  # claim word -> a material name must contain one of these for the claim to be credible
    "wifi|wi-fi|bluetooth|wireless|smart|app\\b": ("phone", "board", "circuit", "usb"),
    "solar": ("solar",),
    "motori[sz]ed|robot|automatic|self-": ("motor", "fan", "servo", "stepper"),
    "led\\b|light|lamp|glow|illuminat|flash": ("led", "lamp", "light", "bulb", "phone", "screen", "board"),
    "sensor|alarm|detect|sound|speaker|music|radio": ("sensor", "speaker", "buzzer", "headphone", "board", "phone"),
}
BROKEN = re.compile(r"broken|dead|cracked|swollen|rusty|jammed|stripped|old|worn", re.I)
FUNCTIONAL_RESULT = re.compile(r"motor|drive|pump|light|lamp|sensor|power|generator|engine|circuit|charger", re.I)


def raw_needs(idea):
    """Raw units needed to craft the final_requires from scratch: each recipe consumes one of each input."""
    by_result = {r["result_id"]: r for r in idea["recipes"]}
    need = {}

    def expand(item, qty):
        if item in by_result:
            r = by_result[item]
            expand(r["a"], qty)
            expand(r["b"], qty)
        else:
            need[item] = need.get(item, 0) + qty

    for f in idea["final_requires"]:
        expand(f["id"], f["qty"])
    return need


def flags_for(idea, materials):
    names = {m["id"]: m["name"] for m in materials}
    have = {m["id"]: m["qty"] for m in materials}
    text = " ".join([idea["title"], idea["pitch"]] + [r["result_name"] for r in idea["recipes"]])
    mat_text = " ".join(names[i] for i in idea["uses_material_ids"]).lower()
    flags = []
    if re.search(SAFETY_WORDS, text, re.I):
        flags.append("SAFETY? mentions: " + ", ".join(sorted({m.lower() for m in re.findall(SAFETY_WORDS, text, re.I)})))
    for pattern, needs in CLAIM_WORDS.items():
        if re.search(pattern, text, re.I) and not any(n in mat_text for n in needs):
            flags.append(f"UNSUPPORTED CLAIM? '{re.search(pattern, text, re.I).group(0)}' but no matching material")
    for r in idea["recipes"]:
        if FUNCTIONAL_RESULT.search(r["result_name"]):
            used = [names[x] for x in (r["a"], r["b"]) if x in names and BROKEN.search(names[x])]
            if used:
                flags.append(f"BROKEN PART AS FUNCTION? '{r['result_name']}' built from {', '.join(used)}")
    short = {i: q - have.get(i, 0) for i, q in raw_needs(idea).items() if q > have.get(i, 0)}
    if short:
        flags.append("needs more than owned: " + ", ".join(f"{names.get(i, i)} (+{q})" for i, q in short.items()))
    return flags


def stub_generate(materials):
    ids = [m["id"] for m in materials]
    if len(ids) < 2:
        return []
    return server.validate_and_clean({"ideas": [{
        "id": "stub", "title": "Stub Winch", "pitch": "A motorized winch with wifi.",
        "recipes": [{"a": ids[0], "b": ids[1], "result_id": "unit", "result_name": "Motor Unit", "result_short": "MU"}],
        "final_requires": [{"id": "unit", "qty": 2}, {"id": ids[0], "qty": 1}],
    }]}, materials)


def real_generate(materials, rejected):
    import anthropic  # noqa: F401  (clear ImportError if missing)
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=server.MODEL, max_tokens=4096, system=server.IDEA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "Materials on hand (id, name, quantity):\n" + json.dumps(materials, indent=2)
                   + "\n\nPropose a catalog of buildable project ideas using these materials, following the schema."}],
        output_config={"format": {"type": "json_schema", "schema": server.api_schema(server.IDEA_SCHEMA)}},
    )
    data = json.loads(server.first_text(response))
    return server.validate_and_clean(data, materials, rejected), len(data.get("ideas", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", type=int, help="1-based scenario numbers")
    ap.add_argument("--steps", action="store_true", help="also generate assembly steps for each idea")
    ap.add_argument("--stub", action="store_true", help="no API calls; canned output to test the harness")
    ap.add_argument("--out", default="recipe_quality_report.md")
    args = ap.parse_args()
    if not args.stub and not __import__("os").environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set (use --stub to test the harness without it).")

    chosen = [(i, s) for i, s in enumerate(SCENARIOS, 1) if not args.only or i in args.only]
    out = ["# Recipe quality report", "", f"Model: `{server.MODEL}`" + ("  (STUB: canned output, not real model results)" if args.stub else ""), ""]
    totals = {"returned": 0, "kept": 0, "flagged": 0}
    for n, (label, mats) in chosen:
        materials = [{"id": server.slugify(name) if hasattr(server, "slugify") else "m_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"), "name": name, "qty": q} for name, q in mats]
        rejected = []
        try:
            if args.stub:
                ideas, returned = stub_generate(materials), 1
            else:
                ideas, returned = real_generate(materials, rejected)
        except Exception as e:  # noqa: BLE001
            out += [f"## {n}. {label}", "", f"**Generation failed:** {e}", ""]
            continue
        totals["returned"] += returned
        totals["kept"] += len(ideas)
        out += [f"## {n}. {label}", "", "Materials: " + ", ".join(f"{name} x{q}" for name, q in mats), "",
                f"Model returned {returned} ideas; {len(ideas)} passed validation.", ""]
        for title, problems in rejected:
            out.append(f"- REJECTED **{title}**: {'; '.join(problems)}")
        if rejected:
            out.append("")
        titles = [i["title"] for i in ideas]
        for idea in ideas:
            fl = flags_for(idea, materials)
            totals["flagged"] += bool([f for f in fl if not f.startswith("needs more")])
            names = {m["id"]: m["name"] for m in materials}
            names.update({r["result_id"]: r["result_name"] for r in idea["recipes"]})
            out += [f"### {idea['title']}", f"_{idea['pitch']}_", ""]
            out += [f"- {names[r['a']]} + {names[r['b']]} -> **{r['result_name']}**" for r in idea["recipes"]]
            out += ["- Final: " + ", ".join(f"{names[f['id']]} x{f['qty']}" for f in idea["final_requires"])]
            out += [f"- ⚑ {f}" for f in fl]
            if args.steps and not args.stub:
                brief = {"title": idea["title"], "pitch": idea["pitch"],
                         "sub_assemblies": [r["result_name"] for r in idea["recipes"]],
                         "final_parts": [f"{names[f['id']]} x{f['qty']}" for f in idea["final_requires"]]}
                try:
                    out += ["", "Steps:"] + [f"{k}. {s}" for k, s in enumerate(server.generate_steps(brief), 1)]
                except Exception as e:  # noqa: BLE001
                    out.append(f"(steps failed: {e})")
            out += ["", "**Reviewer verdict:** [ ] plausible  [ ] unsafe  [ ] boring  [ ] other: ", ""]
        if len(set(t.lower() for t in titles)) < len(titles):
            out.append("⚑ duplicate titles in this batch\n")
    out += ["---", f"Totals: {totals['returned']} ideas returned, {totals['kept']} kept, {totals['flagged']} with safety/claim/broken-part flags to read first."]
    Path(args.out).write_text("\n".join(out) + "\n")
    print(f"Wrote {args.out}  ({totals})")


if __name__ == "__main__":
    main()
