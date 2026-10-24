// Breadboard geometry (the book's 830-point board: rows 1-63, holes a-e and f-j, two rails per long edge:
// the inner rail is GND, the outer rail is +5 V) and a connectivity checker that rebuilds the circuit from
// holes, legs and wires and compares it with the netlist.
export const ROWS = 63;
export const PITCH = 9.6;                 // 2.54 mm at 96 px per inch: the board is drawn 1:1
export const BOARD_W = 640, BOARD_H = 236;
export const X0 = 20, Y0 = 186;           // hole 1a
const COLIDX = { a: 0, b: 1, c: 2, d: 3, e: 4, f: 7, g: 8, h: 9, i: 10, j: 11 };
export const RAILY = { "B-": -2.2, "B+": -3.2, "T-": 13.2, "T+": 14.2 };
export const COLS = "abcdefghij";

export const half = (col) => ("abcde".includes(col) ? "B" : "T");
export function holeXY(row, col) { return [X0 + (row - 1) * PITCH, Y0 - COLIDX[col] * PITCH]; }
export function railXY(rail, row) { return [X0 + (row - 1) * PITCH, Y0 - RAILY[rail] * PITCH]; }
export const isRail = (h) => typeof h === "string" && /^[TB][+-]$/.test(h);
export const holeName = (h) => (Array.isArray(h) ? `${h[0]}${h[1]}` : String(h));
export const RAIL_WORDS = { "B+": "+5 V rail (bottom)", "B-": "GND rail (bottom)", "T+": "+5 V rail (top)", "T-": "GND rail (top)" };

// A wire end: [row, "j"] (a hole), "T+" (rail; position taken from the other end), or [rail, row]
export function endXY(e, otherRow = 1) {
  if (Array.isArray(e) && isRail(e[0])) return railXY(e[0], e[1]);
  if (isRail(e)) return railXY(e, otherRow);
  return holeXY(+e[0], e[1]);
}

// Every leg of a placement: [{pin, at: [row, col] | [rail, row] | rail}] (engine conventions:
// DIP pin 1 at (row, hole) with the other row mirrored across the gap; SIP pins along one column;
// a button straddles the gap over three rows; leaded parts list each leg)
export const mirror = (col) => COLS[9 - COLS.indexOf(col)];
// the other row of a DIP: width pitches (0.1 in) across; the gap is 0.3 in, so a 0.3 in chip
// with pin 1 in e has its other row in f, a 0.6 in one (or a 0.56 in digit) with pin 1 in c, in g
export function across(col, width = 3) {
  if (!"abcde".includes(col)) return null;
  const want = COLIDX[col] + (width || 3);
  return COLS.split("").find((c) => COLIDX[c] === want) || null;
}
export function footprint(def) {
  if (!def) return { kind: "virtual" };
  if (def.footprint) return def.footprint;
  if (/^DIPSW/.test(def.type)) return { kind: "dip", width: 3 };
  if (def.kind === "chip") return { kind: "dip", width: def.width || (def.pins.length >= 24 ? 6 : 3) };
  return { kind: "leads" };
}
export function placementLegs(pl, def) {
  const legs = [];
  if (pl.legs) {
    for (const [k, v] of Object.entries(pl.legs)) legs.push({ key: k, pin: legPin(k, def), at: v });
    return legs;
  }
  if (!def || pl.row == null) return legs;
  const fp = footprint(def);
  const row = +pl.row, col = String(pl.hole || "e");
  const nums = def.pins.map((p) => +p[0]).sort((a, b) => a - b);
  const n = nums.length;
  if (fp.kind === "dip") {
    const top = across(col, fp.width || 3);
    if (!top) return legs;
    for (let p = 1; p <= n; p++) legs.push({ key: String(p), pin: String(p), at: p <= n / 2 ? [row + p - 1, col] : [row + (n - p), top] });
  } else if (fp.kind === "sip") {
    nums.forEach((p, i) => legs.push({ key: String(p), pin: String(p), at: [row + i * (fp.pitch || 1), col] }));
  } else if (fp.kind === "button") {
    const top = mirror(col);
    legs.push({ key: "1", pin: "1", at: [row, col] }, { key: "2", pin: "2", at: [row, top] }, { key: "3", pin: "3", at: [row + 2, col] }, { key: "4", pin: "4", at: [row + 2, top] });
  }
  return legs;
}
export function legPin(key, def) {
  const pins = def ? def.pins.map((p) => String(p[0])) : [];
  if (pins.includes(String(key))) return String(key);
  const byName = def && def.pins.find((p) => String(p[1]) === String(key));
  return byName ? String(byName[0]) : String(key);
}
export const isDip = (def) => def && footprint(def).kind === "dip";

// ------------------------------------------------------------------------- checker
export function checkBreadboards(project, getDef) {
  const problems = [];
  const boards = project.breadboards || [];
  if (!boards.length) return problems;
  const parent = new Map();
  const find = (x) => { if (!parent.has(x)) parent.set(x, x); let r = x; while (parent.get(r) !== r) r = parent.get(r); let c = x; while (parent.get(c) !== r) { const n = parent.get(c); parent.set(c, r); c = n; } return r; };
  const union = (a, b) => parent.set(find(a), find(b));
  const node = (bid, at) => (Array.isArray(at) && isRail(at[0]) ? `R:${at[0][1]}` : isRail(at) ? `R:${at[1]}` : `N:${bid}:${at[0]}:${half(at[1])}`);
  const internal = (def) => (def && def.internal) || [];
  const holeKey = (bid, at) => (Array.isArray(at) && !isRail(at[0]) ? `${bid}:${at[0]}${at[1]}` : null);
  const used = new Map();
  const use = (bid, at, what) => {
    const k = holeKey(bid, at);
    if (!k) return;
    if (used.has(k)) problems.push({ severity: "error", message: `Hole ${k.split(":")[1]} on ${bname(bid)} is used twice (${used.get(k)} and ${what}).`, where: k });
    else used.set(k, what);
  };
  const names = Object.fromEntries(boards.map((b) => [b.id, b.name || b.id]));
  const bname = (id) => names[id] || id;
  const pinAt = new Map();      // "U1.3" -> node
  const placed = new Set();
  for (const b of boards) {
    for (const pl of b.placements || []) {
      const part = project.parts.find((p) => p.id === pl.part);
      if (!part) { problems.push({ severity: "warning", message: `${bname(b.id)} has a placement for ${pl.part}, which is not in the parts list.`, where: pl.part }); continue; }
      placed.add(part.id);
      const def = getDef(part.type);
      for (const leg of placementLegs(pl, def)) {
        use(b.id, leg.at, `${part.id} pin ${leg.pin}`);
        const nd = node(b.id, leg.at);
        find(nd);
        const k = `${part.id}.${leg.pin}`;
        if (pinAt.has(k)) union(pinAt.get(k), nd);
        else pinAt.set(k, nd);
      }
      for (const [a, b] of internal(def)) {                // legs joined inside the part (buttons, digits)
        const na = pinAt.get(`${part.id}.${a}`), nb = pinAt.get(`${part.id}.${b}`);
        if (na && nb) union(na, nb);
      }
    }
    (b.wires || []).forEach((w, i) => {
      use(b.id, w.a, `wire ${i + 1}`);
      use(b.id, w.b, `wire ${i + 1}`);
      union(node(b.id, w.a), node(b.id, w.b));
    });
  }
  for (const l of project.links || []) union(node(l.a[0], l.a[1]), node(l.b[0], l.b[1]));
  // every board's + rails are the supply, every - rail is ground
  union("R:+", "VCC"); union("R:-", "GND");
  const owner = new Map();
  const partsUsed = new Set(project.nets.flatMap((n) => n.pins.map((p) => p[0])));
  for (const pid of partsUsed) {
    if (!placed.has(pid) && project.parts.some((p) => p.id === pid))
      problems.push({ severity: "warning", message: `${pid} is not on a breadboard yet.`, where: pid });
  }
  for (const net of project.nets) {
    const roots = new Set();
    for (const [pid, pin] of net.pins) {
      if (!placed.has(pid)) continue;
      const nd = pinAt.get(`${pid}.${pin}`);
      if (!nd) { problems.push({ severity: "error", message: `${pid} pin ${pin} (${net.name}) has no hole.`, where: `${pid}.${pin}` }); continue; }
      roots.add(find(nd));
    }
    if (net.name === "VCC") roots.add(find("VCC"));
    if (net.name === "GND") roots.add(find("GND"));
    if (roots.size > 1) problems.push({ severity: "error", message: `${net.name} is split into ${roots.size} groups: a wire is missing.`, where: `net:${net.name}` });
    for (const r of roots) {
      if (owner.has(r) && owner.get(r) !== net.name)
        problems.push({ severity: "error", message: `Short: ${net.name} is joined to ${owner.get(r)}.`, where: `net:${net.name}` });
      else owner.set(r, net.name);
    }
  }
  return problems;
}
