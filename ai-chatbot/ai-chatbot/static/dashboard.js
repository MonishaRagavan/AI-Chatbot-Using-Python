// Loads /api/dashboard/stats and draws the dashboard. Refreshes every 10 seconds.
const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";

function fmtMs(ms) {
  if (ms === null || ms === undefined) return "–";
  return ms >= 1000 ? (ms / 1000).toFixed(1) + " s" : ms + " ms";
}

// Database times are UTC; show them in the viewer's own time zone.
function fmtTime(utc) {
  const d = new Date(utc.replace(" ", "T") + "Z");
  return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function svgEl(name, attrs) {
  const el = document.createElementNS(SVG_NS, name);
  for (const key in attrs) el.setAttribute(key, attrs[key]);
  return el;
}

function drawChart(daily) {
  const W = 560, H = 230, left = 30, bottom = 28, top = 10;
  const plotH = H - bottom - top;
  const max = Math.max(1, ...daily.map((d) => d.ok + d.errors));
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}` });

  // Horizontal guide lines with counts
  [0, 0.5, 1].forEach((f) => {
    const y = top + plotH - plotH * f;
    svg.appendChild(svgEl("line", { x1: left, x2: W, y1: y, y2: y, stroke: "#dbe3e8" }));
    const label = svgEl("text", { x: left - 6, y: y + 4, "text-anchor": "end" });
    label.textContent = Math.round(max * f);
    svg.appendChild(label);
  });

  const slot = (W - left) / daily.length;
  const barW = Math.min(44, slot * 0.6);
  daily.forEach((d, i) => {
    const x = left + slot * i + (slot - barW) / 2;
    const okH = (d.ok / max) * plotH;
    const errH = (d.errors / max) * plotH;
    if (okH > 0) svg.appendChild(svgEl("rect", { x, y: top + plotH - okH, width: barW, height: okH, fill: "#0f766e" }));
    if (errH > 0) svg.appendChild(svgEl("rect", { x, y: top + plotH - okH - errH, width: barW, height: errH, fill: "#b42318" }));
    const t = svgEl("text", { x: x + barW / 2, y: H - 8, "text-anchor": "middle" });
    t.textContent = d.date.slice(5);   // MM-DD
    svg.appendChild(t);
    const tip = svgEl("title", {});
    tip.textContent = `${d.date}: ${d.ok} answered, ${d.errors} failed`;
    svg.appendChild(tip);
  });
  $("chart").replaceChildren(svg);
}

function cell(text, className) {
  const td = document.createElement("td");
  if (className) td.className = className;
  td.textContent = text;
  return td;
}

function render(data) {
  $("s-total").textContent = data.total;
  $("s-today").textContent = data.today;
  $("s-rate").textContent = data.success_rate === null ? "–" : data.success_rate + "%";
  $("s-avg").textContent = fmtMs(data.avg_ms);
  $("s-err").textContent = data.errors;
  $("s-err").classList.toggle("has-errors", data.errors > 0);

  const mode = $("mode");
  mode.textContent = data.mode === "demo" ? "Demo mode" : "Live: " + data.model;
  mode.className = "pill " + data.mode;

  drawChart(data.daily);

  const errors = $("errors");
  errors.replaceChildren();
  if (data.top_errors.length === 0) {
    const li = document.createElement("li");
    li.className = "empty-note";
    li.textContent = "No errors recorded.";
    errors.appendChild(li);
  }
  data.top_errors.forEach((e) => {
    const li = document.createElement("li");
    const msg = document.createElement("span");
    msg.textContent = e.error;
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = e.count;
    li.append(msg, count);
    errors.appendChild(li);
  });

  $("empty").hidden = data.recent.length > 0;
  const body = $("recent");
  body.replaceChildren();
  data.recent.forEach((c) => {
    const tr = document.createElement("tr");
    tr.appendChild(cell(fmtTime(c.created_at), "time"));
    const result = document.createElement("td");
    const tag = document.createElement("span");
    tag.className = "tag " + c.status;
    tag.textContent = c.status === "ok" ? "Answered" : "Failed";
    result.appendChild(tag);
    tr.appendChild(result);
    tr.appendChild(cell(c.user_message));
    tr.appendChild(cell(c.status === "ok" ? c.bot_reply : c.error_text));
    tr.appendChild(cell(fmtMs(c.duration_ms), "took"));
    body.appendChild(tr);
  });
}

async function load() {
  try {
    const response = await fetch("/api/dashboard/stats");
    if (response.status === 401) { window.location.href = "/login"; return; }
    if (!response.ok) throw new Error("bad status");
    render(await response.json());
    $("status").textContent = "Updated " + new Date().toLocaleTimeString() + ". Refreshes every 10 seconds.";
  } catch (err) {
    $("status").textContent = "Could not refresh. Trying again in 10 seconds.";
  }
}

load();
setInterval(load, 10000);
