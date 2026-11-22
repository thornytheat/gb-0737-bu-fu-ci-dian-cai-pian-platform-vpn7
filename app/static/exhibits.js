export const at = (id) => document.getElementById(id);

export function tag(name, value = "", className = "") {
  const node = document.createElement(name);
  node.className = className;
  node.textContent = value;
  return node;
}

const shortId = (id) => id?.slice(0, 12) ?? "—";
const TYPES = {piece: "合格裁片", blocked: "禁切", kerf: "切口", unused: "未用段"};

export function drawAxis(book, slip) {
  const axis = at("axis");
  if (!book || !slip) {
    at("roll-badge").textContent = "—";
    axis.replaceChildren(tag("p", "请读取验布单。", "empty"));
    return;
  }
  at("roll-badge").textContent = `${slip.roll} · ${slip.fabric} · 幅宽 ${slip.width} mm`;
  const ruler = tag("div", "", "ruler");
  ruler.setAttribute("aria-label", "毫米刻度");
  const divisions = Math.min(4, book.length);
  for (let slot = 0; slot <= divisions; slot++) {
    const position = Math.round(slot * book.length / divisions);
    const tick = tag("span", String(position), "tick");
    tick.style.left = `${position / book.length * 100}%`;
    ruler.append(tick);
  }
  const band = tag("div", "", "roll-band");
  band.setAttribute("role", "img");
  band.setAttribute("aria-label", Object.entries(book.lengths).map(([key, value]) => `${TYPES[key]} ${value} 毫米`).join("，"));
  for (const span of book.spans) {
    const width = (span.end - span.start) / book.length * 100;
    const label = span.type === "piece" ? span.id : span.type === "blocked" ? "禁切" : "";
    const segment = tag("span", width >= 9 ? label : "", `segment ${span.type}`);
    segment.dataset.type = span.type;
    segment.style.left = `${span.start / book.length * 100}%`;
    segment.style.width = `${width}%`;
    segment.title = `${TYPES[span.type]} ${span.start}–${span.end} mm${span.refs?.length ? ` · ${span.refs.join(" / ")}` : ""}`;
    band.append(segment);
  }
  const line = book.held ? slip.hold_message : `${slip.length} mm · ${slip.pieces.length} 片 · 切口 ${slip.lengths.kerf} mm`;
  axis.replaceChildren(ruler, band, tag("p", line, `roll-status${book.held ? " held" : ""}`));
}

function receipt(slip, manifest, kerf) {
  const content = tag("div", "", "receipt");
  const head = tag("div", "", "receipt-head");
  head.append(tag("b", slip.serial), tag("span", slip.state, `stamp${slip.state === "封存" ? " held" : ""}`));
  const meta = tag("p", `批次 ${shortId(manifest?.id)} · ${slip.fabric} · ${slip.width} mm`, "receipt-meta");
  if (manifest) meta.title = manifest.id;
  const sheet = tag("dl");
  const fields = [
    ["卷长", `${slip.length} mm`], ["计划裁片", `${slip.pieces.length} 片`],
    ["合格裁片", `${slip.lengths.piece} mm`], ["禁切", `${slip.lengths.blocked} mm`],
    ["切口", `${slip.lengths.kerf} mm`], ["未用段", `${slip.lengths.unused} mm`],
    ["刀口设定", `${kerf} mm`], ["领卷次序", slip.sequence ?? "—"],
  ];
  for (const [name, value] of fields) sheet.append(tag("dt", name), tag("dd", value, "num"));
  content.append(head, meta, sheet);
  if (slip.pieces.length) {
    const lines = tag("ol");
    for (const cut of slip.pieces) {
      const item = tag("li", `${cut.id}　${cut.start}–${cut.end} mm　刀口至 ${cut.kerf_end}`);
      item.title = cut.source;
      lines.append(item);
    }
    content.append(lines);
  }
  if (slip.hold_message) content.append(tag("p", slip.hold_message, "receipt-sources"));
  content.append(tag("p", [slip.source, ...slip.hold_refs].join(" / "), "receipt-sources"));
  const signature = tag("div", "", "signature");
  signature.append(tag("span", "验卷 __________"), tag("span", "领卷 __________"));
  content.append(signature);
  return content;
}

export function drawSlip(slip, manifest, kerf) {
  at("slip-body").replaceChildren(slip ? receipt(slip, manifest, kerf) : tag("p", "请选择布卷。", "empty"));
  const printable = at("print-slip");
  printable.replaceChildren();
  if (slip && manifest) {
    printable.append(tag("h1", "裁床签条"), receipt(slip, manifest, kerf));
  }
}
