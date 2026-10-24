// "where" a problem is: the engine gives a dict ({part, pin, net, nets, parts, board, hole}); older
// strings ("U3.7", "BB1:14j", "net:BUS0") are understood too.
export function normWhere(w) {
  if (!w) return {};
  if (typeof w === "object" && !Array.isArray(w)) {
    const o = { ...w };
    if (Array.isArray(o.hole)) o.hole = [+o.hole[0], String(o.hole[1])];
    if (o.pin != null) o.pin = String(o.pin);
    return o;
  }
  const s = String(w);
  let m;
  if ((m = s.match(/^(BB\w*?)[: ]+(\d+)([a-j])$/))) return { board: m[1], hole: [+m[2], m[3]] };
  if ((m = s.match(/^net:(.+)$/))) return { net: m[1] };
  if ((m = s.match(/^([A-Za-z_][\w]*)\.(\w+)$/))) return { part: m[1], pin: m[2] };
  if ((m = s.match(/^([A-Za-z_][\w]*)$/))) return { part: m[1] };
  return {};
}
export function whereText(w) {
  const o = normWhere(w);
  const bits = [];
  if (o.part) bits.push(o.pin ? `${o.part} pin ${o.pin}` : o.part);
  if (o.parts) bits.push(o.parts.slice(0, 6).join(", ") + (o.parts.length > 6 ? "…" : ""));
  if (o.board) bits.push(o.hole ? `${o.board} hole ${o.hole[0]}${o.hole[1]}` : o.board);
  if (o.net) bits.push(`net ${o.net}`);
  if (o.nets) bits.push(`nets ${o.nets.join(", ")}`);
  if (o.drivers) bits.push(`driven by ${[].concat(o.drivers).join(", ")}`);
  return bits.join(" · ");
}
// guess a part from an engine message like "floating input: U7.CLK reads Z on net CLK"
export function guessWhere(msg) {
  const m = String(msg).match(/\b([A-Z]{1,4}\d+)(?:\.(\w+))?\b/);
  return m ? { part: m[1] } : {};
}
