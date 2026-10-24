const SVG_NS = "http://www.w3.org/2000/svg";

const DEVICES = {
  browser: { label: "Your browser", detail: "Host · localhost", kind: "laptop" },
  "external-page": { label: "Lab website", detail: "external-page", kind: "server" },
  preview: { label: "Preview server", detail: "Dual-homed container", kind: "server" },
  "internal-report": { label: "Internal report", detail: "Private lab service", kind: "server" },
  "public-web": { label: "Public websites", detail: "Remote peers", kind: "cloud" },
};

// Positions describe the testbed, never the route taken by a particular trial.
const SCENES = {
  wide: {
    width: 1120,
    height: 480,
    testbed: { x: 209, y: 164, w: 702, h: 294 },
    external: { x: 232, y: 214, w: 226, h: 225 },
    internal: { x: 665, y: 214, w: 224, h: 225 },
    devices: {
      browser: { x: 69, y: 68 },
      "external-page": { x: 313, y: 273 },
      preview: { x: 524, y: 259 },
      "internal-report": { x: 739, y: 273 },
      "public-web": { x: 973, y: 65 },
    },
    dns: { x: 492, y: 400, w: 150, h: 29 },
    stop: { x: 559, y: 302 },
    routes: {
      browser: [[151, 111], [183, 111], [183, 121], [559, 121], [559, 259]],
      "external-page": [[524, 307], [420, 307], [420, 317], [389, 317]],
      "internal-report": [[596, 307], [675, 307], [675, 317], [739, 317]],
      "public-web": [[580, 259], [580, 101], [973, 101]],
    },
  },
  narrow: {
    width: 420,
    height: 800,
    testbed: { x: 18, y: 234, w: 384, h: 548 },
    external: { x: 35, y: 497, w: 165, h: 263 },
    internal: { x: 220, y: 497, w: 165, h: 263 },
    devices: {
      browser: { x: 50, y: 63 },
      "external-page": { x: 82, y: 582 },
      preview: { x: 174, y: 320 },
      "internal-report": { x: 267, y: 582 },
      "public-web": { x: 274, y: 61 },
    },
    dns: { x: 135, y: 451, w: 150, h: 29 },
    stop: { x: 210, y: 364 },
    routes: {
      browser: [[132, 105], [150, 105], [150, 210], [193, 210], [193, 320]],
      "external-page": [[174, 368], [118, 368], [118, 582]],
      "internal-report": [[246, 368], [302, 368], [302, 582]],
      "public-web": [[227, 320], [227, 210], [314, 210], [314, 107]],
    },
  },
};

function element(name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function shape(parent, name, attributes) {
  const node = element(name, attributes);
  parent.append(node);
  return node;
}

function label(parent, x, y, content, className) {
  const node = shape(parent, "text", { x, y, class: className });
  node.textContent = content;
}

function path(parent, points, className) {
  shape(parent, "polyline", {
    points: points.map(([x, y]) => `${x},${y}`).join(" "),
    class: className,
  });
}

function region(parent, box, className, title, subtitle) {
  shape(parent, "rect", {
    x: box.x, y: box.y, width: box.w, height: box.h, rx: 8, class: className,
  });
  label(parent, box.x + 17, box.y + 23, title, "region-title");
  if (subtitle) label(parent, box.x + 17, box.y + 41, subtitle, "region-subtitle");
}

function drawLaptop(parent, x, y) {
  shape(parent, "rect", { x, y, width: 82, height: 55, rx: 5, class: "device-shell" });
  shape(parent, "rect", { x: x + 7, y: y + 7, width: 68, height: 40, rx: 2, class: "laptop-screen" });
  shape(parent, "rect", { x: x + 13, y: y + 13, width: 38, height: 3, rx: 1, class: "screen-line" });
  shape(parent, "rect", { x: x + 13, y: y + 23, width: 53, height: 16, rx: 2, class: "screen-page" });
  shape(parent, "path", { d: `M${x - 5} ${y + 56}h92l-8 8h-76z`, class: "laptop-base" });
}

function drawServer(parent, x, y) {
  shape(parent, "rect", { x, y, width: 72, height: 88, rx: 5, class: "device-shell" });
  for (const offset of [12, 37, 62]) {
    shape(parent, "rect", { x: x + 8, y: y + offset, width: 56, height: 17, rx: 3, class: "server-bay" });
    shape(parent, "circle", { cx: x + 54, cy: y + offset + 8.5, r: 2.5, class: "server-light" });
    shape(parent, "line", { x1: x + 15, y1: y + offset + 8.5, x2: x + 34, y2: y + offset + 8.5, class: "server-slot" });
  }
  shape(parent, "path", { d: `M${x + 10} ${y + 89}v5m52-5v5`, class: "server-feet" });
}

function drawCloud(parent, x, y) {
  shape(parent, "path", {
    d: `M${x + 19} ${y + 58}h45c12 0 18-8 18-18 0-9-7-16-16-17C${x + 60} ${y + 9} ${x + 42} ${y + 7} ${x + 31} ${y + 21}C${x + 15} ${y + 18} ${x + 4} ${y + 29} ${x + 6} ${y + 42}c1 9 6 16 13 16z`,
    class: "device-shell",
  });
  shape(parent, "circle", { cx: x + 29, cy: y + 42, r: 3, class: "cloud-point" });
  shape(parent, "circle", { cx: x + 44, cy: y + 42, r: 3, class: "cloud-point" });
  shape(parent, "circle", { cx: x + 59, cy: y + 42, r: 3, class: "cloud-point" });
  shape(parent, "path", { d: `M${x + 32} ${y + 42}h9m6 0h9`, class: "cloud-link" });
}

function drawDevice(parent, id, position, observation) {
  const info = DEVICES[id];
  const active = observation?.destination === id &&
    ["responded", "response_failed"].includes(observation.outcome) &&
    observation.peer_address !== null;
  const classes = ["device", `device-${id}`];
  if (active) classes.push("is-reached");
  if (active && observation.identity_matches === false) classes.push("identity-warning");
  const group = shape(parent, "g", { class: classes.join(" ") });

  if (info.kind === "laptop") drawLaptop(group, position.x, position.y);
  else if (info.kind === "cloud") drawCloud(group, position.x, position.y);
  else drawServer(group, position.x, position.y);

  const center = position.x + (info.kind === "cloud" ? 44 : info.kind === "laptop" ? 41 : 36);
  const titleY = position.y + (info.kind === "server" ? 113 : 83);
  label(group, center, titleY, info.label, "device-label");
  label(group, center, titleY + 17, active ? observation.peer_address : info.detail, "device-detail");
  if (active && observation.identity_matches === false) {
    shape(group, "circle", { cx: position.x + 69, cy: position.y + 3, r: 10, class: "identity-mark" });
    label(group, position.x + 69, position.y + 7, "!", "identity-symbol");
  }
}

function drawStructure(svg, scene, observation, dnsAnswer, dnsCount) {
  shape(svg, "rect", { x: 0, y: 0, width: scene.width, height: scene.height, class: "scene-background" });
  region(svg, scene.testbed, "testbed-boundary", "DOCKER TESTBED", "Three containers · isolated lab networks");
  region(svg, scene.external, "segment segment-external", scene === SCENES.wide ? "ATTACKER-CONTROLLED LAB" : "EXTERNAL LAB", "external_zone · isolated");
  region(svg, scene.internal, "segment segment-internal", scene === SCENES.wide ? "PRIVATE SERVICE NETWORK" : "PRIVATE NETWORK", "internal_zone · isolated");

  const browser = scene.devices.browser;
  const publicWeb = scene.devices["public-web"];
  label(svg, browser.x - 5, browser.y - 20, "OPERATOR DEVICE", "environment-label");
  label(svg, publicWeb.x - 5, publicWeb.y - 18, "PUBLIC INTERNET", "environment-label");
  for (const [id, points] of Object.entries(scene.routes)) {
    path(svg, points, id === "browser" ? "attachment attachment-browser" : "attachment");
  }
  if (scene === SCENES.wide) {
    label(svg, 266, 107, "localhost UI", "connection-label");
    label(svg, 719, 87, "public_egress", "connection-label");
  }
  for (const [id, position] of Object.entries(scene.devices)) {
    drawDevice(svg, id, position, observation);
  }

  const dns = scene.dns;
  const group = shape(svg, "g", { class: `dns-module ${dnsAnswer ? "is-selected" : ""}` });
  shape(group, "rect", {
    x: dns.x, y: dns.y, width: dns.w, height: dns.h, rx: 5, class: "dns-shell",
  });
  shape(group, "circle", { cx: dns.x + 15, cy: dns.y + 14.5, r: 6, class: "dns-icon" });
  label(group, dns.x + 15, dns.y + 18, "A", "dns-icon-letter");
  const content = dnsAnswer
    ? `#${dnsAnswer.query} → ${dnsAnswer.address}`
    : dnsCount ? `rebind.lab · ${dnsCount} answers` : "rebind.lab · loopback";
  label(group, dns.x + 27, dns.y + 19, content, "dns-text");
}

function prefix(points, distance) {
  const visible = [points[0]];
  let remaining = distance;
  for (let index = 1; index < points.length; index += 1) {
    const [startX, startY] = points[index - 1];
    const [endX, endY] = points[index];
    const length = Math.hypot(endX - startX, endY - startY);
    if (length <= remaining) {
      visible.push(points[index]);
      remaining -= length;
    } else {
      const fraction = remaining / length;
      visible.push([startX + (endX - startX) * fraction, startY + (endY - startY) * fraction]);
      break;
    }
  }
  return visible;
}

function drawStop(svg, scene, outcome) {
  const { x, y } = scene.stop;
  shape(svg, "circle", {
    cx: x, cy: y, r: 13,
    class: outcome === "blocked" ? "trace-stop" : "trace-stop trace-unresolved",
  });
  label(svg, x, y + 5, outcome === "blocked" ? "×" : "?", "trace-stop-symbol");
}

function drawObservedPath(svg, scene, observation, focused) {
  if (["blocked", "unresolved"].includes(observation.outcome)) {
    if (focused) drawStop(svg, scene, observation.outcome);
    return;
  }
  const route = scene.routes[observation.destination];
  if (!route) {
    if (focused) {
      if (observation.outcome === "attempted") {
        const { x, y } = scene.stop;
        shape(svg, "circle", { cx: x, cy: y, r: 9, class: "trace-attempt-mark" });
        label(svg, x, y + 4, "?", "trace-attempt-symbol");
      }
      const description = observation.peer_address === null
        ? "Peer route not confirmed" : "Peer outside mapped networks";
      label(svg, scene.width / 2, scene.height - 10, description, "unmapped-note");
    }
    return;
  }
  if (observation.outcome === "attempted") {
    if (!focused) return;
    const partial = prefix(route, 44);
    path(svg, partial, "trace-attempted");
    const [x, y] = partial.at(-1);
    shape(svg, "circle", { cx: x, cy: y, r: 7, class: "trace-attempt-mark" });
    label(svg, x, y + 4, "?", "trace-attempt-symbol");
    return;
  }
  if (observation.peer_address === null) return;
  const incomplete = observation.outcome === "response_failed";
  const className = focused
    ? incomplete ? "trace-incomplete" : "trace-reached"
    : incomplete ? "trace-history-incomplete" : "trace-history";
  path(svg, route, className);
  if (focused) {
    const [x, y] = route.at(-1);
    shape(svg, "circle", {
      cx: x, cy: y, r: 6,
      class: incomplete ? "trace-endpoint trace-incomplete-endpoint" : "trace-endpoint",
    });
  }
}

export function renderTopology(root, trial, selectedEvent) {
  const scene = root.clientWidth < 900 ? SCENES.narrow : SCENES.wide;
  const observations = trial?.observations || [];
  const selected = selectedEvent?.kind === "request" ? selectedEvent.observation : null;
  const dnsAnswer = selectedEvent?.kind === "dns" ? selectedEvent.answer : null;
  const svg = element("svg", {
    viewBox: `0 0 ${scene.width} ${scene.height}`,
    class: scene === SCENES.narrow ? "scene-narrow" : "scene-wide",
    "aria-hidden": "true",
  });

  drawStructure(svg, scene, selected, dnsAnswer, trial?.dns_answers.length || 0);
  if (trial) path(svg, scene.routes.browser, "trace-browser");
  const selectedTime = selectedEvent?.time ?? -Infinity;
  for (const observation of observations) {
    if (observation === selected) continue;
    if (observation.observed_at !== null && observation.observed_at < selectedTime &&
      ["responded", "response_failed"].includes(observation.outcome)) {
      drawObservedPath(svg, scene, observation, false);
    }
  }
  if (selected) drawObservedPath(svg, scene, selected, true);

  root.replaceChildren(svg);
  const description = selected
    ? `${selected.resource} request ${selected.sequence + 1}: ${selected.outcome}; ${selected.destination || "peer location unknown"}`
    : dnsAnswer
      ? `rebind.lab DNS answer ${dnsAnswer.query}: ${dnsAnswer.address}`
      : trial ? "Trial recorded without a selected network event" : "Docker testbed before a trial";
  root.setAttribute("aria-label", description);
}
