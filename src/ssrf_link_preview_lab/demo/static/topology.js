const SVG_NS = "http://www.w3.org/2000/svg";

const NETWORKS = [
  { id: "external-page", zone: "external_zone", label: "External page", kind: "Lab service" },
  { id: "internal-report", zone: "internal_zone", label: "Internal report", kind: "Lab service" },
  { id: "public-web", zone: "public_egress", label: "Public web", kind: "External peer" },
];

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  return element;
}

function addText(parent, x, y, value, className) {
  const label = svgElement("text", { x, y, class: className });
  label.textContent = value;
  parent.append(label);
}

function addRect(parent, box, className, radius = 5) {
  parent.append(svgElement("rect", {
    x: box.x, y: box.y, width: box.w, height: box.h, rx: radius, class: className,
  }));
}

function addLine(parent, points, className) {
  parent.append(svgElement("polyline", {
    points: points.map(([x, y]) => `${x},${y}`).join(" "),
    class: className,
  }));
}

function geometry(width, includeUnmapped) {
  const mobile = width < 680;
  const height = mobile
    ? includeUnmapped ? 956 : 816
    : includeUnmapped ? 566 : 440;
  const browser = mobile
    ? { x: (width - 150) / 2, y: 18, w: 150, h: 54 }
    : { x: 18, y: 208, w: 142, h: 56 };
  const preview = mobile
    ? { x: (width - 212) / 2, y: 157, w: 212, h: 144 }
    : { x: Math.max(190, Math.round(width * 0.28)), y: 172, w: 196, h: 138 };
  const browserPoints = mobile
    ? [[browser.x + browser.w / 2, browser.y + browser.h], [preview.x + preview.w / 2, preview.y]]
    : [[browser.x + browser.w, browser.y + browser.h / 2], [preview.x, preview.y + preview.h / 2]];
  const zones = {};
  const zoneX = Math.max(preview.x + 228, Math.round(width * 0.59));
  const entries = includeUnmapped
    ? [...NETWORKS, { id: "other-address", zone: "unmapped", label: "Unmapped peer", kind: "Unknown network" }]
    : NETWORKS;

  for (const [index, entry] of entries.entries()) {
    const zone = mobile
      ? { x: 44, y: 354 + index * 140, w: width - 56, h: 102 }
      : { x: zoneX, y: 48 + index * 126, w: width - zoneX - 16, h: 104 };
    const publicNode = entry.id === "public-web";
    const node = mobile
      ? { x: zone.x + (publicNode ? 84 : 22), y: zone.y + 38,
          w: zone.w - (publicNode ? 99 : 44), h: 52 }
      : { x: zone.x + zone.w - 160, y: zone.y + 39, w: 144, h: 52 };
    const port = mobile
      ? { x: preview.x, y: preview.y + 33 + index * 32 }
      : { x: preview.x + preview.w, y: preview.y + 23 + index * 30 };
    const points = mobile
      ? [
          [port.x, port.y],
          [12 + index * 6, port.y],
          [12 + index * 6, zone.y + 64],
          [zone.x, zone.y + 64],
          [node.x, zone.y + 64],
        ]
      : [
          [port.x, port.y],
          [zone.x + 16, zone.y + 65],
          [node.x, zone.y + 65],
        ];
    zones[entry.id] = { entry, zone, node, port, points };
  }
  return { mobile, width, height, browser, browserPoints, preview, zones };
}

function drawStructure(svg, layout, dnsCount, selected) {
  const { browser, browserPoints, preview, zones, mobile } = layout;
  addText(svg, mobile ? 18 : preview.x, mobile ? 135 : 27, "COMPOSE NETWORKS", "boundary-label");

  for (const { entry, zone, node, points } of Object.values(zones)) {
    addRect(svg, zone, `network-zone zone-${entry.id}`, 5);
    addText(svg, zone.x + (entry.id === "public-web" ? 7 : 15), zone.y + 22,
      entry.zone, `zone-label ${entry.id === "public-web" ? "egress-label" : ""}`);
    if (entry.id === "public-web") {
      const boundary = node.x - 10;
      addLine(svg, [[boundary, zone.y + 33], [boundary, zone.y + zone.h - 8]], "internet-boundary");
      addText(svg, boundary + 10, zone.y + 22, "INTERNET", "internet-label");
      addLine(svg, [...points.slice(0, mobile ? 4 : 2), [boundary, zone.y + 65]], "network-attachment");
    } else if (entry.id !== "other-address") {
      addLine(svg, points, "network-attachment");
    }
  }

  addLine(svg, browserPoints, "browser-attachment");

  addRect(svg, browser, "browser-node", 5);
  addText(svg, browser.x + 15, browser.y + 26, "Browser", "node-label");
  addText(svg, browser.x + 15, browser.y + 43, "localhost", "node-subtitle");

  addRect(svg, preview, `preview-node ${selected?.outcome === "blocked" ? "has-block" : ""}`, 6);
  addText(svg, preview.x + 16, preview.y + 27, "Preview", "node-label");
  addText(svg, preview.x + 16, preview.y + 46, "Container · port 8000", "node-subtitle");
  const dns = { x: preview.x + 14, y: preview.y + 69, w: preview.w - 28, h: 56 };
  addRect(svg, dns, "dns-node", 4);
  addText(svg, dns.x + 11, dns.y + 22, "rebind.lab DNS", "dns-label");
  addText(svg, dns.x + 11, dns.y + 42, `Loopback UDP · ${dnsCount} answer${dnsCount === 1 ? "" : "s"}`, "node-subtitle");

  for (const { entry, node, port } of Object.values(zones)) {
    const selectedNode = selected?.destination === entry.id &&
      ["responded", "response_failed"].includes(selected.outcome);
    const candidateNode = selected?.destination === entry.id &&
      ["blocked", "attempted"].includes(selected.outcome);
    const mismatch = selectedNode && selected.identity_matches === false;
    addRect(svg, node, `service-node ${selectedNode ? "selected" : ""} ${candidateNode ? "candidate" : ""} ${mismatch ? "identity-mismatch" : ""}`, 4);
    addText(svg, node.x + 12, node.y + 22, entry.label, "node-label");
    const address = selectedNode ? selected.peer_address : null;
    let subtitle = address || entry.kind;
    if (candidateNode) subtitle = selected.outcome === "blocked" ? "Not reached" : "Unconfirmed";
    addText(svg, node.x + 12, node.y + 40, subtitle,
      candidateNode ? "candidate-subtitle" : "node-subtitle");
    if (entry.id !== "other-address") {
      svg.append(svgElement("circle", { cx: port.x, cy: port.y, r: 3, class: "network-port" }));
    }
    if (mismatch) addText(svg, node.x + node.w - 18, node.y + 22, "!", "mismatch-label");
  }
}

function drawObservation(svg, observation, layout, className, focused = false) {
  const destination = layout.zones[observation.destination];
  if (observation.outcome === "blocked" || observation.outcome === "unresolved") {
    if (!focused) return;
    const { preview } = layout;
    const y = preview.y + 57;
    addLine(svg, [[preview.x + preview.w - 48, y], [preview.x + preview.w - 12, y]], "observation-blocked");
    svg.append(svgElement("circle", { cx: preview.x + preview.w - 12, cy: y, r: 6, class: "stop-mark" }));
    return;
  }
  if (!destination) return;
  if (observation.outcome === "attempted") {
    if (!focused) return;
    const points = destination.points.slice(0, layout.mobile ? 4 : 2);
    addLine(svg, points, "observation-attempted");
    const [x, y] = points.at(-1);
    svg.append(svgElement("circle", { cx: x, cy: y, r: 5, class: "attempt-mark" }));
    return;
  }
  if (observation.peer_address === null) return;
  addLine(svg, destination.points, className);
  if (focused) {
    const [x, y] = destination.points.at(-1);
    svg.append(svgElement("circle", { cx: x, cy: y, r: 5, class: "response-mark" }));
  }
}

export function renderTopology(root, observations, selectedIndex, hasTrial, dnsAnswers = []) {
  const width = Math.max(280, root.clientWidth);
  const includeUnmapped = observations.some((item) =>
    item.destination === "other-address" && item.outcome !== "blocked");
  const layout = geometry(width, includeUnmapped);
  const selected = observations[selectedIndex] || null;
  const svg = svgElement("svg", {
    viewBox: `0 0 ${layout.width} ${layout.height}`,
    width: layout.width,
    height: layout.height,
    "aria-hidden": "true",
  });

  drawStructure(svg, layout, dnsAnswers.length, selected);
  if (hasTrial) {
    addLine(svg, layout.browserPoints, "browser-request");
  }
  for (const [index, observation] of observations.entries()) {
    if (index !== selectedIndex && ["responded", "response_failed"].includes(observation.outcome)) {
      drawObservation(svg, observation, layout,
        observation.outcome === "response_failed" ? "observation-history-incomplete" : "observation-history");
    }
  }
  if (selected) {
    const className = selected.outcome === "response_failed"
      ? "observation-incomplete" : "observation-response";
    drawObservation(svg, selected, layout, className, true);
  }

  root.replaceChildren(svg);
  root.setAttribute("aria-label", selected
    ? `${selected.resource} request ${selected.sequence + 1}: ${selected.outcome}; ${selected.destination || "no known destination"}`
    : hasTrial ? "No HTTP request path was recorded" : "Compose network topology with no trial yet");
}
