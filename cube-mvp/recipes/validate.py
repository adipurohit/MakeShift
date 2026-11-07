#!/usr/bin/env python3
"""
Validate cube-mvp/recipes/pack.json, the offline recipe pack.

Run after adding or editing a recipe:
    python3 cube-mvp/recipes/validate.py

Checks every recipe is playable in the app: each merge uses parts that exist,
no two merges in one recipe share the same pair, every part and sub-assembly
gets used, and the raw part counts are enough to build the final requirements.
Exit code 0 = valid, 1 = at least one problem.
"""
import json
import sys
from collections import Counter
from pathlib import Path

PACK = Path(__file__).resolve().parent / "pack.json"
REQUIRED = ["id", "title", "category", "difficulty", "pitch", "rawMaterials",
            "recipes", "final_requires", "assembly_steps", "extend"]
DIFFICULTIES = {"Easy", "Medium", "Hard"}


def check(recipe):
    errs = []
    rid = recipe.get("id", "?")
    for field in REQUIRED:
        if not recipe.get(field):
            errs.append(f"missing '{field}'")
    if errs:
        return errs
    if recipe["difficulty"] not in DIFFICULTIES:
        errs.append(f"difficulty must be one of {sorted(DIFFICULTIES)}")
    if "Robot Arm" in recipe["title"]:
        errs.append("title must not contain 'Robot Arm' (reserved for the built-in demo)")

    raw = {}
    for m in recipe["rawMaterials"]:
        if m["id"] in raw:
            errs.append(f"duplicate raw material '{m['id']}'")
        if not m.get("name") or not isinstance(m.get("qty"), int) or m["qty"] < 1:
            errs.append(f"raw material '{m['id']}' needs a name and a qty of 1 or more")
        raw[m["id"]] = m.get("qty", 0)

    results, pairs, used = {}, set(), Counter()
    for r in recipe["recipes"]:
        a, b, res = r["a"], r["b"], r["result_id"]
        if a == b:
            errs.append(f"merge {a} + {b}: both inputs are the same part")
        for x in (a, b):
            if x not in raw and x not in results:
                errs.append(f"merge for '{res}' uses '{x}', which is not a raw part or an earlier result")
            used[x] += 1
        pair = frozenset((a, b))
        if pair in pairs:
            errs.append(f"two merges use the same pair {a} + {b}")
        pairs.add(pair)
        if res in raw or res in results:
            errs.append(f"result id '{res}' is already in use")
        if not r.get("result_name") or not r.get("result_short"):
            errs.append(f"result '{res}' needs result_name and result_short")
        results[res] = (a, b)

    need = Counter()

    def expand(item, q):
        if item in results:
            a, b = results[item]
            expand(a, q)
            expand(b, q)
        else:
            need[item] += q

    for f in recipe["final_requires"]:
        if f["id"] not in raw and f["id"] not in results:
            errs.append(f"final requirement '{f['id']}' is not a raw part or result")
            continue
        if not isinstance(f.get("qty"), int) or not 1 <= f["qty"] <= 10:
            errs.append(f"final requirement '{f['id']}' qty must be 1 to 10")
            continue
        used[f["id"]] += 1
        expand(f["id"], f["qty"])

    for res in results:
        if not used[res]:
            errs.append(f"result '{res}' is never used")
    for m in raw:
        if not used[m]:
            errs.append(f"raw part '{m}' is never used")
        elif raw[m] < need[m]:
            errs.append(f"raw part '{m}' has qty {raw[m]} but the build needs {need[m]}")

    steps = recipe["assembly_steps"]
    if not 2 <= len(steps) <= 8:
        errs.append("needs 2 to 8 assembly steps")
    for s in steps:
        if len(s) < 25:
            errs.append(f"step too short to follow: '{s}'")
    return errs


def main():
    data = json.loads(PACK.read_text())
    recipes = data.get("recipes", [])
    problems = 0
    ids, titles = Counter(r.get("id") for r in recipes), Counter(r.get("title") for r in recipes)
    for dup in [i for i, n in ids.items() if n > 1]:
        print(f"[FAIL] duplicate id '{dup}'")
        problems += 1
    for dup in [t for t, n in titles.items() if n > 1]:
        print(f"[FAIL] duplicate title '{dup}'")
        problems += 1
    for r in recipes:
        for e in check(r):
            print(f"[FAIL] {r.get('id', '?')}: {e}")
            problems += 1
    cats = Counter(r.get("category") for r in recipes)
    print(f"{len(recipes)} recipes, {len(cats)} categories: " +
          ", ".join(f"{c} {n}" for c, n in sorted(cats.items())))
    print("OK" if not problems else f"{problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
