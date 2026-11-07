// MakeShift AI endpoints for the Cloudflare Worker.
// A line-for-line port of the guards in cube-mvp/server.py. Prompts, schemas, and limits come
// from ai-config.json, which scripts/export-ai-config.py generates from server.py.
// tests/worker_parity_test.py checks this file gives the same results as server.py.
import CFG from "./ai-config.json" with { type: "json" };

const L = CFG.limits;

// Python str() for the values JSON can hold, so id handling matches server.py exactly.
function pyStr(v) {
  if (v === null || v === undefined) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  return String(v);
}
const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const take = (s, n) => Array.from(s).slice(0, n).join("");

export function cleanText(value, limit) {
  if (typeof value !== "string") return "";
  let v = value.replace(/<[^>]*>/g, "");
  v = v.replace(/[<>\x00-\x08\x0b\x0c\x0e-\x1f]/g, "");
  return take(v.replace(/\s+/g, " ").trim(), limit);
}

export function makeShort(name) {
  const letters = name.match(/[A-Za-z0-9]+/g) || [];
  if (letters.length >= 2) return (letters[0][0] + letters[1][0]).toUpperCase();
  return (letters.length ? letters[0].slice(0, 2) : "??").toUpperCase();
}

const pairKey = (a, b) => [pyStr(a), pyStr(b)].sort().join("\u0000");

export function validateIdea(idea, materialIds) {
  const problems = [];
  if (!isObj(idea)) return [null, ["not an object"]];

  const title = cleanText(idea.title, 60);
  const pitch = cleanText(idea.pitch, 280);
  if (!title) problems.push("missing title");
  if (!pitch) problems.push("missing pitch");

  const recipesIn = Array.isArray(idea.recipes) ? idea.recipes : [];
  const finalIn = Array.isArray(idea.final_requires) ? idea.final_requires : [];
  if (!recipesIn.length) problems.push("no recipes");
  if (!finalIn.length) problems.push("no final_requires");
  if (recipesIn.length > L.max_recipes) problems.push(`${recipesIn.length} recipes (max ${L.max_recipes})`);
  if (finalIn.length > L.max_final) problems.push(`${finalIn.length} final_requires lines (max ${L.max_final})`);
  if (problems.length) return [null, problems];

  const known = new Set(materialIds);
  const results = new Map();
  const usedResults = new Set();
  const usedRaw = new Set();
  const recipes = [];
  const seenPairs = new Set();
  recipesIn.forEach((r, i) => {
    const n = i + 1;
    if (!isObj(r)) { problems.push(`recipe ${n} is not an object`); return; }
    const a = r.a, b = r.b, rid = r.result_id;
    const rname = cleanText(r.result_name, 40);
    for (const side of [a, b]) {
      if (!known.has(side)) problems.push(`recipe ${n} uses unknown id ${JSON.stringify(side ?? null)}`);
      else if (results.has(side)) usedResults.add(side);
      else usedRaw.add(side);
    }
    const pair = pairKey(a, b);
    if (seenPairs.has(pair)) { problems.push(`recipe ${n} repeats the pair ${a} + ${b}`); return; }
    seenPairs.add(pair);
    if (typeof rid !== "string" || !/^[A-Za-z0-9_]{1,40}$/.test(rid)) { problems.push(`recipe ${n} has an invalid result_id`); return; }
    if (known.has(rid)) { problems.push(`recipe ${n} result_id ${rid} collides with an existing id`); return; }
    if (!rname) { problems.push(`recipe ${n} has no result_name`); return; }
    let short = pyStr("result_short" in r ? r.result_short : "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (short.length < 2 || short.length > 3) short = makeShort(rname);
    known.add(rid);
    results.set(rid, rname);
    recipes.push({ a, b, result_id: rid, result_name: rname, result_short: short });
  });

  const finals = [];
  const seenFinal = new Set();
  finalIn.forEach((f, i) => {
    const n = i + 1;
    const fid = isObj(f) ? f.id : undefined;
    const qty = isObj(f) ? f.qty : undefined;
    if (!known.has(fid)) { problems.push(`final_requires ${n} uses unknown id`); return; }
    if (seenFinal.has(fid)) { problems.push(`final_requires lists ${fid} twice`); return; }
    if (!Number.isInteger(qty) || qty < 1 || qty > L.max_qty) { problems.push(`final_requires ${n} has qty ${qty} (must be 1-${L.max_qty})`); return; }
    seenFinal.add(fid);
    if (results.has(fid)) usedResults.add(fid); else usedRaw.add(fid);
    finals.push({ id: fid, qty });
  });

  const orphans = [...results.keys()].filter((rid) => !usedResults.has(rid));
  if (orphans.length) problems.push("dead-end recipe result(s): " + orphans.join(", "));
  if (!usedRaw.size) problems.push("uses no raw materials");
  if (usedRaw.size > 8) problems.push(`uses ${usedRaw.size} raw materials (max 8)`);
  if (problems.length) return [null, problems];

  const slug = (s, re) => s.replace(re, "_").replace(/^_+|_+$/g, "").slice(0, 40);
  const ideaId = slug(("id" in idea ? pyStr(idea.id) : "").toLowerCase(), /[^a-z0-9_]+/g)
    || slug(title.toLowerCase(), /[^a-z0-9]+/g);
  return [{
    id: ideaId,
    title,
    pitch,
    uses_material_ids: [...usedRaw].sort(),
    recipes,
    final_requires: finals,
  }, []];
}

export function validateAndClean(data, materials) {
  const materialIds = materials.map((m) => m.id);
  const clean = [];
  const seenIds = new Set();
  const seenTitles = new Set();
  const raw = isObj(data) && Array.isArray(data.ideas) ? data.ideas : [];
  for (const item of raw) {
    let [idea, problems] = validateIdea(item, materialIds);
    if (idea) {
      if (seenTitles.has(idea.title.toLowerCase())) problems = ["duplicate title"];
      else {
        const base = idea.id;
        let k = 2;
        while (seenIds.has(idea.id)) idea.id = `${base}_${k++}`;
      }
    }
    if (problems.length) continue;
    seenIds.add(idea.id);
    seenTitles.add(idea.title.toLowerCase());
    clean.push(idea);
    if (clean.length >= L.max_ideas) break;
  }
  return clean;
}

export function cleanSteps(steps) {
  const out = [];
  for (const step of Array.isArray(steps) ? steps : []) {
    let text = cleanText(step, 400);
    text = text.replace(/^\s*(?:step\s*)?\d+\s*[.):\-]\s*/i, "").replace(/^[*\-• ]+/, "").trim();
    if (text) out.push(text);
  }
  return out.slice(0, 9);
}

export function cleanSourceSuggestions(data, requestedNames) {
  const allowed = new Map(requestedNames.map((name) => [name.toLowerCase(), name]));
  const out = [];
  const rows = isObj(data) && Array.isArray(data.suggestions) ? data.suggestions : [];
  for (const row of rows) {
    if (!isObj(row)) continue;
    const rawName = cleanText(row.material, 60);
    const canonical = allowed.get(rawName.toLowerCase());
    if (!canonical) continue;
    const places = [];
    for (const rawPlace of Array.isArray(row.places) ? row.places : []) {
      const place = cleanText(rawPlace, 100);
      if (place && !places.some((p) => p.toLowerCase() === place.toLowerCase())) places.push(place);
      if (places.length >= 4) break;
    }
    const tip = cleanText(row.salvage_tip, 240);
    const safety = cleanText(row.safety_note, 180);
    if (places.length) {
      out.push({ material: canonical, places, salvage_tip: tip, safety_note: safety });
    }
    if (out.length >= 12) break;
  }
  return out;
}

export function cleanSourceMaterials(incoming) {
  if (!Array.isArray(incoming)) return [];
  const out = [];
  for (const material of incoming.slice(0, 12)) {
    if (!isObj(material)) continue;
    const name = cleanText(material.name, 60);
    if (!name) continue;
    const safeQty = (field) => {
      const value = field in material ? material[field] : 0;
      const text = pyStr(value);
      return /^\d+$/.test(text) ? Math.min(99, Math.max(0, parseInt(text, 10))) : 0;
    };
    out.push({ name, needed: safeQty("needed"), have: safeQty("have"), missing: safeQty("missing") });
  }
  return out;
}

// Same cleanup server.py applies to the materials list before prompting.
export function cleanMaterials(materials) {
  if (!Array.isArray(materials)) return [];
  return materials
    .filter((m) => isObj(m) && m.id && m.name)
    .map((m) => {
      const q = pyStr("qty" in m ? m.qty : "");
      const qty = /^\d+$/.test(q.replace(/^-+/, "")) ? Math.max(0, parseInt(q, 10) || 0) : 1;
      return { id: cleanText(m.id, 60), name: cleanText(m.name, 60), qty };
    })
    .filter((m) => m.id && m.name);
}

// ---------------- Groq calls ----------------
export class ApiError extends Error {}

async function chatJson(env, system, user, name, schema, maxTokens, model) {
  model = model || env.GROQ_TEXT_MODEL || CFG.text_model;
  const body = {
    model,
    max_completion_tokens: maxTokens,
    messages: [{ role: "system", content: system }, { role: "user", content: user }],
    response_format: { type: "json_schema", json_schema: { name, schema } },
  };
  if (model.startsWith("openai/gpt-oss")) body.reasoning_effort = "low";
  else if (model.startsWith("qwen/")) body.reasoning_effort = "none";

  let res;
  try {
    res = await fetch((env.GROQ_BASE_URL || "https://api.groq.com/openai/v1") + "/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.GROQ_API_KEY}` },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError("Couldn't reach the Groq API. Try again in a moment.");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) throw new ApiError("The API key was rejected. Check the GROQ_API_KEY secret in the Cloudflare Worker settings.");
  if (res.status === 429) throw new ApiError("Rate limited by the API. Wait a moment and try again.");
  if (!res.ok) throw new ApiError(`API error (${res.status}): ${(data.error && data.error.message) || res.statusText}`);

  const choice = (data.choices || [])[0] || {};
  if (choice.finish_reason === "length") throw new ApiError("The model ran out of room before finishing. Try again.");
  const text = ((choice.message && choice.message.content) || "").trim();
  if (!text) throw new ApiError("The model returned an empty response. Try again.");
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new ApiError("Unexpected error: the model's reply was not valid JSON.");
  }
}

export async function generateIdeas(env, materials) {
  const user = "Materials on hand (id, name, quantity):\n" + JSON.stringify(materials, null, 2) +
    "\n\nPropose a catalog of buildable project ideas using these materials, following the schema.";
  const data = await chatJson(env, CFG.idea_system_prompt, user, "ideas", CFG.idea_schema, 6144);
  return validateAndClean(data, materials);
}

export async function generateSteps(env, brief) {
  const user = "Project:\n" + JSON.stringify(brief, null, 2) + "\n\nWrite the assembly steps, following the schema.";
  const data = await chatJson(env, CFG.steps_system_prompt, user, "steps", CFG.steps_schema, 3072);
  return cleanSteps(isObj(data) ? data.assembly_steps : []);
}

export async function generateSourceSuggestions(env, project, materials) {
  const brief = { project: cleanText(project, 80), materials };
  const user = "Suggest safe places to find these materials:\n" + JSON.stringify(brief, null, 2);
  const data = await chatJson(env, CFG.sources_system_prompt, user, "sources", CFG.sources_schema, 4096);
  return cleanSourceSuggestions(data, materials.map((m) => m.name));
}

export class BadImage extends Error {}

export async function identifyMaterial(env, dataUrl) {
  const m = /^data:([\w/.+-]+);base64,(.+)$/s.exec(typeof dataUrl === "string" ? dataUrl : "");
  if (!m) throw new BadImage("Image must be a base64 data URL.");
  const mediaType = m[1].toLowerCase();
  const imageData = m[2];
  if (!L.allowed_image_types.includes(mediaType)) throw new BadImage("Unsupported image type. Use JPEG, PNG, GIF or WebP.");
  if (imageData.length > L.max_image_b64_chars) throw new BadImage("That photo is too large. Try again with a smaller capture.");

  const data = await chatJson(env, CFG.identify_system_prompt, [
    { type: "image_url", image_url: { url: `data:${mediaType};base64,${imageData}` } },
    { type: "text", text: "What is this?" },
  ], "material", CFG.identify_schema, 512, env.GROQ_VISION_MODEL || CFG.vision_model);
  const name = cleanText(isObj(data) ? data.name : "", 60) || "unclear item";
  const confidence = ["low", "medium", "high"].includes(data && data.confidence) ? data.confidence : "low";
  return { name, confidence };
}

export const MAX_BODY_BYTES = L.max_body_bytes;
