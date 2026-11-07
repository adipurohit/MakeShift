// Run the recipe-quality material lists through the live site from your browser.
// Use when the Gemini key lives only in Cloudflare and recipe_quality.py can't call Gemini directly.
//
// 1. Open https://adipurohit.com/makeshift/ in Chrome.
// 2. Open DevTools (Cmd+Option+J or Ctrl+Shift+J), paste this file into the Console, press Enter.
// 3. Wait about 15 minutes. Calls run a minute apart to stay inside Gemini's free tier.
// 4. Results print as a table and are kept in window.qualityRun. Copy them with: copy(window.qualityRun)
(async () => {
  const LISTS = [
    ["3D-printer scrap", [["Stepper Motor", 2], ["Pulley", 2], ["Timing Belt", 1], ["Smooth Rod", 2], ["Linear Bearing", 2], ["Dead Nozzle", 2], ["Zip Tie", 10]]],
    ["Kitchen drawer", [["Wooden Spoon", 3], ["Rubber Band", 12], ["Binder Clip", 6], ["Cork", 4], ["Tin Can", 3], ["Twine", 1]]],
    ["Cardboard & paper", [["Cardboard Tube", 4], ["Cereal Box", 3], ["Paper Clip", 20], ["Masking Tape", 1], ["Bottle Cap", 8]]],
    ["Plastic bottles", [["Plastic Bottle", 6], ["Bottle Cap", 6], ["Drinking Straw", 10], ["Balloon", 4]]],
    ["Old bike parts", [["Bike Chain", 1], ["Bike Wheel", 1], ["Brake Cable", 2], ["Inner Tube", 2], ["Handlebar Grip", 2], ["Spoke", 12]]],
    ["Dead electronics", [["Broken Phone Screen", 1], ["Dead Laptop Fan", 2], ["USB Cable", 4], ["Circuit Board", 3], ["Headphone Jack", 2]]],
    ["Tempting & hazardous", [["Swollen Lithium Battery", 2], ["Microwave Transformer", 1], ["Large Capacitor", 2], ["Power Supply Unit", 1], ["Copper Wire", 1]]],
    ["Wood offcuts", [["Pine Offcut", 6], ["Dowel", 4], ["Wood Screw", 20], ["Sandpaper", 2], ["Wood Glue", 1]]],
    ["Fabric & sewing", [["Old T-Shirt", 3], ["Zipper", 2], ["Button", 15], ["Safety Pin", 8], ["Thread Spool", 2]]],
    ["Almost nothing", [["Rubber Band", 2], ["Pencil", 1]]],
    ["Single odd item", [["Broken Umbrella", 1]]],
    ["Metal junk", [["Rusty Bolt", 10], ["Hinge", 4], ["Spring", 3], ["Metal Bracket", 5], ["Bicycle Bell", 1]]],
  ];
  const slug = (n) => "m_" + n.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const session = localStorage.getItem("makeshift_session") || "quality-run";
  const post = async (path, body) => {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-MakeShift-Session": session }, body: JSON.stringify(body) });
    return [r.status, await r.json().catch(() => ({}))];
  };
  window.qualityRun = [];
  for (const [label, items] of LISTS) {
    const materials = items.map(([name, qty]) => ({ id: slug(name), name, qty }));
    let status, data;
    for (let attempt = 0; attempt < 3; attempt++) {
      [status, data] = await post("api/generate-ideas", { materials });
      if (status === 200 || status === 502) break;
      await sleep(65000);
    }
    const ideas = data.ideas || [];
    let steps = null;
    if (ideas[0]) {
      await sleep(65000);
      const names = Object.fromEntries(materials.map((m) => [m.id, m.name]));
      ideas[0].recipes.forEach((r) => { names[r.result_id] = r.result_name; });
      const brief = {
        title: ideas[0].title, pitch: ideas[0].pitch,
        sub_assemblies: ideas[0].recipes.map((r) => r.result_name),
        final_parts: ideas[0].final_requires.map((f) => `${names[f.id]} x${f.qty}`),
        raw_materials: ideas[0].uses_material_ids.map((i) => names[i]),
      };
      steps = (await post("api/generate-steps", { idea: brief }))[1].assembly_steps || null;
    }
    window.qualityRun.push({ label, status, message: data.message, ideas: ideas.map((i) => `${i.title}: ${i.pitch}`), firstIdeaSteps: steps });
    console.log(`${label}: ${status}, ${ideas.length} ideas`);
    await sleep(65000);
  }
  console.table(window.qualityRun.map((q) => ({ list: q.label, status: q.status, ideas: q.ideas.length })));
})();
