/* ---------------------------------------------------------------
   Part categories: one keyword classifier drives both the 2D icons
   (TASKS.md #2) and the 3D shapes (TASKS.md #3), so a "Stepper Motor"
   looks like a motor in the inventory, the palette, the bench and the
   3D viewer. Works on any name, including AI-generated and scanned ones.
   --------------------------------------------------------------- */

import * as THREE from "three";

// First match wins, so more specific keywords sit above generic ones.
const RULES = [
  ["power",    /power supply|\bpsu\b|battery|batteries|charger|adapter|power bank/],
  ["board",     /control board|circuit board|amp board|\bpcb\b|circuit|arduino|raspberry|controller|microcontroller|\bchip\b|\bmodule\b|transistor|keyboard/],
  ["sensor",    /sensor|endstop|thermistor|photocell/],
  ["light",     /\bled\b|light|lamp|bulb|lantern|flashlight/],
  ["speaker",   /speaker|buzzer|microphone|headphone/],
  ["fan",       /\bfan\b|propeller|impeller/],
  ["pump",      /pump|syringe|valve/],
  ["switch",    /switch|button|toggle/],
  ["gripper",   /grip|claw|pincer|tong/],
  ["joint",     /joint|hinge|pivot|elbow|shoulder/],
  ["motor",     /motor|servo|stepper|drive unit/],
  ["wheel",     /wheel|tire|tyre|caster|roller/],
  ["pulley",    /pulley|gear|sprocket|cog/],
  ["belt",      /belt|rubber band|elastic|strap|inner tube|velcro/],
  ["spring",    /spring|coil/],
  ["bearing",   /bearing|bushing|\bring\b|washer/],
  ["nozzle",    /nozzle|hotend|hot end|funnel/],
  ["rail",      /extrusion|rail|beam|segment|\barm\b|frame|bracket|profile|\bbar\b|ruler/],
  ["disc",      /bottle cap|\blid\b|washer|magnet|\bcoin\b|\bcd\b|paper plate/],
  ["ball",      /balloon|marble|\bball\b|potato/],
  ["granular",  /dry rice|\brice\b|\bsand\b|gravel/],
  ["rod",       /\brod\b|shaft|dowel|axle|pipe|tube|straw|pencil|stick|skewer|marker|cork/],
  ["wire",      /wire|cable|cord|string|rope|twine|thread|yarn|hose|tubing|hanger/],
  ["fastener",  /zip tie|cable tie|screw|bolt|\bnut\b|\bnail|clip|clamp|tape|glue|rivet|pin\b|magnet/],
  ["tool",      /wrench|spanner|screwdriver|hammer|pliers|drill|saw|scissor|toothbrush|\bkey\b|spoon/],
  ["sheet",     /cardboard|paper|plywood|\bwood|acrylic|sheet|panel|plate|board|foam|card\b|foil|mirror|screen mesh/],
  ["container", /bottle|\bcan\b|\bjar\b|\bbox\b|\bcup\b|container|tin\b|tub\b|carton|tray|bucket|plant pot/],
  ["fabric",    /fabric|cloth|cotton|felt|denim|t-shirt|sock|towel|tarp|plastic bag|plastic wrap/],
];

export function categoryFor(item) {
  const name = (item && item.name ? item.name : "").toLowerCase();
  for (const [cat, re] of RULES) if (re.test(name)) return cat;
  return item && item.raw === false ? "assembly" : "generic";
}

/* ---------------- 2D icons (24x24, stroke-only, white on the item color) ---------------- */
const ICON_PATHS = {
  motor:     '<rect x="5" y="8" width="11" height="11" rx="2"/><path d="M16 13.5h4M10.5 8V5M8 12h5M8 15h5"/>',
  pulley:    '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2"/>',
  belt:      '<rect x="3" y="7" width="18" height="10" rx="5"/><path d="M7 7v10M11 7v10M15 7v10"/>',
  bearing:   '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><circle cx="12" cy="6" r=".9"/><circle cx="12" cy="18" r=".9"/><circle cx="6" cy="12" r=".9"/><circle cx="18" cy="12" r=".9"/>',
  nozzle:    '<path d="M8 4h8v5H8zM9 9l2.2 8h1.6L15 9M12 17v3"/>',
  rail:      '<rect x="3" y="9" width="18" height="6" rx="1"/><path d="M3 12h18M7 9v6M17 9v6"/>',
  rod:       '<path d="M4 18L18 4"/><path d="M6 20L20 6"/><path d="M4 18l2 2M18 4l2 2"/>',
  wire:      '<path d="M3 15c3 0 3-6 6-6s3 6 6 6 3-6 6-6"/><path d="M3 15v3M21 9V6"/>',
  fastener:  '<path d="M9 4h6v3H9zM12 7v13M10 10h4M10 13h4M10 16h4"/>',
  board:     '<rect x="3" y="5" width="18" height="14" rx="1.5"/><rect x="9" y="9" width="6" height="6"/><path d="M6 8h1M6 12h1M6 16h1M17 8h1M17 12h1M17 16h1"/>',
  power:     '<rect x="4" y="7" width="14" height="12" rx="1.5"/><path d="M18 11h2v4h-2M12 9l-3 5h4l-3 5"/>',
  light:     '<path d="M9 15h6M10 18h4"/><path d="M8 12a6 6 0 1 1 8 0c-1 .8-1 1.5-1 3H9c0-1.5 0-2.2-1-3z"/>',
  speaker:   '<rect x="5" y="3" width="14" height="18" rx="2"/><circle cx="12" cy="14" r="4"/><circle cx="12" cy="7" r="1.5"/>',
  fan:       '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 10c-1-5 5-5 4-1-.5 2-2 3-4 3M14 12c5-1 5 5 1 4-2-.5-3-2-3-4M12 14c1 5-5 5-4 1 .5-2 2-3 4-3"/>',
  pump:      '<rect x="5" y="7" width="11" height="12" rx="2"/><path d="M16 11h4v5h-4M8 7V4h5v3"/>',
  sensor:    '<rect x="5" y="5" width="14" height="14" rx="2"/><circle cx="12" cy="12" r="3"/><path d="M2 12h3M19 12h3"/>',
  switch:    '<rect x="4" y="12" width="16" height="7" rx="1.5"/><path d="M12 12l5-7"/><circle cx="17" cy="5" r="1.2"/>',
  sheet:     '<path d="M4 8l8-4 8 4-8 4z"/><path d="M4 8v4l8 4 8-4V8"/>',
  container: '<path d="M7 7h10l-1 13H8z"/><path d="M6 4h12v3H6z"/>',
  fabric:    '<path d="M4 6c3-2 5 2 8 0s5-2 8 0v12c-3-2-5 2-8 0s-5-2-8 0z"/>',
  gripper:   '<path d="M12 3v6M12 9l-5 5v6M12 9l5 5v6M7 20h2M15 20h2"/>',
  joint:     '<circle cx="9" cy="15" r="4"/><circle cx="9" cy="15" r="1.2"/><path d="M12 12l7-7M17 5h2v2"/>',
  wheel:     '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 4v6M12 14v6M4 12h6M14 12h6"/>',
  spring:    '<path d="M7 4h10M7 20h10M9 4c8 2-2 4 6 6s-2 4 0 6-6 2-6 4"/>',
  tool:      '<path d="M14 5a4 4 0 0 0-5 5L3 16l5 5 6-6a4 4 0 0 0 5-5l-3 3-3-3z"/>',
  disc:      '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M6 8h12M6 16h12"/>',
  ball:      '<circle cx="12" cy="12" r="8"/><path d="M5 9c4 2 10 2 14 0M8 19c3-4 3-10 0-14"/>',
  granular:  '<path d="M4 18c1-6 4-9 8-9s7 3 8 9z"/><circle cx="9" cy="14" r=".8"/><circle cx="13" cy="12" r=".8"/><circle cx="16" cy="15" r=".8"/>',
  assembly:  '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  generic:   '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M5 10h14M10 10v9"/>',
};

export function iconSvg(item) {
  const body = ICON_PATHS[categoryFor(item)] || ICON_PATHS.generic;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

/* ---------------- 3D shapes (primitive composites, merged into one geometry) ----------------
   One BufferGeometry per part keeps the existing raycast/drag/hologram code
   working unchanged (it expects a single Mesh). Each shape is built from a
   few primitives, merged, then lifted so its base sits on the ground plane. */
const geometryCache = new Map();

function piece(geo, { x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0 } = {}) {
  const m = new THREE.Matrix4().compose(
    new THREE.Vector3(x, y, z),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz)),
    new THREE.Vector3(1, 1, 1)
  );
  const g = (geo.index ? geo.toNonIndexed() : geo.clone()).applyMatrix4(m);
  geo.dispose();
  return g;
}

function merge(pieces) {
  let count = 0;
  pieces.forEach((g) => { count += g.attributes.position.count; });
  const pos = new Float32Array(count * 3);
  const nrm = new Float32Array(count * 3);
  let off = 0;
  pieces.forEach((g) => {
    pos.set(g.attributes.position.array, off * 3);
    nrm.set(g.attributes.normal.array, off * 3);
    off += g.attributes.position.count;
    g.dispose();
  });
  const out = new THREE.BufferGeometry();
  out.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  out.setAttribute("normal", new THREE.BufferAttribute(nrm, 3));
  // Sit on the ground: the caller places meshes at y=0.4, so base goes to -0.4.
  out.computeBoundingBox();
  const bb = out.boundingBox;
  out.translate(-(bb.min.x + bb.max.x) / 2, -0.4 - bb.min.y, -(bb.min.z + bb.max.z) / 2);
  out.computeBoundingSphere();
  return out;
}

const HALF_PI = Math.PI / 2;
const BUILDERS = {
  motor: () => [
    piece(new THREE.BoxGeometry(0.6, 0.55, 0.6)),
    piece(new THREE.CylinderGeometry(0.06, 0.06, 0.3, 12), { y: 0.42 }),
    piece(new THREE.CylinderGeometry(0.16, 0.16, 0.06, 20), { y: 0.3 }),
  ],
  pulley: () => [
    piece(new THREE.CylinderGeometry(0.38, 0.38, 0.08, 28), { y: 0.0 }),
    piece(new THREE.CylinderGeometry(0.3, 0.3, 0.16, 28), { y: 0.12 }),
    piece(new THREE.CylinderGeometry(0.38, 0.38, 0.08, 28), { y: 0.24 }),
  ],
  belt: () => [piece(new THREE.TorusGeometry(0.42, 0.05, 8, 40), { rx: HALF_PI })],
  bearing: () => [
    piece(new THREE.TorusGeometry(0.28, 0.1, 12, 28)),
    piece(new THREE.CylinderGeometry(0.17, 0.17, 0.22, 20), { rx: HALF_PI }),
  ],
  nozzle: () => [
    piece(new THREE.BoxGeometry(0.34, 0.24, 0.34), { y: 0.38 }),
    piece(new THREE.CylinderGeometry(0.1, 0.1, 0.18, 12), { y: 0.17 }),
    piece(new THREE.ConeGeometry(0.14, 0.22, 16), { y: -0.03, rx: Math.PI }),
  ],
  rail: () => [
    piece(new THREE.BoxGeometry(1.05, 0.2, 0.2)),
    piece(new THREE.BoxGeometry(1.05, 0.06, 0.06), { y: 0.13 }),
  ],
  rod: () => [piece(new THREE.CylinderGeometry(0.07, 0.07, 1.05, 16), { rz: HALF_PI })],
  wire: () => [piece(new THREE.TorusKnotGeometry(0.22, 0.04, 80, 8, 2, 5), { rx: HALF_PI })],
  fastener: () => [
    piece(new THREE.CylinderGeometry(0.16, 0.16, 0.08, 6), { y: 0.3 }),
    piece(new THREE.CylinderGeometry(0.06, 0.06, 0.55, 12)),
  ],
  board: () => [
    piece(new THREE.BoxGeometry(0.85, 0.05, 0.6)),
    piece(new THREE.BoxGeometry(0.22, 0.07, 0.22), { y: 0.06 }),
    piece(new THREE.BoxGeometry(0.12, 0.08, 0.3), { x: 0.28, y: 0.06 }),
    piece(new THREE.BoxGeometry(0.12, 0.08, 0.3), { x: -0.28, y: 0.06 }),
  ],
  power: () => [
    piece(new THREE.BoxGeometry(0.75, 0.38, 0.5)),
    piece(new THREE.CylinderGeometry(0.08, 0.08, 0.1, 16), { x: 0.42, rz: HALF_PI }),
  ],
  light: () => [
    piece(new THREE.SphereGeometry(0.26, 20, 14), { y: 0.22 }),
    piece(new THREE.CylinderGeometry(0.14, 0.18, 0.2, 16), { y: -0.08 }),
  ],
  speaker: () => [
    piece(new THREE.BoxGeometry(0.6, 0.8, 0.35)),
    piece(new THREE.CylinderGeometry(0.22, 0.22, 0.05, 24), { z: 0.2, rx: HALF_PI }),
    piece(new THREE.CylinderGeometry(0.08, 0.08, 0.05, 16), { y: 0.25, z: 0.2, rx: HALF_PI }),
  ],
  fan: () => [
    piece(new THREE.TorusGeometry(0.36, 0.05, 10, 30), { rx: HALF_PI }),
    piece(new THREE.CylinderGeometry(0.09, 0.09, 0.18, 16), { rx: HALF_PI }),
    ...[0, 1, 2, 3].map((i) => piece(new THREE.BoxGeometry(0.08, 0.38, 0.04), { rz: i * HALF_PI, z: 0.02 })),
  ],
  pump: () => [
    piece(new THREE.CylinderGeometry(0.24, 0.24, 0.5, 20)),
    piece(new THREE.CylinderGeometry(0.08, 0.08, 0.3, 12), { x: 0.27, rz: HALF_PI }),
  ],
  sensor: () => [
    piece(new THREE.BoxGeometry(0.42, 0.12, 0.32)),
    piece(new THREE.CylinderGeometry(0.1, 0.1, 0.12, 16), { y: 0.12 }),
  ],
  switch: () => [
    piece(new THREE.BoxGeometry(0.42, 0.2, 0.2)),
    piece(new THREE.BoxGeometry(0.36, 0.03, 0.08), { x: 0.05, y: 0.16, rz: -0.25 }),
  ],
  sheet: () => [piece(new THREE.BoxGeometry(0.9, 0.06, 0.7))],
  container: () => [
    piece(new THREE.CylinderGeometry(0.24, 0.26, 0.6, 24)),
    piece(new THREE.CylinderGeometry(0.11, 0.11, 0.12, 16), { y: 0.36 }),
  ],
  fabric: () => [
    piece(new THREE.BoxGeometry(0.8, 0.04, 0.6)),
    piece(new THREE.BoxGeometry(0.8, 0.04, 0.5), { y: 0.06, ry: 0.25 }),
  ],
  gripper: () => [
    piece(new THREE.BoxGeometry(0.4, 0.14, 0.2), { y: 0.5 }),
    piece(new THREE.BoxGeometry(0.06, 0.55, 0.12), { x: -0.16, y: 0.18, rz: -0.2 }),
    piece(new THREE.BoxGeometry(0.06, 0.55, 0.12), { x: 0.16, y: 0.18, rz: 0.2 }),
  ],
  joint: () => [
    piece(new THREE.CylinderGeometry(0.3, 0.3, 0.3, 24)),
    piece(new THREE.BoxGeometry(0.7, 0.12, 0.16), { x: 0.4, y: 0.22 }),
    piece(new THREE.CylinderGeometry(0.07, 0.07, 0.2, 12), { y: 0.25 }),
  ],
  wheel: () => [
    piece(new THREE.TorusGeometry(0.34, 0.1, 12, 28), { rx: HALF_PI }),
    piece(new THREE.CylinderGeometry(0.1, 0.1, 0.22, 16), { rx: HALF_PI }),
  ],
  spring: () => [piece(new THREE.TorusKnotGeometry(0.22, 0.045, 96, 8, 2, 9), { rz: HALF_PI })],
  tool: () => [
    piece(new THREE.BoxGeometry(0.16, 0.16, 0.75), { rz: -0.55 }),
    piece(new THREE.TorusGeometry(0.2, 0.06, 8, 18, Math.PI * 1.35), { x: 0.26, y: 0.3, rz: -0.55 }),
  ],
  disc: () => [
    piece(new THREE.CylinderGeometry(0.38, 0.38, 0.08, 28)),
    piece(new THREE.CylinderGeometry(0.09, 0.09, 0.12, 18), { y: 0.05 }),
  ],
  ball: () => [piece(new THREE.SphereGeometry(0.4, 22, 16))],
  granular: () => [
    piece(new THREE.SphereGeometry(0.22, 12, 8), { x: -0.2 }),
    piece(new THREE.SphereGeometry(0.25, 12, 8), { x: 0.12, z: 0.08 }),
    piece(new THREE.SphereGeometry(0.18, 12, 8), { x: 0.28, z: -0.18 }),
  ],
  assembly: () => [piece(new THREE.DodecahedronGeometry(0.45, 0))],
  generic: () => [piece(new THREE.BoxGeometry(0.65, 0.65, 0.65))],
};

// Returns a shared geometry per category. Callers must not dispose it.
export function partGeometry(item) {
  const cat = categoryFor(item);
  if (!geometryCache.has(cat)) geometryCache.set(cat, merge((BUILDERS[cat] || BUILDERS.generic)()));
  return geometryCache.get(cat);
}

const SOURCE_HINTS = {
  power: { places: ["Certified e-waste or electronics reuse center", "Computer repair shop parts bin", "Maker space donation shelf"], tip: "Reuse only intact, labeled low-voltage adapters; do not open mains power supplies or damaged batteries." },
  board: { places: ["Electronics repair shop scrap bin", "Certified e-waste collection", "Maker space spare-parts shelf"], tip: "Look in discarded printers, toys, or hobby kits and choose clean boards without corrosion or swollen components." },
  motor: { places: ["Printer or appliance repair shop", "Certified e-waste collection", "Broken toy or small appliance you own"], tip: "Printers, scanners, fans, and toys often contain small motors; avoid mains appliances unless a qualified adult removes the part." },
  fan: { places: ["Computer repair shop", "Certified e-waste collection", "Old desktop computer you own"], tip: "PC cases and network equipment often contain low-voltage fans; inspect the cable and blades for damage." },
  light: { places: ["Bicycle or electronics repair shop", "Maker space parts shelf", "Broken low-voltage light you own"], tip: "Choose intact low-voltage LEDs or lamp modules and avoid opening mains-powered bulbs." },
  speaker: { places: ["Electronics repair shop", "Certified e-waste collection", "Broken radio or toy you own"], tip: "Small radios, toys, and headphones may contain speakers; check that the cone and wires are intact." },
  sheet: { places: ["Your clean recycling", "Framing or cabinet shop offcut bin", "Community reuse center"], tip: "Shipping boxes, signs, and clean offcuts are useful; avoid wet, moldy, or chemically treated material." },
  rod: { places: ["Hardware-store offcut bin", "Bike or appliance repair shop", "Community workshop scrap rack"], tip: "Old shelving, furniture, and broken tools may yield straight rods or tubes; cover sharp cut ends." },
  wire: { places: ["Electronics repair shop offcuts", "Maker space scrap wire bin", "Certified e-waste collection"], tip: "Use clean insulated low-voltage wire and reject brittle, scorched, or unknown mains cable." },
  container: { places: ["Your clean recycling", "Thrift store housewares", "Restaurant or café with permission"], tip: "Choose clean food-safe containers; wash them and never reuse chemical or pressurized containers." },
  fabric: { places: ["Old clothing or linens you own", "Thrift store textile section", "Community fabric-swap bin"], tip: "Choose clean, dry fabric and wash it before cutting." },
  generic: { places: ["Community reuse center", "Maker space donation shelf", "Local repair shop scrap bin"], tip: "Bring a photo or dimensions, ask permission, and inspect the part for damage before taking it." },
};

// Donor objects: the discarded things that usually contain a specific part, and how to get it out.
// Checked before the broad category hints above, first match wins, so specific parts sit first.
const PART_DONORS = [
  [/stepper/, ["Dead inkjet or laser printer (paper-feed motor)", "Old flatbed scanner (carriage motor)", "Broken 3D printer from a school or maker space"], "Unplug the 4-wire connector at the board, then remove the 2-4 screws on the motor face. Spin the shaft by hand: it should step evenly with no grinding."],
  [/servo/, ["Broken RC car or plane", "Old robot or hobby kit", "Maker space spares drawer"], "Servos unscrew from their mount and unplug from a 3-pin header. Turn the horn gently; a stripped servo slips or clicks."],
  [/vibration motor/, ["Dead phone or game controller", "Broken electric toothbrush (sealed battery removed first)", "Pager-style toys"], "The coin-shaped motor is glued near the case edge; pry it off with a plastic tool and keep its two thin wires."],
  [/\bfan\b/, ["Old desktop PC (case fans)", "Dead laptop (small blower fan)", "Broken game console"], "PC case fans come off with 4 screws and a 3- or 4-pin plug. Never take the fan out of a power supply box."],
  [/motor/, ["Broken toy car or remote-control toy", "Dead cordless (not corded) handheld fan", "Old CD or DVD drive (tray motor)"], "Small DC motors are held by 2 screws or a clip. Check the shaft turns freely and the two terminals are not snapped off."],
  [/timing belt|\bbelt\b/, ["Dead inkjet printer (carriage belt)", "Old flatbed scanner", "Broken 3D printer"], "Loosen the idler or tensioner screw first so the belt slides off without stretching. Look for missing teeth and cracks."],
  [/pulley|gear|sprocket/, ["Dead printer or scanner", "Broken VCR or cassette deck", "Old wind-up or motorized toy"], "Most pulleys and gears press onto a shaft or use a tiny set screw; a 1.5 mm hex key fits many. Check teeth are not worn flat."],
  [/smooth rod|linear rod|steel rod/, ["Dead inkjet printer (carriage rod)", "Old flatbed scanner", "Broken 3D printer"], "Rods sit in clips or end brackets; pop the clips and slide the rod out. Roll it on a table to check it is straight."],
  [/bearing/, ["Worn skateboard or inline-skate wheels (608 bearings)", "Dead printer or scanner carriage", "Broken fidget spinner"], "Push the bearing out with a bolt as a punch. It should spin quietly; grinding means grit or rust."],
  [/extrusion/, ["Broken 3D printer frame", "Old display stand or trade-show rig", "Maker space offcut rack"], "Frame corners use T-nuts and hex bolts; loosen, slide the corner bracket off, and keep the T-nuts."],
  [/nozzle/, ["Clogged 3D printer spares bag", "Maker space nozzle jar"], "Only remove a nozzle from a cold printer. Keep them in a jar; the tips are small and sharp."],
  [/limit switch|endstop|micro ?switch/, ["Broken 3D printer", "Old computer mouse (click switches)", "Dead arcade or game controller"], "Endstops come off with 2 small screws and a plug. Press the lever: you should hear a clean click."],
  [/control board|\barduino\b|microcontroller/, ["Broken 3D printer or CNC kit", "School robotics kit leftovers", "Maker space donation shelf"], "Unplug every connector and photograph the wiring first. Skip boards with burnt spots or bulging capacitors."],
  [/power supply|\bpsu\b|adapter/, ["Old router, modem or LED strip with a sealed wall adapter", "Electronics reuse center", "Your own drawer of unused chargers"], "Use only sealed plug-in adapters with a printed voltage label. Never open a power supply box or a mains appliance."],
  [/power bank/, ["Your own drawer of old chargers", "Electronics reuse center"], "Use only power banks that are not swollen, cracked or hot. Recycle damaged ones at an e-waste point; don't open them."],
  [/coin cell/, ["Dead car-key fob or bathroom scale", "Old calculator or motherboard"], "Coin cells slide out sideways. Keep them away from small children; they are a serious swallowing hazard."],
  [/battery holder/, ["Broken battery-powered toy or flashlight", "Old remote control"], "Desolder or cut the holder's two wires close to the old board, then strip 5 mm of insulation."],
  [/\bled\b|led strip/, ["Broken battery toy or bike light", "Old electronics with indicator lights", "Leftover LED strip from a room makeover"], "Snip LEDs with their legs as long as possible. The longer leg is plus. Cut LED strips only on the marked copper pads."],
  [/speaker/, ["Broken radio, toy or laptop", "Old computer speakers", "Dead headphones"], "Speakers unscrew from the case; cut the two wires near the old board. Press the cone gently: it should move without scraping."],
  [/magnet/, ["Dead hard drive (very strong, pinch hazard)", "Old fridge magnets or cabinet latches", "Broken toys"], "Hard-drive magnets snap together hard enough to pinch skin; slide them apart sideways and keep them away from phones and cards."],
  [/spring/, ["Broken retractable pen", "Old mattress or chair mechanism", "Clothespins and binder clips"], "Springs store energy. Point them away from your face when removing, and wear glasses for anything bigger than a pen spring."],
  [/usb cable|cable/, ["Your drawer of old phone cables", "Electronics reuse center"], "Cut the plug end off a USB cable and strip it: red is 5V, black is ground. Check the outer jacket is not split."],
  [/solar/, ["Broken solar garden light", "Old solar calculator"], "Garden-light panels lift out of the lid with 2-4 small screws; keep the wires attached and test in sunlight."],
  [/mirror|lens|\bcd\b/, ["Old makeup compact or bathroom mirror tile", "Broken flashlight or magnifier", "Scratched CDs and DVDs"], "Tape over glass mirrors before cutting or snapping, and wear gloves. Avoid cracked glass entirely."],
  [/cardboard|cereal box|shoe box|pizza box/, ["Your own clean recycling", "Grocery or appliance store box pile (ask first)"], "Pick dry, unprinted-inside boxes. Corrugated board is stiffer along the flutes, so cut with the flutes running the long way."],
  [/bottle cap|\bcap\b/, ["Your own recycling", "Café or school collection jar (ask first)"], "Wash caps in warm soapy water and let them dry before gluing."],
  [/plastic bottle|bottle/, ["Your own recycling", "School or office recycling bin (ask first)"], "Rinse and dry. Clear PET bottles cut cleanly with scissors after a starter slit from a craft knife."],
  [/jar|\blid\b/, ["Your own kitchen recycling", "Thrift store housewares"], "Soak off labels in warm water. Check the rim for chips before handling."],
  [/tin can|\bcan\b/, ["Your own kitchen recycling"], "Use a safety can opener that leaves a smooth edge, and file or tape any sharp rim."],
  [/cork/, ["Restaurant or wine bar (they often save them)", "Your own kitchen"], "Natural cork cuts with a serrated knife; synthetic corks are rubbery and don't slice cleanly."],
  [/dowel|popsicle|chopstick|skewer/, ["Broken chair rungs or old roller blinds", "Takeout chopsticks", "Craft store scrap bin"], "Check the grain runs straight along the stick; diagonal grain snaps under load."],
  [/pallet|plank|scrap wood|offcut|\bwood\b/, ["Pallets marked HT (heat treated) from a store's loading dock (ask first)", "Cabinet or framing shop offcut bin", "Community workshop scrap rack"], "Avoid pallets stamped MB (chemically treated). Pull every nail and staple before cutting or sanding."],
  [/pvc|pipe/, ["Plumber or renovation offcuts (ask first)", "Community reuse center"], "Use a hacksaw and sand the cut edge. Skip pipe that held chemicals or has an unknown residue."],
  [/hose|tubing/, ["Leaky garden hose", "Old aquarium setup"], "Cut out the split section and keep the clean lengths; rinse inside before reuse."],
  [/rubber band|elastic|inner tube/, ["Produce bands from the grocery store", "Punctured bike inner tube from a bike shop (they bin them daily)"], "Bike shops usually give away punctured tubes free. Cut rings for heavy-duty bands."],
  [/zip tie|binder clip|clothespin|paper clip|hanger/, ["Office supply drawer", "Dry cleaner (wire hangers)", "Your own junk drawer"], "Wire hangers straighten with pliers; wear eye protection when bending the cut ends."],
  [/t-shirt|tshirt|jeans|denim|fabric|felt|sock|towel/, ["Your own worn-out clothes", "Thrift store rag bin", "Community fabric-swap bin"], "Wash first. Jersey t-shirt fabric curls when cut, which makes clean, no-sew cord."],
  [/egg carton|paper towel tube|cardboard tube|toilet roll/, ["Your own recycling"], "Paper egg cartons are compostable seed trays; foam ones are better for paint palettes."],
  [/hinge|bracket|caster|bolt|screw|nail|washer/, ["Broken furniture or cabinet doors", "Community reuse center hardware bins", "Hardware store bulk bin (last resort)"], "Keep fasteners in a labeled jar per size; rusty screws often still work once wire-brushed."],
  [/phone|keyboard|laptop|circuit board/, ["Your own dead devices", "Certified e-waste drop-off"], "Remove or tape over any battery before taking a device apart, and never puncture a lithium battery."],
];

export function sourceHintsFor(item) {
  const name = (item && item.name ? item.name : "").toLowerCase();
  const donor = PART_DONORS.find(([re]) => re.test(name));
  if (donor) return { places: donor[1], tip: donor[2], donor: true };
  return SOURCE_HINTS[categoryFor(item)] || SOURCE_HINTS.generic;
}

// A final-project silhouette is separate from the loose-part geometry. It gives
// the hologram a visual goal instead of making every requirement look like an
// unrelated object floating in space.
const projectGeometryCache = new Map();
const PROJECT_BUILDERS = {
  robotics: () => [
    piece(new THREE.CylinderGeometry(0.48, 0.58, 0.2, 24)),
    piece(new THREE.CylinderGeometry(0.2, 0.2, 0.25, 20), { y: 0.22 }),
    piece(new THREE.BoxGeometry(0.18, 0.9, 0.2), { x: 0.28, y: 0.65, rz: -0.55 }),
    piece(new THREE.CylinderGeometry(0.18, 0.18, 0.24, 20), { x: 0.53, y: 1.02, rz: HALF_PI }),
    piece(new THREE.BoxGeometry(0.16, 0.75, 0.18), { x: 0.75, y: 1.28, rz: 0.35 }),
    piece(new THREE.BoxGeometry(0.05, 0.35, 0.12), { x: 0.7, y: 1.68, rz: -0.28 }),
    piece(new THREE.BoxGeometry(0.05, 0.35, 0.12), { x: 0.9, y: 1.68, rz: 0.28 }),
  ],
  lighting: () => [
    piece(new THREE.CylinderGeometry(0.42, 0.52, 0.14, 24)),
    piece(new THREE.CylinderGeometry(0.06, 0.06, 1.25, 14), { y: 0.65 }),
    piece(new THREE.ConeGeometry(0.48, 0.55, 24, 1, true), { y: 1.34, rx: Math.PI }),
    piece(new THREE.SphereGeometry(0.18, 18, 12), { y: 1.2 }),
  ],
  garden: () => [
    piece(new THREE.CylinderGeometry(0.42, 0.32, 0.65, 24)),
    piece(new THREE.CylinderGeometry(0.04, 0.04, 0.8, 10), { y: 0.62 }),
    piece(new THREE.SphereGeometry(0.28, 14, 10), { x: -0.2, y: 0.92 }),
    piece(new THREE.SphereGeometry(0.25, 14, 10), { x: 0.22, y: 1.08 }),
  ],
  "home & desk": () => [
    piece(new THREE.BoxGeometry(1.0, 0.1, 0.75)),
    piece(new THREE.BoxGeometry(0.12, 0.8, 0.12), { x: -0.42, y: 0.4, z: -0.28 }),
    piece(new THREE.BoxGeometry(0.12, 0.8, 0.12), { x: 0.42, y: 0.4, z: -0.28 }),
    piece(new THREE.BoxGeometry(0.12, 0.8, 0.12), { x: -0.42, y: 0.4, z: 0.28 }),
    piece(new THREE.BoxGeometry(0.12, 0.8, 0.12), { x: 0.42, y: 0.4, z: 0.28 }),
  ],
  storage: () => [
    piece(new THREE.BoxGeometry(1.0, 0.08, 0.7)),
    piece(new THREE.BoxGeometry(1.0, 0.55, 0.08), { y: 0.28, z: -0.32 }),
    piece(new THREE.BoxGeometry(1.0, 0.55, 0.08), { y: 0.28, z: 0.32 }),
    piece(new THREE.BoxGeometry(0.08, 0.55, 0.56), { x: -0.46, y: 0.28 }),
    piece(new THREE.BoxGeometry(0.08, 0.55, 0.56), { x: 0.46, y: 0.28 }),
  ],
  sound: () => [
    piece(new THREE.BoxGeometry(0.8, 1.1, 0.45)),
    piece(new THREE.CylinderGeometry(0.3, 0.3, 0.06, 24), { y: -0.15, z: 0.25, rx: HALF_PI }),
    piece(new THREE.CylinderGeometry(0.13, 0.13, 0.06, 20), { y: 0.35, z: 0.25, rx: HALF_PI }),
  ],
  play: () => [
    piece(new THREE.BoxGeometry(1.05, 0.32, 0.58), { y: 0.2 }),
    piece(new THREE.BoxGeometry(0.5, 0.28, 0.48), { x: -0.05, y: 0.48 }),
    ...[-0.38, 0.38].flatMap((x) => [-0.34, 0.34].map((z) => piece(new THREE.CylinderGeometry(0.16, 0.16, 0.1, 18), { x, z, rx: HALF_PI }))),
  ],
  outdoor: () => [
    piece(new THREE.CylinderGeometry(0.35, 0.45, 0.7, 20)),
    piece(new THREE.ConeGeometry(0.5, 0.45, 20), { y: 0.58 }),
    piece(new THREE.TorusGeometry(0.28, 0.04, 8, 24, Math.PI), { y: 0.82, rz: Math.PI }),
  ],
  workshop: () => [
    piece(new THREE.BoxGeometry(1.1, 0.12, 0.65), { y: 0.65 }),
    piece(new THREE.BoxGeometry(0.12, 0.75, 0.12), { x: -0.45, y: 0.3, z: -0.25 }),
    piece(new THREE.BoxGeometry(0.12, 0.75, 0.12), { x: 0.45, y: 0.3, z: 0.25 }),
    piece(new THREE.BoxGeometry(0.16, 0.16, 0.8), { y: 0.85, rz: -0.6 }),
  ],
  science: () => [
    piece(new THREE.BoxGeometry(0.9, 0.1, 0.6)),
    piece(new THREE.CylinderGeometry(0.18, 0.28, 0.7, 20), { y: 0.4 }),
    piece(new THREE.TorusGeometry(0.35, 0.035, 8, 24), { y: 0.3, rx: HALF_PI }),
  ],
  generic: () => [
    piece(new THREE.BoxGeometry(0.95, 0.55, 0.65)),
    piece(new THREE.CylinderGeometry(0.16, 0.16, 0.65, 18), { y: 0.5 }),
  ],
};

export function projectGeometry(idea) {
  const category = String(idea && idea.category || "generic").toLowerCase();
  const key = PROJECT_BUILDERS[category] ? category : "generic";
  if (!projectGeometryCache.has(key)) projectGeometryCache.set(key, merge(PROJECT_BUILDERS[key]()));
  return projectGeometryCache.get(key);
}
