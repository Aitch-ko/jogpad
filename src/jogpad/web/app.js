// Live view of the pad. Read-only: this page never sends anything to the machine.
"use strict";

const UNIT = 60; // pixels per key unit
const GAP = 6;
const RECENT = 12;
const SVG_NS = "http://www.w3.org/2000/svg";

let catalog = {};
const t = (key) => catalog[key] || key;
const $ = (id) => document.getElementById(id);

function actionLabels() {
  return {
    x_plus: t("ui.action.x_plus"),
    x_minus: t("ui.action.x_minus"),
    y_plus: t("ui.action.y_plus"),
    y_minus: t("ui.action.y_minus"),
    z_plus: t("ui.action.z_plus"),
    z_minus: t("ui.action.z_minus"),
    e_plus: t("ui.action.e_plus"),
    e_minus: t("ui.action.e_minus"),
    selected_plus: t("ui.action.selected_plus"),
    selected_minus: t("ui.action.selected_minus"),
    select_next: t("ui.action.select_next"),
    step: t("ui.action.step"),
    home: t("ui.action.home"),
    stop: t("ui.action.stop"),
  };
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function svg(tag, attrs, parent) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  parent.appendChild(node);
  return node;
}

function text(content, attrs, parent) {
  const node = svg("text", attrs, parent);
  node.textContent = content;
  return node;
}

function drawPad(pad, labels) {
  const root = $("pad");
  const controls = new Map();
  if (!pad.layout) {
    $("layout-name").textContent = t("ui.no_layout");
    root.remove();
    return controls;
  }
  $("layout-name").textContent = pad.layout.name;
  $("layout-note").textContent = pad.layout.note;
  root.setAttribute("aria-label", pad.layout.name);

  let width = 0;
  let height = 0;
  for (const c of pad.layout.controls) {
    const x = c.x * UNIT + GAP / 2;
    const y = c.y * UNIT + GAP / 2;
    const w = c.w * UNIT - GAP;
    const h = c.h * UNIT - GAP;
    width = Math.max(width, x + w + GAP / 2);
    height = Math.max(height, y + h + GAP / 2);

    const group = svg("g", { class: "control" }, root);
    if (c.kind === "knob") {
      svg("circle", { cx: x + w / 2, cy: y + h / 2, r: Math.min(w, h) / 2 }, group);
    } else {
      svg("rect", { x, y, width: w, height: h, rx: 6 }, group);
    }
    text(c.label, { class: "label", x: x + 6, y: y + 14 }, group);

    const actions = pad.actions[c.id] || {};
    const names = ["press", "cw", "ccw"]
      .filter((part) => actions[part])
      .map((part) => labels[actions[part]] || actions[part]);
    const middle = { x: x + w / 2, "text-anchor": "middle" };
    names.forEach((name, i) => {
      const offset = (i - (names.length - 1) / 2) * 14;
      text(name, { ...middle, class: "action", y: y + h / 2 + 5 + offset }, group);
    });
    const turn = text("", { ...middle, class: "turn", y: y + h - 8 }, group);
    controls.set(c.id, { group, turn });
  }
  root.setAttribute("viewBox", `0 0 ${width} ${height}`);
  return controls;
}

function showEvent(event, controls, labels) {
  const control = event.control && controls.get(event.control);
  if (control) {
    if (event.part === "press") {
      control.group.classList.toggle("active", event.pressed);
    } else if (event.pressed) {
      // Knob detents have no lasting "down" state: flash and show the direction.
      control.turn.textContent = event.part === "cw" ? "↻" : "↺";
      control.group.classList.add("active");
      clearTimeout(control.timer);
      control.timer = setTimeout(() => {
        control.group.classList.remove("active");
        control.turn.textContent = "";
      }, 250);
    }
  }
  if (!event.pressed) return;
  const list = $("recent");
  list.querySelector(".empty")?.remove();
  const item = document.createElement("li");
  const key = document.createElement("span");
  key.textContent = `${event.name} (${event.code})`;
  const action = document.createElement("span");
  action.textContent = event.action ? labels[event.action] || event.action : t("ui.unassigned");
  item.append(key, action);
  list.prepend(item);
  while (list.children.length > RECENT) list.lastChild.remove();
}

async function refreshState() {
  try {
    const s = await getJson("/api/state");
    $("step").textContent = `${s.step} mm`;
    $("axis").textContent = s.selected_axis;
    $("home").textContent = s.home_selection === null ? "–" : s.home_selection.join(" ") || t("ui.home_all");
    $("refusal").textContent = s.last_refusal || "–";
  } catch {
    // The live link shows the outage; keep the last values.
  }
}

function connect(controls, labels) {
  const link = $("link");
  const source = new EventSource("/api/events");
  source.onopen = () => {
    link.textContent = t("ui.connected");
    link.classList.add("on");
  };
  source.onerror = () => {
    // EventSource reconnects by itself.
    link.textContent = t("ui.disconnected");
    link.classList.remove("on");
  };
  source.onmessage = (message) => {
    showEvent(JSON.parse(message.data), controls, labels);
    refreshState();
  };
}

async function main() {
  const [config, version, pad] = await Promise.all([
    getJson("/api/config"),
    getJson("/api/version"),
    getJson("/api/pad"),
  ]);
  catalog = await getJson("/api/messages");
  document.documentElement.lang = config.server.language;
  $("version").textContent = version.version;
  $("label-step").textContent = t("ui.step");
  $("label-axis").textContent = t("ui.axis");
  $("label-home").textContent = t("ui.home");
  $("label-refusal").textContent = t("ui.refusal");
  $("label-recent").textContent = t("ui.recent");
  $("link").textContent = t("ui.disconnected");
  const empty = document.createElement("li");
  empty.className = "empty";
  empty.textContent = t("ui.recent_empty");
  $("recent").append(empty);

  const labels = actionLabels();
  const controls = drawPad(pad, labels);
  connect(controls, labels);
  refreshState();
  setInterval(refreshState, 2000);
}

main();
