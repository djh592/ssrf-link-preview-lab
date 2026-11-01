import { SCENES } from "./topology-scene.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const DEVICES = {
  browser: { label: "Browser", symbol: "laptop" },
  preview: { label: "Preview", symbol: "preview" },
  dns: { label: "DNS", symbol: "dns" },
  "external-page": { label: "Attacker web", symbol: "web" },
  "internal-report": { label: "Private report", symbol: "report" },
  "public-web": { label: "Internet", symbol: "cloud" },
};
const DEFENSE_NAMES = {
  none: "No lab check", initial: "Initial URL", each_hop: "Each hop", bound: "Check & bind",
  no_redirects: "No redirects",
};
const EXTERNAL_NAMES = {
  page: "HTTP 200", redirect_page: "302 → page", redirect_internal: "302 → report",
};

function add(parent, name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  parent.append(node);
  return node;
}

function text(parent, x, y, value, className) {
  add(parent, "text", { x, y, class: className }).textContent = value;
}

function line(parent, points, className) {
  add(parent, "polyline", {
    points: points.map(([x, y]) => `${x},${y}`).join(" "),
    class: className,
  });
}

function drawLaptop(group, x, y) {
  add(group, "rect", { x, y, width: 82, height: 57, rx: 5, class: "device-shell" });
  add(group, "rect", { x: x + 7, y: y + 7, width: 68, height: 42, rx: 2, class: "screen" });
  add(group, "rect", { x: x + 14, y: y + 15, width: 26, height: 3, rx: 1, class: "screen-detail" });
  add(group, "rect", { x: x + 14, y: y + 24, width: 54, height: 17, rx: 2, class: "screen-preview" });
  add(group, "path", { d: `M${x - 5} ${y + 58}h92l-8 7h-76z`, class: "laptop-base" });
}

function drawServer(group, x, y, symbol) {
  add(group, "rect", { x, y, width: 72, height: 88, rx: 6, class: "device-shell" });
  add(group, "rect", { x: x + 9, y: y + 9, width: 54, height: 46, rx: 3, class: "server-face" });
  if (symbol === "web") {
    add(group, "circle", { cx: x + 36, cy: y + 32, r: 13, class: "role-line" });
    add(group, "ellipse", { cx: x + 36, cy: y + 32, rx: 6, ry: 13, class: "role-line" });
    add(group, "line", { x1: x + 23, y1: y + 32, x2: x + 49, y2: y + 32, class: "role-line" });
  } else if (symbol === "report") {
    add(group, "path", {
      d: `M${x + 27} ${y + 17}h16l7 7v24h-23z M${x + 43} ${y + 17}v7h7`,
      class: "role-line",
    });
    for (const offset of [32, 39]) {
      add(group, "line", { x1: x + 32, y1: y + offset, x2: x + 44, y2: y + offset, class: "role-line" });
    }
  } else {
    add(group, "rect", { x: x + 17, y: y + 18, width: 38, height: 28, rx: 2, class: "preview-card" });
    add(group, "line", { x1: x + 17, y1: y + 25, x2: x + 55, y2: y + 25, class: "role-line" });
    add(group, "rect", { x: x + 22, y: y + 30, width: 11, height: 10, rx: 1, class: "preview-image" });
    for (const offset of [33, 39]) {
      add(group, "line", { x1: x + 37, y1: y + offset, x2: x + 49, y2: y + offset, class: "role-line" });
    }
  }
  for (const offset of [63, 74]) {
    add(group, "line", { x1: x + 16, y1: y + offset, x2: x + 44, y2: y + offset, class: "server-slot" });
    add(group, "circle", { cx: x + 55, cy: y + offset, r: 2.5, class: "server-light" });
  }
}

function drawDns(group, x, y) {
  add(group, "rect", { x, y, width: 56, height: 60, rx: 6, class: "device-shell" });
  add(group, "circle", { cx: x + 28, cy: y + 26, r: 15, class: "dns-ring" });
  add(group, "circle", { cx: x + 28, cy: y + 26, r: 4, class: "dns-center" });
  for (const offset of [45, 52]) {
    add(group, "line", { x1: x + 16, y1: y + offset, x2: x + 40, y2: y + offset, class: "dns-slot" });
  }
}

function drawCloud(group, x, y) {
  add(group, "path", {
    d: `M${x + 18} ${y + 60}h46c12 0 18-8 18-18 0-10-7-17-16-18C${x + 61} ${y + 8} ${x + 42} ${y + 7} ${x + 31} ${y + 22}C${x + 15} ${y + 19} ${x + 4} ${y + 30} ${x + 5} ${y + 43}c1 10 6 17 13 17z`,
    class: "device-shell",
  });
  for (const offset of [29, 44, 59]) {
    add(group, "circle", { cx: x + offset, cy: y + 44, r: 2.5, class: "cloud-node" });
  }
  add(group, "line", { x1: x + 31, y1: y + 44, x2: x + 57, y2: y + 44, class: "cloud-connection" });
}

function deviceStatus(id, configuration, targets) {
  if (id === "preview") return DEFENSE_NAMES[configuration.defense];
  if (id === "dns") return configuration.dns_mode === "rebind" ? "Rebinding" : "Stable";
  if (id === "external-page") {
    const key = ["page", "redirect_page", "redirect_internal"]
      .find((name) => configuration.url === targets[name]);
    return key ? EXTERNAL_NAMES[key] : "Not targeted";
  }
  return null;
}

function drawDevice(svg, id, position, configuration, targets, observation, dnsSelected) {
  const { symbol, label } = DEVICES[id];
  const reached = observation?.destination === id &&
    ["responded", "response_failed"].includes(observation.outcome) &&
    observation.peer_address != null;
  const group = add(svg, "g", {
    class: ["device", `device-${id}`, reached ? "is-reached" : "",
      reached && observation.identity_matches === false ? "identity-warning" : "",
      id === "dns" && dnsSelected ? "is-observed" : ""].filter(Boolean).join(" "),
  });
  const { x, y } = position;
  if (symbol === "laptop") drawLaptop(group, x, y);
  else if (symbol === "cloud") drawCloud(group, x, y);
  else if (symbol === "dns") drawDns(group, x, y);
  else drawServer(group, x, y, symbol);
  const center = x + (symbol === "cloud" ? 44 : symbol === "laptop" ? 41 : symbol === "dns" ? 28 : 36);
  const labelY = position.labelAbove
    ? y - (symbol === "cloud" ? 8 : 26)
    : y + (symbol === "laptop" ? 88 : symbol === "dns" ? 79 : 113);
  text(group, center, labelY, label, "device-label");
  const status = deviceStatus(id, configuration, targets);
  if (status) text(group, center, labelY + 17, status, "node-status");
  if (reached && observation.identity_matches === false) {
    add(group, "circle", { cx: x + 68, cy: y + 4, r: 10, class: "identity-mark" });
    text(group, x + 68, y + 8, "!", "identity-symbol");
  }
}

function drawStructure(svg, scene) {
  const { testbed, previewContainer } = scene;
  add(svg, "rect", { x: testbed.x, y: testbed.y, width: testbed.width,
    height: testbed.height, rx: 8, class: "testbed-boundary" });
  text(svg, testbed.labelX, testbed.y + 25, "DOCKER LAB", "boundary-label");
  add(svg, "rect", { x: previewContainer.x, y: previewContainer.y,
    width: previewContainer.width, height: previewContainer.height,
    rx: 8, class: "preview-boundary" });
  text(svg, previewContainer.labelX, previewContainer.y + 18, "PREVIEW CONTAINER", "container-label");
  for (const [id, route] of Object.entries(scene.routes)) {
    line(svg, route, id === "browser" ? "attachment attachment-browser" :
      id === "dns" ? "attachment attachment-loopback" : "attachment");
  }
  for (const network of scene.networks) {
    line(svg, [[network.x1, network.y], [network.x2, network.y]], `network-bus bus-${network.id}`);
    for (const x of network.ports) {
      add(svg, "circle", { cx: x, cy: network.y, r: 4.5, class: `network-port port-${network.id}` });
    }
    text(svg, network.labelX ?? (network.x1 + network.x2) / 2,
      network.labelY ?? network.y + 27, network.label, "network-label");
  }
}

function drawDevices(svg, scene, configuration, targets, observation, dnsSelected) {
  for (const [id, position] of Object.entries(scene.devices)) {
    drawDevice(svg, id, position, configuration, targets, observation, dnsSelected);
  }
}

function pathPrefix(points, distance) {
  const result = [points[0]];
  let remaining = distance;
  for (let index = 1; index < points.length; index += 1) {
    const [x1, y1] = points[index - 1];
    const [x2, y2] = points[index];
    const length = Math.hypot(x2 - x1, y2 - y1);
    if (length <= remaining) {
      result.push(points[index]);
      remaining -= length;
    } else {
      const fraction = remaining / length;
      result.push([x1 + (x2 - x1) * fraction, y1 + (y2 - y1) * fraction]);
      break;
    }
  }
  return result;
}

function drawObservation(svg, scene, observation, focused) {
  if (["blocked", "unresolved"].includes(observation.outcome)) {
    if (focused) {
      const [x, y] = scene.stops[observation.destination] || scene.stops.default;
      return { x, y, type: observation.outcome };
    }
    return null;
  }
  const route = scene.routes[observation.destination];
  if (!route) return null;
  if (observation.outcome === "attempted") {
    if (!focused) return null;
    const partial = pathPrefix(route, 33);
    line(svg, partial, "trace-attempted");
    const [x, y] = partial.at(-1);
    return { x, y, type: "attempted" };
  }
  if (observation.peer_address == null) return null;
  const incomplete = observation.outcome === "response_failed";
  line(svg, route, focused
    ? incomplete ? "trace-incomplete" : "trace-reached"
    : incomplete ? "trace-history-incomplete" : "trace-history");
  if (!focused) return null;
  const [x, y] = route.at(-1);
  return { x, y, type: observation.outcome };
}

function drawMarker(svg, marker) {
  if (!marker) return;
  const { x, y, type } = marker;
  if (type === "responded" || type === "response_failed") {
    add(svg, "circle", { cx: x, cy: y, r: 6,
      class: type === "response_failed" ? "trace-endpoint is-incomplete" : "trace-endpoint" });
  } else if (type === "attempted") {
    add(svg, "circle", { cx: x, cy: y, r: 7, class: "attempt-mark" });
    text(svg, x, y + 4, "?", "attempt-symbol");
  } else {
    const unresolved = type === "unresolved";
    add(svg, "circle", { cx: x, cy: y, r: 12, class: unresolved ? "stop-mark is-unresolved" : "stop-mark" });
    text(svg, x, y + 5, unresolved ? "?" : "×", "stop-symbol");
  }
}

function addHitTargets(viewport, scene, selectedNode, onSelectNode) {
  for (const [id, position] of Object.entries(scene.devices)) {
    const [dx, dy, width, height, ringTop, ringHeight] = position.hit;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "node-hit";
    button.dataset.node = id;
    button.setAttribute("aria-label", DEVICES[id].label);
    button.setAttribute("aria-pressed", String(id === selectedNode));
    button.title = DEVICES[id].label;
    button.style.left = `${(position.x + dx) / scene.width * 100}%`;
    button.style.top = `${(position.y + dy) / scene.height * 100}%`;
    button.style.width = `${width / scene.width * 100}%`;
    button.style.height = `${height / scene.height * 100}%`;
    button.style.setProperty("--ring-top", `${ringTop / height * 100}%`);
    button.style.setProperty("--ring-height", `${ringHeight / height * 100}%`);
    button.addEventListener("click", (event) => onSelectNode(id, event.detail === 0));
    viewport.append(button);
  }
}

export function renderTopology(root, { trial, selectedEvent, selectedNode, configuration, targets, onSelectNode }) {
  const scene = root.clientWidth < 560
    ? SCENES.narrow
    : root.clientWidth < 900 ? SCENES.medium : SCENES.wide;
  const observation = selectedEvent?.kind === "request" ? selectedEvent.observation : null;
  const dnsSelected = selectedEvent?.kind === "dns";
  const focusNode = root.contains(document.activeElement) ? document.activeElement.dataset.node : null;
  const viewport = document.createElement("div");
  viewport.className = scene === SCENES.narrow ? "topology-viewport scene-narrow" : "topology-viewport";
  viewport.style.aspectRatio = `${scene.width} / ${scene.height}`;
  const svg = add(viewport, "svg", { viewBox: `0 0 ${scene.width} ${scene.height}`, "aria-hidden": "true" });
  drawStructure(svg, scene);
  if (trial) line(svg, scene.routes.browser, "trace-browser");
  const selectedTime = selectedEvent?.time ?? -Infinity;
  for (const previous of trial?.observations || []) {
    if (previous !== observation && previous.observed_at != null &&
      previous.observed_at < selectedTime &&
      ["responded", "response_failed"].includes(previous.outcome)) {
      drawObservation(svg, scene, previous, false);
    }
  }
  const marker = observation ? drawObservation(svg, scene, observation, true) : null;
  if (dnsSelected) line(svg, scene.routes.dns, "trace-dns");
  drawDevices(svg, scene, configuration, targets, observation, dnsSelected);
  drawMarker(svg, marker);
  addHitTargets(viewport, scene, selectedNode, onSelectNode);
  root.replaceChildren(viewport);
  if (focusNode) viewport.querySelector(`[data-node="${focusNode}"]`)?.focus({ preventScroll: true });
  const description = observation
    ? `${observation.resource} request ${observation.sequence + 1}: ${observation.outcome}; ${observation.destination || "peer location unknown"}`
    : dnsSelected
      ? `rebind.lab DNS answer ${selectedEvent.answer.query}: ${selectedEvent.answer.address}`
      : trial ? "Recorded trial without a selected network event" : "Network testbed before a trial";
  root.setAttribute("aria-label", description);
}
