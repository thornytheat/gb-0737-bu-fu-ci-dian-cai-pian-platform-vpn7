import {at, tag} from "./exhibits.js";

const column = (name, get, numeric = false) => ({name, get, numeric});
const ref = (item) => item.source.ref;
const list = (values) => values?.join(" / ");
const interval = (values) => values.join("–");
const issueColumns = [column("记录号", (r) => r.id), column("卷号", (r) => r.roll), column("原因码", (r) => r.code),
  column("说明", (r) => r.message), column("来源", ref), column("关联行", (r) => list(r.related)), column("原值", (r) => list(r.source.cells))];
const rollColumns = [column("卷号", (r) => r.id), column("布种", (r) => r.fabric), column("幅宽 mm", (r) => r.width, true),
  column("卷长 mm", (r) => r.length, true), column("源行", ref)];
const orderColumns = [column("订单号", (r) => r.id), column("布种", (r) => r.fabric), column("最小幅宽 mm", (r) => r.width, true),
  column("净长 mm", (r) => r.net, true), column("单端缝份 mm", (r) => r.seam, true), column("裁长 mm", (r) => r.length, true),
  column("数量", (r) => r.quantity, true), column("优先", (r) => r.priority), column("源行", ref)];
const spanColumns = [column("起点 mm", (r) => r.start, true), column("终点 mm", (r) => r.end, true),
  column("长度 mm", (r) => r.end - r.start, true), column("依据", (r) => list(r.refs))];

export function views(stage, data, activeRoll, history) {
  const roll = data?.zones.rolls.find((row) => row.id === activeRoll);
  switch (stage) {
    case "intake": return [
      ["来源统计", data ? Object.values(data.intake) : [], [column("源文件", (r) => r.file), column("编码", (r) => r.encoding),
        column("分段", (r) => r.segments, true), column("原始", (r) => r.raw, true), column("空行", (r) => r.blank, true),
        column("录入", (r) => r.accepted.length, true), column("重复", (r) => r.duplicates.length, true),
        column("隔离", (r) => r.isolated.length, true)]],
      ["布卷档案", data?.intake.rolls.accepted, rollColumns], ["工单", data?.intake.orders.accepted, orderColumns],
      ["原始隔离", data && Object.values(data.intake).flatMap((r) => r.isolated), issueColumns],
      ["重复记录", data && Object.values(data.intake).flatMap((r) => r.duplicates), issueColumns],
    ];
    case "locate": return [
      ["坐标定位", data?.locate.located, [column("疵号", (r) => r.id), column("卷号", (r) => r.roll), column("基准", (r) => r.origin),
        column("卷首坐标 mm", (r) => interval(r.anchor), true), column("疵段 mm", (r) => interval(r.footprint), true),
        column("安全区 mm", (r) => interval(r.expanded), true), column("源行", ref)]],
      ["待定位", data?.locate.isolated, issueColumns],
    ];
    case "zones": return [["禁切并集", roll?.blocked, spanColumns], ["可用段", roll?.available, spanColumns]];
    case "fit": return [
      ["各卷可排方案", data?.fit.roll_options, [column("卷号", (r) => r.roll), column("匹配工单", (r) => list(r.compatible)),
        column("可用段", (r) => r.usable_spans, true), column("组合数", (r) => r.options, true),
        column("单卷优选片数", (r) => r.best_piece_count, true),
        column("单卷优选明细", (r) => Object.entries(r.best_by_order).filter(([, count]) => count).map(([id, count]) => `${id} × ${count}`).join(" / "))]],
      ["裁片规格", data?.fit.orders, orderColumns],
    ];
    case "changeovers": return [
      ["领卷排程", data?.changeovers.placements, [column("卷号", (r) => r.roll), column("裁片", (r) => r.id),
        column("起点 mm", (r) => r.start, true), column("终点 mm", (r) => r.end, true), column("刀口终点 mm", (r) => r.kerf_end, true),
        column("订单行", (r) => r.source)]],
      ["工单欠料", data?.changeovers.orders, [column("订单号", (r) => r.order), column("优先", (r) => r.priority),
        column("需求", (r) => r.requested, true), column("已排", (r) => r.planned, true), column("待补", (r) => r.remaining, true),
        column("原因码", (r) => r.review?.code), column("说明", (r) => r.review?.message), column("依据卷号", (r) => list(r.review?.rolls))]],
    ];
    case "ledger": return [
      ["卷长勾稽", data?.ledger.rolls, [column("卷号", (r) => r.roll), column("卷长 mm", (r) => r.length, true),
        column("合格 mm", (r) => r.lengths.piece, true), column("禁切 mm", (r) => r.lengths.blocked, true),
        column("切口 mm", (r) => r.lengths.kerf, true), column("未用 mm", (r) => r.lengths.unused, true),
        column("差额 mm", (r) => r.length - Object.values(r.lengths).reduce((a, b) => a + b, 0), true), column("源行", (r) => r.source)]],
      ["采信勾稽", data && Object.entries(data.ledger.records), [column("来源", (r) => ({rolls:"布卷", defects:"疵点", orders:"订单"})[r[0]]),
        column("原始", (r) => r[1].raw, true), column("有效", (r) => r[1].accepted, true),
        column("重复", (r) => r[1].duplicates, true), column("隔离", (r) => r[1].isolated, true), column("差额", (r) => r[1].delta, true)]],
    ];
    case "slips": return [
      ["签条登记", data?.slips, [column("签号", (r) => ({text: r.serial, roll: r.roll})), column("卷号", (r) => r.roll),
        column("状态", (r) => r.state), column("领卷次序", (r) => r.sequence, true), column("片数", (r) => r.pieces.length, true),
        column("复核依据", (r) => list(r.hold_refs)), column("布卷来源", (r) => r.source)]],
      ["归档历史", history, [column("批次号", (r) => ({text: r.id.slice(0, 12), run: r.id})), column("验布单", (r) => r.inputs.defects.file),
        column("刀口 mm", (r) => r.kerf_mm, true), column("片数", (r) => r.piece_count, true), column("归档 UTC", (r) => r.created_at)]],
    ];
    default: throw new Error("模块不存在");
  }
}

export function drawTable(tab) {
  const [, rows = [], columns] = tab;
  const host = at("record-table");
  at("view-meta").textContent = `${rows.length} 条`;
  if (!rows.length) {
    host.replaceChildren(tag("p", "此处暂无记录。", "empty"));
    return;
  }
  const sheet = tag("table", "", "sheet");
  const head = sheet.createTHead().insertRow();
  for (const definition of columns) {
    const th = tag("th", definition.name, definition.numeric ? "num" : "");
    th.scope = "col";
    head.append(th);
  }
  const body = sheet.createTBody();
  for (const item of rows) {
    const row = body.insertRow();
    for (const definition of columns) {
      const value = definition.get(item);
      const cell = row.insertCell();
      if (definition.numeric) cell.className = "num";
      if (value && typeof value === "object") {
        const button = tag("button", value.text);
        button.type = "button";
        if (value.run) button.dataset.open = value.run;
        if (value.roll) button.dataset.roll = value.roll;
        cell.append(button);
      } else {
        cell.textContent = value ?? "—";
        cell.title = cell.textContent;
      }
    }
  }
  host.replaceChildren(sheet);
  host.scrollTo(0, 0);
}
