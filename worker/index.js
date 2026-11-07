// Cloudflare Worker for MakeShift at adipurohit.com/makeshift.
// Serves the static app from ./dist, and answers the four AI endpoints the Python server
// answers locally: POST .../api/generate-ideas, generate-steps, suggest-sources, identify-material.
// The Gemini key lives in a Worker secret named GEMINI_API_KEY, never in the repo.
import {
  ApiError, BadImage, BusyError, CONFIG_VERSION, MAX_BODY_BYTES,
  cleanMaterials, cleanSourceMaterials, generateIdeas, generateSteps, generateSourceSuggestions, identifyMaterial,
} from "./ai.js";

const API_RE = /\/api\/(generate-ideas|generate-steps|suggest-sources|identify-material)$/;

// ---- idea cache (Cloudflare Cache API, per data center) ----
async function cacheKeyFor(url, kind, value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify([CONFIG_VERSION, value])));
  const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return new Request(`${url.origin}/makeshift/__cache/${kind}/${hex}`);
}
const ideasCacheKey = (url, materials) =>
  cacheKeyFor(url, "ideas", materials.map((m) => [m.id, m.name, m.qty]).sort());
// Step guides take ~1 minute from Gemini; the same brief gets the same guide for 6 hours, so a pre-warmed
// demo build answers instantly.
const stepsCacheKey = (url, brief) => cacheKeyFor(url, "steps", brief);
async function cacheGet(key) {
  try {
    const hit = typeof caches !== "undefined" && (await caches.default.match(key));
    return hit ? await hit.json() : null;
  } catch (e) {
    return null;
  }
}
async function cachePut(key, payload) {
  try {
    if (typeof caches === "undefined") return;
    await caches.default.put(key, new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=21600" },
    }));
  } catch (e) { /* cache is best-effort */ }
}

const json = (status, payload) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const match = API_RE.exec(url.pathname);
    if (!match) return env.ASSETS.fetch(request);
    if (request.method !== "POST") return json(405, { error: "method_not_allowed", message: "Use POST." });

    // Only the MakeShift page may call these endpoints. Browsers always send Origin on a POST, so a
    // missing Origin means a script, not the app. A script can fake the header, so the real protection
    // is the rate limits below plus a spending cap on the Gemini key.
    const origin = request.headers.get("Origin");
    if (origin !== url.origin) {
      return json(403, { error: "forbidden", message: "This endpoint only serves the MakeShift app." });
    }

    // Per-network and per-browser-session limits protect the Gemini key while allowing
    // multiple people on the same network to use the demo independently.
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const session = (request.headers.get("X-MakeShift-Session") || "").replace(/[^A-Za-z0-9_-]/g, "").slice(0, 40);
    if (env.AI_IP_LIMIT && !(await env.AI_IP_LIMIT.limit({ key: ip })).success) {
      return json(429, { error: "rate_limited", message: "Too many AI requests from this network. Wait a minute and try again." });
    }
    if (env.AI_LIMIT && !(await env.AI_LIMIT.limit({ key: `${ip}:${session}` })).success) {
      return json(429, { error: "rate_limited", message: "Too many AI requests. Wait a minute and try again." });
    }

    const length = Number(request.headers.get("Content-Length") || 0);
    if (length > MAX_BODY_BYTES) return json(413, { error: "too_large", message: "Request is too large." });
    let body;
    try {
      const text = await request.text();
      if (text.length > MAX_BODY_BYTES) return json(413, { error: "too_large", message: "Request is too large." });
      body = JSON.parse(text || "{}");
    } catch (e) {
      return json(400, { error: "bad_request", message: "Invalid JSON body." });
    }
    if (body === null || typeof body !== "object" || Array.isArray(body)) {
      return json(400, { error: "bad_request", message: "Expected a JSON object." });
    }

    if (!env.GEMINI_API_KEY) {
      if (match[1] === "suggest-sources") return json(200, { suggestions: [], fallback: true });
      return json(503, {
        error: "no_api_key",
        message: "AI features are off: no GEMINI_API_KEY secret on this site. Catalog recipes still work.",
      });
    }

    // aiEnv carries the bindings plus a trace of which Gemini model answered (the backup model may step in).
    const trace = [];
    const aiEnv = Object.assign(Object.create(env), { __trace: trace });
    const model = () => trace[trace.length - 1];
    try {
      if (match[1] === "generate-ideas") {
        const materials = cleanMaterials(body.materials);
        if (!materials.length) return json(400, { error: "no_materials", message: "Add at least one material first." });
        // Same inventory, same ideas for 6 hours: saves Gemini quota and lets you pre-warm a demo inventory.
        const cacheKey = await ideasCacheKey(url, materials);
        const cached = await cacheGet(cacheKey);
        if (cached) return json(200, { ...cached, cached: true });
        const ideas = await generateIdeas(aiEnv, materials);
        if (ideas.length) await cachePut(cacheKey, { ideas, model: model() });
        if (!ideas.length) {
          return json(502, { error: "no_valid_ideas", message: "The model's response didn't validate cleanly. Try again, or use the offline example idea." });
        }
        return json(200, { ideas, model: model() });
      }
      if (match[1] === "generate-steps") {
        const brief = body.idea;
        if (!brief || typeof brief !== "object" || Array.isArray(brief)) {
          return json(400, { error: "bad_request", message: "Missing idea details." });
        }
        const stepsKey = await stepsCacheKey(url, brief);
        const cachedSteps = await cacheGet(stepsKey);
        if (cachedSteps) return json(200, { ...cachedSteps, cached: true });
        const steps = await generateSteps(aiEnv, brief);
        if (!steps.length) return json(502, { error: "no_steps", message: "Couldn't generate assembly steps. Try again." });
        await cachePut(stepsKey, { assembly_steps: steps, model: model() });
        return json(200, { assembly_steps: steps, model: model() });
      }
      if (match[1] === "suggest-sources") {
        const materials = cleanSourceMaterials(body.materials);
        if (!materials.length) return json(400, { error: "no_materials", message: "No needed materials were provided." });
        const suggestions = await generateSourceSuggestions(aiEnv, body.project, materials);
        if (!suggestions.length) return json(502, { error: "no_suggestions", message: "Couldn't generate sourcing suggestions. Try again." });
        return json(200, { suggestions, model: model() });
      }
      if (!body.image) return json(400, { error: "bad_request", message: "No image provided." });
      return json(200, { ...(await identifyMaterial(aiEnv, body.image)), model: model() });
    } catch (e) {
      if (e instanceof BadImage) return json(400, { error: "bad_image", message: e.message });
      if (e instanceof BusyError) return json(503, { error: "ai_busy", message: e.message });
      const message = e instanceof ApiError ? e.message : "Unexpected error. Try again.";
      return json(502, { error: "generation_failed", message });
    }
  },
};
