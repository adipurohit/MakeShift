#!/usr/bin/env python3
"""
End-to-end test of the Cloudflare Worker (worker/ + wrangler.jsonc) without a real Gemini key.

Runs the Worker locally with `wrangler dev`, pointed at a stand-in Gemini server on localhost,
then checks: the app loads at /makeshift/, the camera scan in a real browser (fake camera)
reaches the Worker and gets a cleaned answer, ideas, steps, and source suggestions come back validated, the Worker
sends Gemini the right key, model, and schema, and the guards work (no key, wrong origin,
bad image, rate limit).

Usage: python3 cube-mvp/tests/worker_e2e_test.py
Needs: Node 18+, `npx wrangler` (or WRANGLER=/path/to/wrangler), Playwright with Chromium.
Exit code 0 = all checks passed, 1 = at least one failure.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRANGLER = os.environ.get("WRANGLER") or shutil.which("wrangler") or "npx wrangler"
results = []
gemini_calls = []
# reject_json_schema: act like a Gemini that doesn't know responseJsonSchema, to exercise the fallback
gemini_mode = {"reject_json_schema": False, "reject_thinking": False}


def schema_of(body):
    gc = body["generationConfig"]
    return gc.get("responseJsonSchema") or gc.get("responseSchema")


def has_key(obj, key):
    if isinstance(obj, dict):
        return key in obj or any(has_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(has_key(v, key) for v in obj)
    return False
gemini_429 = {"left": 0}  # respond with 429 this many times before succeeding


def check(ok, name, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeGemini(BaseHTTPRequestHandler):
    """Returns Gemini generateContent responses, selecting output from the requested JSON schema."""

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        gemini_calls.append({"auth": self.headers.get("x-goog-api-key"), "body": body, "path": self.path})
        if gemini_429["left"] > 0:
            gemini_429["left"] -= 1
            self.send_response(429)
            self.send_header("Retry-After", "1")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": {"message": "rate limit"}}')
            return
        # Gemini's responseSchema is an OpenAPI subset; reject unsupported JSON Schema keywords.
        gc = body.get("generationConfig", {})
        schema = gc.get("responseJsonSchema") or gc.get("responseSchema") or {}
        bad = None
        if "responseSchema" in gc and has_key(gc["responseSchema"], "additionalProperties"):
            bad = 'Invalid JSON payload received. Unknown name "additionalProperties" at \'generation_config.response_schema\': Cannot find field.'
        elif gemini_mode["reject_thinking"] and "thinkingConfig" in gc:
            bad = 'Invalid JSON payload received. Unknown name "thinkingConfig" at \'generation_config\': Cannot find field.'
        elif gemini_mode["reject_json_schema"] and "responseJsonSchema" in gc:
            bad = 'Invalid JSON payload received. Unknown name "responseJsonSchema" at \'generation_config\': Cannot find field.'
        if bad:
            out = json.dumps({"error": {"code": 400, "message": bad, "status": "INVALID_ARGUMENT"}}).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        props = schema.get("properties", {})
        if "confidence" in props:
            content = {"name": "  <b>broken</b> stepper   motor ", "confidence": "high"}
        elif "assembly_steps" in props:
            content = {"assembly_steps": ["1. Glue the tube to the base.", "Step 2: Tie the pulley on.", "<i>Check</i> it spins freely."]}
        elif "suggestions" in props:
            brief = json.loads(body["contents"][0]["parts"][0]["text"].split("\n", 1)[1])
            content = {"suggestions": [
                {"material": "Motor", "places": ["<b>Repair shop</b>", "Repair shop", "E-waste center"],
                 "salvage_tip": "Check an old printer.", "safety_note": "Ask permission."},
                {"material": "Invented part", "places": ["Nowhere"], "salvage_tip": "", "safety_note": ""},
            ] + [{"material": m["name"], "places": ["Makerspace parts bin"], "salvage_tip": "Look in old printers.",
                  "safety_note": "Ask first."} for m in brief["materials"] if m["name"] != "Motor"]}
        else:
            content = {"ideas": [
                {"id": "Crank!", "title": "Hand Crank", "pitch": "A winch.", "uses_material_ids": [],
                 "recipes": [{"a": "m_motor", "b": "m_pulley", "result_id": "crank", "result_name": "Crank", "result_short": "CR"}],
                 "final_requires": [{"id": "crank", "qty": 1}, {"id": "m_zip", "qty": 2}]},
                {"id": "bad", "title": "Bad", "pitch": "Uses a part that does not exist.", "uses_material_ids": [],
                 "recipes": [{"a": "m_motor", "b": "ghost", "result_id": "x", "result_name": "X", "result_short": "X"}],
                 "final_requires": [{"id": "x", "qty": 1}]},
            ]}
        out = json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(content)}]}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def start_worker(port, extra_vars):
    # a fresh state folder per run, so rate-limit counters from an earlier run never leak in
    state_dir = tempfile.mkdtemp(prefix="makeshift-wrangler-")
    cmd = WRANGLER.split() + ["dev", "--port", str(port), "--ip", "127.0.0.1", "--show-interactive-dev-session=false",
                              "--persist-to", state_dir]
    for k, v in extra_vars.items():
        cmd += ["--var", f"{k}:{v}"]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/makeshift/", timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("wrangler dev did not start")


def post(port, path, payload, origin="same", session="test-session"):
    # like the app: same-origin Origin header and a session id; origin=None sends no Origin at all
    origin = f"http://127.0.0.1:{port}" if origin == "same" else origin
    headers = {"Content-Type": "application/json", "X-MakeShift-Session": session, **({"Origin": origin} if origin else {})}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def stop(proc):
    try:
        os.killpg(proc.pid, 15)
    except Exception:
        proc.terminate()


def main():
    from playwright.sync_api import sync_playwright

    gemini_port, port, nokey_port = free_port(), free_port(), free_port()
    gemini = ThreadingHTTPServer(("127.0.0.1", gemini_port), FakeGemini)
    threading.Thread(target=gemini.serve_forever, daemon=True).start()
    worker = start_worker(port, {"GEMINI_API_KEY": "test-key", "GEMINI_BASE_URL": f"http://127.0.0.1:{gemini_port}/v1beta"})
    nokey = start_worker(nokey_port, {})
    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/makeshift", timeout=5) as r:
            check(r.url.endswith("/makeshift/"), "/makeshift redirects to /makeshift/", r.url)

        # camera scan through the real page, fake camera, real Worker
        with sync_playwright() as pw:
            args = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            browser = pw.chromium.launch(args=args)
            ctx = browser.new_context(permissions=["camera"], viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            requested = []
            session_headers = []
            def record_request(request):
                if request.url.startswith(base):
                    path = urllib.parse.urlsplit(request.url).path
                    requested.append(path)
                    if "/api/" in path:
                        session_headers.append(request.headers.get("x-makeshift-session"))
            page.on("request", record_request)
            page.goto(f"{base}/makeshift/")
            page.evaluate("localStorage.setItem('makeshift_intro_seen', '1')")
            page.reload()
            check(page.locator("#catalogList .idea-row").count() == 101, "app loads all 101 recipes from the Worker")
            page.click("#scanBtn")
            page.wait_for_function("document.getElementById('scanVideo').videoWidth > 0", timeout=8000)
            page.click("#captureBtn")
            page.wait_for_selector("#scanResult:not([hidden])", timeout=10000)
            name = page.input_value("#scanNameInput")
            check(name == "broken stepper motor", "scan in the browser returns the Worker's cleaned answer", name)
            check(not errors, "no page errors during scan", "; ".join(errors))
            check(bool(session_headers) and all(session_headers), "browser AI requests include a per-browser session ID")

            # sourcing from the real button, on the page served under /makeshift/
            page.click("#closeScanBtn")
            page.locator("#catalogList .idea-row", has_text="Robot Arm").first.click()
            page.click("#findSourcesBtn")
            page.wait_for_selector("#sourceSuggestions .source-mode-note", timeout=10000)
            note = page.inner_text("#sourceSuggestions .source-mode-note")
            check(note.startswith("AI suggestions"), "sourcing button on the hosted page gets AI suggestions, not the offline fallback", note)
            outside = sorted({u for u in requested if not u.startswith("/makeshift/") and u != "/makeshift"})
            check(not outside, "every request from the page stays under /makeshift/", ", ".join(outside))
            browser.close()

        scan_call = next((c for c in gemini_calls if "confidence" in schema_of(c["body"]).get("properties", {})), None)
        gens = [c["body"]["generationConfig"] for c in gemini_calls]
        check(gens and all(("responseJsonSchema" in g) ^ ("responseSchema" in g) for g in gens),
              "every Gemini call sends exactly one supported schema field", f"{len(gens)} call(s)")
        check(scan_call and scan_call["auth"] == "test-key", "Worker sends the GEMINI_API_KEY secret in x-goog-api-key")
        check(scan_call and "/models/gemini-3.8-flash:generateContent" in scan_call["path"],
              "scan uses the configured Gemini vision model", scan_call and scan_call["path"])
        check(scan_call and scan_call["body"]["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/jpeg",
              "scan forwards the captured photo as Gemini inlineData")

        before = len(gemini_calls)
        status, data = post(port, "/makeshift/api/generate-ideas", {"materials": [
            {"id": "m_motor", "name": "Motor", "qty": 2}, {"id": "m_pulley", "name": "Pulley", "qty": 2},
            {"id": "m_zip", "name": "Zip Tie", "qty": 5}, {"id": "m_led", "name": "LED", "qty": 0}]})
        ideas = data.get("ideas", [])
        check(status == 200 and len(ideas) == 1 and ideas[0]["id"] == "crank" and ideas[0]["uses_material_ids"] == ["m_motor", "m_pulley", "m_zip"],
              "ideas come back validated: bad idea dropped, ids recomputed", json.dumps(ideas)[:160])
        idea_calls = [c["body"] for c in gemini_calls[before:]]
        idea_call = idea_calls[0]
        check(idea_call["generationConfig"]["responseMimeType"] == "application/json" and idea_call["contents"][0]["parts"][0]["text"].startswith("Materials on hand"), "ideas use the text model from server.py")
        check("m_led" not in idea_call["contents"][0]["parts"][0]["text"], "parts with quantity 0 never reach the AI")
        check(len(idea_calls) == 2 and "already in the catalog: Hand Crank" in idea_calls[1]["contents"][0]["parts"][0]["text"],
              "fewer than 10 valid ideas triggers one top-up call for different ones", f"{len(idea_calls)} idea call(s)")

        status, data = post(port, "/makeshift/api/generate-steps", {"idea": {"title": "Hand Crank"}})
        check(status == 200 and data.get("assembly_steps") == ["Glue the tube to the base.", "Tie the pulley on.", "Check it spins freely."],
              "steps come back with numbering and markup stripped", json.dumps(data)[:160])

        status, data = post(port, "/makeshift/api/suggest-sources", {
            "project": "Hand Crank",
            "materials": [{"name": "Motor", "needed": 2, "have": 1, "missing": 1}],
        })
        suggestions = data.get("suggestions", [])
        check(status == 200 and len(suggestions) == 1 and suggestions[0]["places"] == ["Repair shop", "E-waste center"],
              "source suggestions are sanitized and limited to requested materials", json.dumps(data)[:180])

        materials = {"materials": [{"id": "m_motor", "name": "Motor", "qty": 2}, {"id": "m_pulley", "name": "Pulley", "qty": 2},
                                   {"id": "m_zip", "name": "Zip Tie", "qty": 5}]}
        before = len(gemini_calls)
        status, data = post(port, "/makeshift/api/generate-ideas", materials)
        check(status == 200 and data.get("cached") is True and len(gemini_calls) == before,
              "the same inventory again is served from cache without calling Gemini", f"{len(gemini_calls) - before} Gemini call(s)")

        gemini_429["left"] = 1
        before = len(gemini_calls)
        status, data = post(port, "/makeshift/api/generate-steps", {"idea": {"title": "Retry"}})
        check(status == 200 and len(gemini_calls) - before == 2, "a Gemini rate limit is retried once and then succeeds", f"{status}, {len(gemini_calls) - before} calls")
        gemini_429["left"] = 2
        status, data = post(port, "/makeshift/api/generate-steps", {"idea": {"title": "Busy"}})
        check(status == 503 and data.get("error") == "ai_busy", "two Gemini rate limits in a row report the AI as busy", f"{status} {data.get('error')}")

        # Every request so far used the JSON-schema field; the live 400 came from the OpenAPI-subset field.
        check(all("responseJsonSchema" in c["body"]["generationConfig"] for c in gemini_calls[:before]),
              "Worker sends standard JSON Schema in responseJsonSchema")
        gemini_mode["reject_json_schema"] = True
        before = len(gemini_calls)
        status, data = post(port, "/makeshift/api/generate-steps", {"idea": {"title": "Fallback"}})
        retry = gemini_calls[-1]["body"]["generationConfig"] if len(gemini_calls) > before else {}
        check(status == 200 and len(gemini_calls) - before == 2 and "responseSchema" in retry
              and not has_key(retry.get("responseSchema"), "additionalProperties"),
              "if Gemini rejects responseJsonSchema, the Worker retries with a stripped responseSchema",
              f"{status}, {len(gemini_calls) - before} calls")
        gemini_mode["reject_json_schema"] = False

        check(all(c["body"]["generationConfig"].get("thinkingConfig") == {"thinkingLevel": "low"} for c in gemini_calls[:before]),
              "Worker asks Gemini for low thinking (medium took 100+ s live)")
        gemini_mode["reject_thinking"] = True
        before = len(gemini_calls)
        status, data = post(port, "/makeshift/api/generate-steps", {"idea": {"title": "No thinking"}})
        retry = gemini_calls[-1]["body"]["generationConfig"] if len(gemini_calls) > before else {}
        check(status == 200 and len(gemini_calls) - before == 2 and "thinkingConfig" not in retry,
              "if a model rejects the thinking setting, the Worker retries without it", f"{status}, {len(gemini_calls) - before} calls")
        gemini_mode["reject_thinking"] = False
        gemini_429["left"] = 0

        status, data = post(port, "/makeshift/api/identify-material", {"image": "data:image/png;base64,AAAA"}, origin=None)
        check(status == 403, "requests with no Origin (curl, scripts) are refused", status)

        status, data = post(port, "/makeshift/api/identify-material", {"image": "data:image/bmp;base64,AAAA"})
        check(status == 400 and data.get("error") == "bad_image", "unsupported image type is rejected", status)
        status, data = post(port, "/makeshift/api/identify-material", {"image": "data:image/png;base64,AAAA"}, origin="https://evil.example")
        check(status == 403, "requests from another website are refused", status)
        status, data = post(nokey_port, "/makeshift/api/identify-material", {"image": "data:image/png;base64,AAAA"})
        check(status == 503 and data.get("error") == "no_api_key", "without the secret the Worker reports AI is off", status)
        status, data = post(nokey_port, "/makeshift/api/suggest-sources", {"materials": [{"name": "Motor"}]})
        check(status == 200 and data.get("fallback") is True, "source finder quietly advertises its no-key fallback", status)

        codes = [post(port, "/makeshift/api/generate-steps", {"idea": {"title": "x"}}, session="busy-visitor")[0] for _ in range(30)]
        check(429 in codes, "one session is limited to about 20 AI calls a minute", f"first 429 at call {codes.index(429) + 1 if 429 in codes else '-'}")
        status, _ = post(port, "/makeshift/api/generate-steps", {"idea": {"title": "x"}}, session="another-visitor")
        check(status == 200, "another session on the same network still gets through", status)
    finally:
        stop(worker)
        stop(nokey)
        gemini.shutdown()
    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
