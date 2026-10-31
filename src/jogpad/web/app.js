// Live view and setup of the pad. Nothing here moves the machine: moves only
// come from the pad itself, and learning keeps even those back.
"use strict";

const UNIT = 60; // pixels per key unit
const GAP = 6;
// The pad's outline runs this far around its controls, in key units; api.py
// counts it into the panel's aspect ratio.
const OUTLINE = 0.2;
// The arrow above a knob, in pixels like UNIT. It clears the knob's real cap,
// which is as wide as the knob's box, and stays inside the pad's outline.
const TURN_GAP = 10;
const TURN_ANGLE = (32 * Math.PI) / 180; // from the top to each end
const TURN_HEAD = 8;
const TURN_LABEL = 11; // from the arrow's tip outwards to its label's middle
const RECENT = 12;
const LEARN_S = 30;
const LANGUAGE_KEY = "jogpad.language";
const THEME_KEY = "jogpad.theme";
const SVG_NS = "http://www.w3.org/2000/svg";
const ACTIONS = [
  "x_plus", "x_minus", "y_plus", "y_minus", "z_plus", "z_minus", "e_plus", "e_minus",
  "selected_plus", "selected_minus", "select_next", "step", "home", "stop",
];

let catalog = {};
let config = null;
let labels = {};
let controls = new Map();
// Last known switch: true, false, or null while it cannot be read.
let switchedOn = null;
// Set while the page waits for a key press: learning or a direction check.
let waiter = null;

const $ = (id) => document.getElementById(id);
function t(key, values = {}) {
  return (catalog[key] || key).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? "");
}

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

// What the user saw after pressing the + key of an axis. `right` is whether
// that matches the standard: the tool moves in + relative to the bed.
function directionAnswers(axis) {
  return {
    X: [
      { text: t("ui.dir.head_right"), right: true },
      { text: t("ui.dir.head_left"), right: false },
      { text: t("ui.dir.bed_left"), right: true },
      { text: t("ui.dir.bed_right"), right: false },
    ],
    Y: [
      { text: t("ui.dir.head_back"), right: true },
      { text: t("ui.dir.head_front"), right: false },
      { text: t("ui.dir.bed_front"), right: true },
      { text: t("ui.dir.bed_back"), right: false },
    ],
    Z: [
      { text: t("ui.dir.head_up"), right: true },
      { text: t("ui.dir.head_down"), right: false },
      { text: t("ui.dir.bed_down"), right: true },
      { text: t("ui.dir.bed_up"), right: false },
    ],
  }[axis];
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

async function send(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  return { status: response.status, data };
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value);
  }
  node.append(...children);
  return node;
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

function drawPad(pad) {
  const root = $("pad");
  root.replaceChildren();
  controls = new Map();
  if (!pad.layout) {
    $("layout-name").textContent = t("ui.no_layout");
    root.hidden = true;
    return;
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
    const knob = c.kind === "knob";
    const actions = pad.actions[c.id] || {};
    if (knob) {
      svg("circle", { cx: x + w / 2, cy: y + h / 2, r: Math.min(w, h) / 2 }, group);
    } else {
      svg("rect", { x, y, width: w, height: h }, group);
    }
    // On a knob the corner of the box lies outside the circle, so the label goes inside.
    const label = knob ? { x: x + w / 2, y: y + 15, "text-anchor": "middle" } : { x: x + 6, y: y + 14 };
    text(c.label, { class: "label", ...label }, group);
    if (actions.press) {
      // Below a knob's label.
      const press = { x: x + w / 2, y: y + h / 2 + (knob ? 10 : 5), "text-anchor": "middle", class: "action" };
      text(labels[actions.press] || actions.press, press, group);
    }
    const ends = knob ? drawTurns(x + w / 2, y + h / 2, Math.min(w, h) / 2, actions, root) : {};
    group.classList.toggle("stop", Object.values(actions).includes("stop"));
    controls.set(c.id, { group, ends, actions: Object.values(actions) });
  }
  const shape = pad.layout.outline;
  const margin = OUTLINE * UNIT;
  const box = shape
    ? { x: shape.x * UNIT, y: shape.y * UNIT, width: shape.w * UNIT, height: shape.h * UNIT }
    : { x: -margin, y: -margin, width: width + 2 * margin, height: height + 2 * margin };
  const outline = shape
    ? svg("path", { class: "outline", d: shape.path, transform: `scale(${UNIT})` }, root)
    : svg("rect", { class: "outline", x: box.x + 1, y: box.y + 1, width: box.width - 2, height: box.height - 2 }, root);
  // First child, so it lies behind the controls.
  root.prepend(outline);
  root.setAttribute("viewBox", `${box.x} ${box.y} ${box.width} ${box.height}`);
}

// Above a knob, outside its circle: an arc with a head at each end, labelled
// with what that turn does, anticlockwise on the left. Lines and filled heads
// in one colour, so the drawing also serves as a template for marking the pad.
// Outside the knob's group, whose colours for STOP or the step would hide it.
function drawTurns(cx, cy, r, actions, root) {
  const radius = r + TURN_GAP;
  // Angles from the top, clockwise; as "x,y" in a path.
  const at = (angle, distance) => [cx + distance * Math.sin(angle), cy - distance * Math.cos(angle)];
  // Where the arc ends and the head begins.
  const neck = TURN_ANGLE - TURN_HEAD / radius;
  const group = svg("g", { class: "turns" }, root);
  svg("path", { class: "arc", d: `M${at(-neck, radius)} A${radius} ${radius} 0 0 1 ${at(neck, radius)}` }, group);
  const ends = {};
  for (const [part, side] of [["ccw", -1], ["cw", 1]]) {
    const node = svg("g", {}, group);
    const tip = at(side * TURN_ANGLE, radius);
    const wing = (offset) => at(side * neck, radius + offset);
    svg("path", { class: "head", d: `M${tip} L${wing(TURN_HEAD / 2)} L${wing(-TURN_HEAD / 2)} Z` }, node);
    const [x, y] = at(side * TURN_ANGLE, radius + TURN_LABEL);
    const label = text(turnLabel(actions[part]), { x, y, "text-anchor": "middle", "dominant-baseline": "central" }, node);
    ends[part] = { node, label, action: actions[part] };
  }
  return ends;
}

// A knob on selected_plus/minus moves whichever axis is selected at the time.
function turnLabel(action, axis = "") {
  if (action === "selected_plus") return `${axis}+`;
  if (action === "selected_minus") return `${axis}−`;
  return labels[action] || action || "";
}

function labelTurns(state) {
  for (const { ends } of controls.values()) {
    for (const end of Object.values(ends)) end.label.textContent = turnLabel(end.action, state.selected_axis);
  }
}

function showEvent(event) {
  const control = event.control && controls.get(event.control);
  if (control) {
    if (event.part === "press") {
      control.group.classList.toggle("active", event.pressed);
    } else if (event.pressed) {
      // Knob detents have no lasting "down" state: flash the knob and the end of its arrow.
      control.group.classList.add("active");
      control.ends[event.part]?.node.classList.add("on");
      clearTimeout(control.timer);
      control.timer = setTimeout(() => {
        control.group.classList.remove("active");
        for (const end of Object.values(control.ends)) end.node.classList.remove("on");
      }, 250);
    }
  }
  if (!event.pressed) return;
  const list = $("recent");
  list.querySelector(".empty")?.remove();
  const action = event.action ? labels[event.action] || event.action : t("ui.unassigned");
  list.prepend(el("li", {}, el("span", {}, `${event.name} (${event.code})`), el("span", {}, action)));
  while (list.children.length > RECENT) list.lastChild.remove();
  if (waiter) waiter(event);
}

function say(message, kind = "") {
  const node = $("setup-message");
  node.textContent = message;
  node.className = `message ${kind}`;
}

// -- setup: keys --------------------------------------------------------------

function renderKeys() {
  const rows = ACTIONS.map((action) => {
    const keys = config.input.keys[action] || [];
    return el(
      "tr",
      {},
      el("th", { scope: "row" }, labels[action]),
      el("td", { class: "mono" }, keys.join(", ") || "–"),
      el("td", {}, el("button", { type: "button", onclick: () => learnKey(action) }, t("ui.learn"))),
    );
  });
  $("keys").replaceChildren(...rows);
}

async function learnKey(action) {
  const started = await send("POST", "/api/learn", { seconds: LEARN_S });
  if (started.status !== 200) return failed(started);
  say(t("ui.press_key", { action: labels[action] }), "wait");
  const timer = setTimeout(() => endWait(t("ui.timeout")), LEARN_S * 1000);
  waiter = async (event) => {
    clearTimeout(timer);
    waiter = null;
    await send("POST", "/api/learn", { seconds: 0 });
    await assign(action, event.name);
  };
}

async function assign(action, key, replace = false) {
  const result = await send("PUT", `/api/keys/${action}`, { keys: [key], replace });
  if (result.status === 409 && result.data.detail?.conflicts) {
    const other = result.data.detail.conflicts[key];
    const question = t("ui.taken", { key, action: labels[other], target: labels[action] });
    if (window.confirm(question)) return assign(action, key, true);
    return say(t("ui.unchanged"));
  }
  if (result.status !== 200) return failed(result);
  await changed(result.data);
  say(t("ui.assigned", { key, action: labels[action] }), "ok");
}

// -- setup: directions --------------------------------------------------------

function renderDirections() {
  const rows = ["X", "Y", "Z"].map((axis) => {
    const inverted = config.jog.invert.includes(axis);
    return el(
      "tr",
      {},
      el("th", { scope: "row" }, axis),
      el("td", {}, inverted ? t("ui.inverted") : "–"),
      el("td", {}, el("button", { type: "button", onclick: () => checkDirection(axis) }, t("ui.check"))),
    );
  });
  $("directions").replaceChildren(...rows);
}

function checkDirection(axis) {
  const plus = `${axis.toLowerCase()}_plus`;
  say(t("ui.press_axis", { action: labels[plus] }), "wait");
  waiter = (event) => {
    if (event.action !== plus) return;
    waiter = null;
    const buttons = directionAnswers(axis).map((answer) =>
      el("button", { type: "button", onclick: () => answerDirection(axis, answer.right) }, answer.text),
    );
    buttons.push(el("button", { type: "button", onclick: () => endWait(t("ui.dir.nothing_hint")) }, t("ui.dir.nothing")));
    $("answers").replaceChildren(...buttons);
    say(t("ui.what_moved"), "wait");
  };
}

async function answerDirection(axis, right) {
  $("answers").replaceChildren();
  if (right) return say(t("ui.direction_ok", { axis }), "ok");
  const invert = new Set(config.jog.invert);
  if (invert.has(axis)) invert.delete(axis);
  else invert.add(axis);
  const result = await send("PUT", "/api/invert", { axes: [...invert] });
  if (result.status !== 200) return failed(result);
  await changed(result.data);
  say(t("ui.direction_fixed", { axis }), "ok");
}

// -- setup: shared ------------------------------------------------------------

function endWait(message) {
  waiter = null;
  $("answers").replaceChildren();
  send("POST", "/api/learn", { seconds: 0 });
  say(message);
}

function failed(result) {
  if (result.status === 403) return say(t("ui.forbidden"), "error");
  const error = typeof result.data.detail === "string" ? result.data.detail : result.status;
  say(t("ui.error", { error }), "error");
}

async function changed(newConfig) {
  config = newConfig;
  drawPad(await getJson(`/api/pad?lang=${document.documentElement.lang}`));
  renderKeys();
  renderDirections();
  refreshState();
}

// -- language -----------------------------------------------------------------

// Storage can be unavailable (private windows, blocked site data); the page then
// falls back to the browser's language on every visit.
function storedLanguage() {
  try {
    return localStorage.getItem(LANGUAGE_KEY);
  } catch {
    return null;
  }
}

function pickLanguage(codes, fallback) {
  const stored = storedLanguage();
  if (codes.includes(stored)) return stored;
  for (const tag of navigator.languages || []) {
    const code = tag.slice(0, 2).toLowerCase();
    if (codes.includes(code)) return code;
  }
  return fallback;
}

function setUpLanguages(available, current) {
  const select = $("language");
  const label = (l) => `${l.code.toUpperCase()} · ${l.name}`;
  select.replaceChildren(...available.map((l) => el("option", { value: l.code }, label(l))));
  select.value = current;
  select.addEventListener("change", () => {
    try {
      localStorage.setItem(LANGUAGE_KEY, select.value);
    } catch {
      // Not remembered; the URL carries the choice for this visit.
      location.assign(`${location.pathname}?lang=${select.value}`);
      return;
    }
    // Without ?lang, which would otherwise win over the stored choice.
    location.assign(location.pathname);
  });
}

// -- theme --------------------------------------------------------------------

// "auto" follows the browser. Without storage the choice lasts for this visit.
function storedTheme() {
  try {
    const theme = localStorage.getItem(THEME_KEY);
    return theme === "light" || theme === "dark" ? theme : "auto";
  } catch {
    return "auto";
  }
}

function applyTheme(theme) {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

function setUpThemes() {
  const select = $("theme");
  const names = { auto: t("ui.theme_auto"), light: t("ui.theme_light"), dark: t("ui.theme_dark") };
  select.setAttribute("aria-label", t("ui.theme"));
  select.replaceChildren(...Object.entries(names).map(([value, name]) => el("option", { value }, name)));
  select.value = storedTheme();
  select.addEventListener("change", () => {
    applyTheme(select.value);
    try {
      localStorage.setItem(THEME_KEY, select.value);
    } catch {
      // Not remembered beyond this visit.
    }
  });
}

// -- footer -------------------------------------------------------------------

function showLinks(version) {
  const links = version.links;
  const set = (id, href, label) => {
    if (!href) return;
    const a = $(id);
    a.href = href;
    a.textContent = label;
    a.target = "_blank";
    a.rel = "noopener";
    a.hidden = false;
  };
  set("link-repo", links.Homepage, t("ui.link.repo"));
  // The issue form takes field values from the URL, so the version is filled in.
  const bug = links.Issues &&
    `${links.Issues}/new?template=bug_report.yml&version=${encodeURIComponent(version.version)}`;
  set("link-bug", bug, t("ui.link.bug"));
  set("link-changelog", links.Changelog, t("ui.link.changelog"));
}

// -- setup: Mainsail and Fluidd ------------------------------------------------

async function renderMainsail() {
  const button = $("mainsail-button");
  let panel;
  try {
    panel = await getJson("/api/panel");
  } catch {
    $("mainsail-status").textContent = t("ui.panel_unknown");
    button.hidden = true;
    return;
  }
  $("mainsail-status").textContent = panel.url ? t("ui.panel_added") : t("ui.panel_missing");
  button.textContent = panel.url ? t("ui.panel_remove") : t("ui.panel_add");
  button.onclick = () => togglePanel(Boolean(panel.url));
  button.hidden = false;
}

async function togglePanel(added) {
  const result = await send(added ? "DELETE" : "PUT", "/api/panel");
  if (result.status === 409) return say(t("ui.panel_local"), "error");
  if (result.status !== 200) return failed(result);
  say(added ? t("ui.panel_removed") : t("ui.panel_done"), "ok");
  renderMainsail();
}

// -- switch -------------------------------------------------------------------

async function setSwitch(on) {
  const result = await send("PUT", "/api/switch", { on });
  const message = $("switch-message");
  if (result.status === 403) message.textContent = t("ui.forbidden");
  else if (result.status !== 200) message.textContent = t("ui.error", { error: result.data.detail ?? result.status });
  else message.textContent = "";
  refreshState();
}

// -- live state ---------------------------------------------------------------

// Ranked by size, not by position in `steps`, which may run from large to small.
function stepSize(step) {
  const steps = [...new Set(config.jog.steps)].sort((a, b) => a - b);
  const i = steps.indexOf(step);
  if (i < 0 || steps.length < 2) return null;
  if (i === 0) return "small";
  return i === steps.length - 1 ? "large" : "middle";
}

// A knob on the selected axis takes that axis's colour; a control that moves
// two axes takes none.
function colourControls(state) {
  const size = stepSize(state.step);
  for (const { group, actions } of controls.values()) {
    const axes = new Set(
      actions
        .map((a) => (a.startsWith("selected_") ? state.selected_axis : a.match(/^([xyz])_/)?.[1]))
        .filter(Boolean)
        .map((axis) => axis.toLowerCase()),
    );
    for (const axis of ["x", "y", "z"]) {
      group.classList.toggle(`axis-${axis}`, axes.size === 1 && axes.has(axis));
    }
    for (const s of ["small", "middle", "large"]) {
      group.classList.toggle(`step-${s}`, actions.includes("step") && size === s);
    }
  }
}

async function refreshState() {
  try {
    const s = await getJson("/api/state");
    const switched = { true: t("ui.switch_on"), false: t("ui.switch_off") };
    switchedOn = s.switched_on;
    $("switch").textContent = switched[switchedOn] ?? "–";
    $("switch").hidden = s.has_switch;
    const button = $("switch-button");
    button.textContent = switched[switchedOn] ?? "–";
    button.setAttribute("aria-pressed", String(switchedOn === true));
    button.hidden = !s.has_switch;
    $("switched-off").hidden = switchedOn !== false;
    document.body.classList.toggle("switched-off", switchedOn === false);
    $("step").textContent = `${s.step} mm`;
    const size = stepSize(s.step);
    if (size) $("step").dataset.size = size;
    else delete $("step").dataset.size;
    colourControls(s);
    labelTurns(s);
    $("axis").textContent = s.selected_axis;
    $("home").textContent = s.home_selection === null ? "–" : s.home_selection.join(" ") || t("ui.home_all");
    $("refusal").textContent = s.last_refusal || "–";
  } catch {
    // The live link shows the outage; keep the last values.
  }
}

function connect() {
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
    showEvent(JSON.parse(message.data));
    refreshState();
  };
}

async function main() {
  document.body.classList.toggle("panel", new URLSearchParams(location.search).get("view") === "panel");
  let version;
  let available;
  [config, version, available] = await Promise.all([
    getJson("/api/config"),
    getJson("/api/version"),
    getJson("/api/languages"),
  ]);
  const codes = available.map((l) => l.code);
  const fromUrl = new URLSearchParams(location.search).get("lang");
  const language = codes.includes(fromUrl) ? fromUrl : pickLanguage(codes, config.server.language);
  catalog = await getJson(`/api/messages?lang=${language}`);
  document.documentElement.lang = language;
  setUpLanguages(available, language);
  setUpThemes();
  labels = actionLabels();
  $("version").textContent = version.version;
  showLinks(version);
  $("label-step").textContent = t("ui.step");
  $("label-switch").textContent = t("ui.switch");
  // The camera panel in Mainsail and Fluidd hides the header; its label leads to the full page.
  if (document.body.classList.contains("panel")) {
    const attrs = { href: "/", target: "_blank", rel: "noopener", title: t("ui.open_page") };
    $("label-switch").replaceChildren(el("a", attrs, `${t("ui.switch")} ↗`));
  }
  $("switched-off-text").textContent = t("ui.switch_off_note");
  $("switch-on").textContent = t("ui.switch_turn_on");
  $("switch-on").onclick = () => setSwitch(true);
  $("switch-button").onclick = () => setSwitch(switchedOn === false);
  $("label-axis").textContent = t("ui.axis");
  $("label-home").textContent = t("ui.home");
  $("label-refusal").textContent = t("ui.refusal");
  $("label-recent").textContent = t("ui.recent");
  $("label-setup").textContent = t("ui.setup");
  $("label-keys").textContent = t("ui.keys");
  $("label-directions").textContent = t("ui.directions");
  $("setup-note").textContent = t("ui.setup_note");
  $("label-mainsail").textContent = t("ui.panel");
  $("link").textContent = t("ui.disconnected");
  $("recent").append(el("li", { class: "empty" }, t("ui.recent_empty")));

  drawPad(await getJson(`/api/pad?lang=${document.documentElement.lang}`));
  renderKeys();
  renderDirections();
  renderMainsail();
  connect();
  refreshState();
  setInterval(refreshState, 2000);
}

// Before main() waits for anything, so the page does not flash in the other theme.
applyTheme(storedTheme());
main();
