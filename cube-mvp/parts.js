/* ---------------------------------------------------------------
   Part categories: one keyword classifier drives both the 2D icons
   (TASKS.md #2) and the 3D shapes (TASKS.md #3), so a "Stepper Motor"
   looks like a motor in the inventory, the palette, the bench and the
   3D viewer. Works on any name, including AI-generated and scanned ones.
   --------------------------------------------------------------- */

import * as THREE from "three";

// First match wins, so more specific keywords sit above generic ones.
const RULES = [
  ["sheet",     /cardboard|plywood|foam board|poster board|chipboard|particle board/],
  ["power",    /power supply|\bpsu\b|battery|batteries|charger|adapter|power bank/],
  ["board",     /board|\bpcb\b|circuit|arduino|raspberry|controller|microcontroller|\bchip\b/],
  ["switch",    /switch|button|sensor|endstop/],
  ["gripper",   /grip|claw|pincer|tong/],
  ["joint",     /joint|hinge|pivot|elbow|shoulder/],
  ["motor",     /motor|servo|stepper|drive unit|\bfan\b/],
  ["pulley",    /pulley|gear|sprocket|wheel|cog/],
  ["belt",      /belt|rubber band|elastic|strap/],
  ["bearing",   /bearing|bushing|\bring\b|washer/],
  ["nozzle",    /nozzle|hotend|hot end|funnel/],
  ["rail",      /extrusion|rail|beam|segment|\barm\b|frame|bracket|profile|\bbar\b|ruler/],
  ["rod",       /\brod\b|shaft|dowel|axle|pipe|tube|straw|pencil|stick|skewer/],
  ["wire",      /wire|cable|cord|string|rope|twine|thread|yarn/],
  ["fastener",  /zip tie|cable tie|screw|bolt|\bnut\b|\bnail|clip|clamp|tape|glue|rivet|pin\b|magnet/],
  ["sheet",     /cardboard|paper|plywood|\bwood|acrylic|sheet|panel|plate|board|foam|card\b/],
  ["container", /bottle|\bcan\b|\bjar\b|\bbox\b|\bcup\b|container|tin\b|tub\b|lid\b/],
  ["fabric",    /fabric|cloth|cotton|felt|denim|t-shirt|sock|towel/],
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
  switch:    '<rect x="4" y="12" width="16" height="7" rx="1.5"/><path d="M12 12l5-7"/><circle cx="17" cy="5" r="1.2"/>',
  sheet:     '<path d="M4 8l8-4 8 4-8 4z"/><path d="M4 8v4l8 4 8-4V8"/>',
  container: '<path d="M7 7h10l-1 13H8z"/><path d="M6 4h12v3H6z"/>',
  fabric:    '<path d="M4 6c3-2 5 2 8 0s5-2 8 0v12c-3-2-5 2-8 0s-5-2-8 0z"/>',
  gripper:   '<path d="M12 3v6M12 9l-5 5v6M12 9l5 5v6M7 20h2M15 20h2"/>',
  joint:     '<circle cx="9" cy="15" r="4"/><circle cx="9" cy="15" r="1.2"/><path d="M12 12l7-7M17 5h2v2"/>',
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
  assembly: () => [piece(new THREE.DodecahedronGeometry(0.45, 0))],
  generic: () => [piece(new THREE.BoxGeometry(0.65, 0.65, 0.65))],
};

// Returns a shared geometry per category. Callers must not dispose it.
export function partGeometry(item) {
  const cat = categoryFor(item);
  if (!geometryCache.has(cat)) geometryCache.set(cat, merge((BUILDERS[cat] || BUILDERS.generic)()));
  return geometryCache.get(cat);
}
