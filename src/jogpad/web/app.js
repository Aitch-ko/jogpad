// Live view and setup of the pad. Nothing here moves the machine: moves only
// come from the pad itself, and learning keeps even those back.
"use strict";

const UNIT = 60; // pixels per key unit
const GAP = 6;
const RECENT = 12;
const LEARN_S = 30;
const LANGUAGE_KEY = "jogpad.language";
const SVG_NS = "http://www.w3.org/2000/svg";
const ACTIONS = [
  "x_plus", "x_minus", "y_plus", "y_minus", "z_plus", "z_minus", "e_plus", "e_minus",
  "selected_plus", "selected_minus", "select_next", "step", "home", "stop",
];

let catalog = {};
let config = null;
let labels = {};
let controls = new Map();
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
    if (c.kind === "knob") {
      svg("circle", { cx: x + w / 2, cy: y + h / 2, r: Math.min(w, h) / 2 }, group);
    } else {
      svg("rect", { x, y, width: w, height: h }, group);
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
}

function showEvent(event) {
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

// -- live state ---------------------------------------------------------------

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
  labels = actionLabels();
  $("version").textContent = version.version;
  showLinks(version);
  $("label-step").textContent = t("ui.step");
  $("label-axis").textContent = t("ui.axis");
  $("label-home").textContent = t("ui.home");
  $("label-refusal").textContent = t("ui.refusal");
  $("label-recent").textContent = t("ui.recent");
  $("label-setup").textContent = t("ui.setup");
  $("label-keys").textContent = t("ui.keys");
  $("label-directions").textContent = t("ui.directions");
  $("setup-note").textContent = t("ui.setup_note");
  $("link").textContent = t("ui.disconnected");
  $("recent").append(el("li", { class: "empty" }, t("ui.recent_empty")));

  drawPad(await getJson(`/api/pad?lang=${document.documentElement.lang}`));
  renderKeys();
  renderDirections();
  connect();
  refreshState();
  setInterval(refreshState, 2000);
}

main();
