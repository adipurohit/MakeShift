// Exercises the camera-scan state machine in app.js against a mocked camera + fetch (jsdom).
// Not a substitute for a real-device test, but it covers the permission/race/timeout paths.
//   cd cube-mvp && npm i --no-save jsdom && node tests/scan_logic.test.js
const fs = require("fs"), path = require("path"), assert = require("assert");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8").replace(/<script[\s\S]*?<\/script>/g, "");
const src = fs.readFileSync(path.join(root, "app.js"), "utf8");
const section = src.slice(src.indexOf("/* ================= CAMERA SCAN"), src.indexOf("/* ================= RESET"));

const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));
let passed = 0;
async function test(name, fn) {
  const dom = new JSDOM(html, { pretendToBeVisual: true, runScripts: "outside-only", url: "http://localhost:8743/" });
  const w = dom.window;
  const log = { added: [], toasts: [], stopped: 0, getUserMediaCalls: 0 };
  const makeStream = () => ({ getTracks: () => [{ stop: () => log.stopped++ }], getVideoTracks: () => [{ readyState: "live" }] });
  const ctx = { cam: { mode: "ok", delay: 0 }, fetchImpl: null };
  Object.defineProperty(w.navigator, "mediaDevices", { configurable: true, value: {
    getUserMedia: async () => {
      log.getUserMediaCalls++;
      await tick(ctx.cam.delay);
      if (ctx.cam.mode === "denied") { const e = new Error("denied"); e.name = "NotAllowedError"; throw e; }
      return makeStream();
    } } });
  w.HTMLMediaElement.prototype.play = () => Promise.resolve();
  w.HTMLCanvasElement.prototype.getContext = () => ({ drawImage() {} });
  w.HTMLCanvasElement.prototype.toDataURL = () => "data:image/jpeg;base64,AAAA";
  w.fetch = (...a) => ctx.fetchImpl(...a);
  const video = w.document.getElementById("scanVideo");
  Object.defineProperty(video, "videoWidth", { value: 1920, configurable: true });
  Object.defineProperty(video, "videoHeight", { value: 1080, configurable: true });
  Object.defineProperty(video, "readyState", { value: 4, configurable: true });
  w.addMaterial = (n, q) => log.added.push([n, q]);
  w.toast = (m) => log.toasts.push(m);
  w.eval(section + "\ninitScan();");
  const $ = (id) => w.document.getElementById(id);
  const click = (id) => $(id).dispatchEvent(new w.Event("click"));
  const vis = (id) => !$(id).hidden;
  try { await fn({ w, $, click, vis, log, ctx }); console.log("  ok  " + name); passed++; }
  catch (e) { console.log("FAIL  " + name + "\n      " + e.message); process.exitCode = 1; }
  finally { w.close(); }
}
const okJson = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body });

(async () => {
  await test("happy path: open, capture, AI name, add to inventory", async ({ $, click, vis, log, ctx }) => {
    let sent; ctx.fetchImpl = (u, o) => { sent = JSON.parse(o.body); return okJson({ name: "broken stepper motor", confidence: "high" }); };
    click("scanBtn"); await tick(5);
    assert(vis("scanCameraWrap") && $("scanModal").classList.contains("visible"));
    click("captureBtn"); await tick(5);
    assert(sent.image.startsWith("data:image/jpeg"));
    assert(vis("scanResult") && $("scanNameInput").value === "broken stepper motor");
    click("scanConfirmBtn");
    assert.deepStrictEqual(log.added, [["broken stepper motor", 1]]);
    assert(!$("scanModal").classList.contains("visible") && log.stopped === 1, "camera must be released");
  });

  await test("permission denied -> manual form; 'back' retries instead of showing a dead video", async ({ $, click, vis, log, ctx }) => {
    ctx.cam.mode = "denied";
    click("scanBtn"); await tick(5);
    assert(vis("manualAddPanel") && !vis("scanCameraWrap"));
    assert(/denied/i.test($("scanStatus").textContent), $("scanStatus").textContent);
    ctx.cam.mode = "ok";
    click("manualBackBtn"); await tick(5);
    assert(log.getUserMediaCalls === 2 && vis("scanCameraWrap"), "second attempt should re-request the camera");
  });

  await test("closing while the permission prompt is open does not leak the camera", async ({ $, click, log, ctx }) => {
    ctx.cam.delay = 30;
    click("scanBtn"); await tick(5);
    click("closeScanBtn"); await tick(60);
    assert(log.stopped === 1, "late stream must be stopped (stopped=" + log.stopped + ")");
  });

  await test("double-clicking Scan opens only one stream", async ({ click, log }) => {
    click("scanBtn"); click("scanBtn"); await tick(10);
    assert(log.getUserMediaCalls === 1);
  });

  await test("server error -> manual fallback with the server's message", async ({ $, click, vis, ctx }) => {
    ctx.fetchImpl = () => okJson({ message: "The API key was rejected." }, 502);
    click("scanBtn"); await tick(5); click("captureBtn"); await tick(5);
    assert(vis("manualAddPanel") && /API key was rejected/.test($("scanStatus").textContent));
  });

  await test("server unreachable -> friendly message", async ({ $, click, vis, w, ctx }) => {
    ctx.fetchImpl = () => Promise.reject(new w.TypeError("Failed to fetch"));
    click("scanBtn"); await tick(5); click("captureBtn"); await tick(5);
    assert(vis("manualAddPanel") && /reach the MakeShift server/.test($("scanStatus").textContent), $("scanStatus").textContent);
  });

  await test("closing mid-identify ignores the late response", async ({ $, click, vis, ctx, log }) => {
    ctx.fetchImpl = () => new Promise((r) => setTimeout(() => r({ ok: true, status: 200, json: async () => ({ name: "late", confidence: "high" }) }), 30));
    click("scanBtn"); await tick(5); click("captureBtn"); await tick(5);
    click("closeScanBtn"); await tick(60);
    assert(!vis("scanResult") && $("scanNameInput").value === "", "stale result must not populate the form");
  });

  await test("low-confidence / unclear result warns the user", async ({ $, click, ctx }) => {
    ctx.fetchImpl = () => okJson({ name: "unclear item", confidence: "low" });
    click("scanBtn"); await tick(5); click("captureBtn"); await tick(5);
    assert(/Not sure/.test($("scanStatus").textContent));
  });

  await test("capture before the video has frames is refused (no black-frame upload)", async ({ $, click, ctx, w }) => {
    let called = false; ctx.fetchImpl = () => { called = true; return okJson({}); };
    click("scanBtn"); await tick(5);
    Object.defineProperty($("scanVideo"), "readyState", { value: 0, configurable: true });
    Object.defineProperty($("scanVideo"), "videoWidth", { value: 0, configurable: true });
    click("captureBtn"); await tick(5);
    assert(!called && /warming up/.test($("scanStatus").textContent));
  });

  await test("Retake returns to the live camera without re-prompting", async ({ $, click, vis, ctx, log }) => {
    ctx.fetchImpl = () => okJson({ name: "zip ties", confidence: "medium" });
    click("scanBtn"); await tick(5); click("captureBtn"); await tick(5);
    click("scanRetryBtn"); await tick(5);
    assert(vis("scanCameraWrap") && log.getUserMediaCalls === 1);
  });

  await test("insecure context / no mediaDevices -> readable message + manual form", async ({ $, click, vis, w }) => {
    Object.defineProperty(w.navigator, "mediaDevices", { configurable: true, value: undefined });
    click("scanBtn"); await tick(5);
    assert(vis("manualAddPanel") && /secure page|can't access a camera/.test($("scanStatus").textContent), $("scanStatus").textContent);
  });

  console.log(`\n${passed} passed`);
})();
