#!/usr/bin/env python3
"""
Measure camera-scan accuracy on real photos of real scrap.

1. Photograph about 30 different scrap items, one item per photo, on a plain table, the way a user would.
2. Name each file after what the item really is: stepper-motor.jpg, cardboard-tube-2.jpg, zip-ties.heic ...
   (dashes or underscores become spaces; a trailing -2 / _3 counter is ignored).
3. Put them in one folder and run:

       python3 scripts/scan_accuracy.py ~/scan-photos                       # through the live site
       python3 scripts/scan_accuracy.py ~/scan-photos --url http://localhost:8743/   # through server.py

It sends each photo to the same endpoint the app's Scan button uses, then writes scan-accuracy.md in the
folder: top-1 accuracy (strict and lenient), accuracy by confidence level, and every miss side by side.

Lenient match: every meaningful word of the true label appears in the guess, ignoring plurals and condition
words ("broken", "old", "rusty"), so "stepper motor" matches "broken stepper motor" but not "dc motor".
Strict match: the same, plus no extra object words. Read the misses yourself; the numbers are a guide.
"""
import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
         ".heic": "image/heic", ".heif": "image/heif"}
CONDITION = {"broken", "old", "used", "rusty", "cracked", "dead", "worn", "dirty", "bent", "damaged", "small",
             "large", "big", "a", "an", "the", "of", "piece", "pieces", "bundle", "pile", "set"}


def words(text):
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in CONDITION:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


def label_for(path):
    stem = re.sub(r"[-_ ]\d+$", "", path.stem)
    return re.sub(r"[-_]+", " ", stem).strip()


def identify(url, path, origin):
    data = base64.b64encode(path.read_bytes()).decode()
    body = json.dumps({"image": f"data:{TYPES[path.suffix.lower()]};base64,{data}"}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Origin": origin, "X-MakeShift-Session": "scan-accuracy"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "message": json.loads(e.read() or b"{}").get("message", "")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--url", default="https://adipurohit.com/makeshift/", help="app URL (live site by default)")
    ap.add_argument("--pace", type=float, default=4.0, help="seconds between photos, to stay under rate limits")
    args = ap.parse_args()

    photos = sorted(p for p in args.folder.iterdir() if p.suffix.lower() in TYPES)
    if not photos:
        sys.exit(f"No photos in {args.folder} (jpg, png, webp, heic).")
    base = args.url.rstrip("/") + "/"
    origin = re.match(r"https?://[^/]+", base).group(0)
    rows = []
    for i, photo in enumerate(photos):
        truth = label_for(photo)
        res = identify(base + "api/identify-material", photo, origin)
        guess = res.get("name", "")
        t, g = words(truth), words(guess)
        lenient = bool(t) and t <= g
        strict = lenient and g <= t
        rows.append({"file": photo.name, "truth": truth, "guess": guess or f"(error {res.get('error')}: {res.get('message')})",
                     "confidence": res.get("confidence", "-"), "lenient": lenient, "strict": strict})
        print(f"{'OK ' if lenient else 'MISS'} {truth!r:32} -> {guess!r} ({res.get('confidence', '-')})")
        if i < len(photos) - 1:
            time.sleep(args.pace)

    n = len(rows)
    pct = lambda k: f"{sum(r[k] for r in rows)}/{n} ({100 * sum(r[k] for r in rows) / n:.0f}%)"
    lines = ["# Camera scan accuracy", "", f"{n} photos via {base}", "",
             f"- Top-1 lenient: **{pct('lenient')}**", f"- Top-1 strict: {pct('strict')}", ""]
    lines += ["| Confidence | Photos | Lenient correct |", "|---|---|---|"]
    for level in ("high", "medium", "low"):
        sub = [r for r in rows if r["confidence"] == level]
        if sub:
            lines.append(f"| {level} | {len(sub)} | {sum(r['lenient'] for r in sub)} |")
    lines += ["", "## Misses", "", "| Photo | True item | Scan said | Confidence |", "|---|---|---|---|"]
    lines += [f"| {r['file']} | {r['truth']} | {r['guess']} | {r['confidence']} |" for r in rows if not r["lenient"]]
    out = args.folder / "scan-accuracy.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"\nTop-1 lenient {pct('lenient')}, strict {pct('strict')}. Report: {out}")


if __name__ == "__main__":
    main()
