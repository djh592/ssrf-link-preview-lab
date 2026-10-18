const SVG_NS = "http://www.w3.org/2000/svg";

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  return element;
}

function nodePositions(width, includeOther) {
  const targets = includeOther
    ? ["external-page", "internal-report", "public-web", "other-address"]
    : ["external-page", "internal-report", "public-web"];
  if (width < 460) {
    const nodeWidth = Math.min(138, (width - 32) / 2);
    const left = (width - nodeWidth * 2 - 12) / 2;
    const nodes = {
      browser: { x: (width - 106) / 2, y: 8, w: 106, h: 38 },
      preview: { x: (width - 116) / 2, y: 72, w: 116, h: 42 },
    };
    for (const [index, target] of targets.entries()) {
      nodes[target] = {
        x: left + (index % 2) * (nodeWidth + 12),
        y: 162 + Math.floor(index / 2) * 68,
        w: nodeWidth,
        h: 42,
      };
    }
    return { nodes, height: 285, vertical: true };
  }

  const nodes = {
    browser: { x: 14, y: 117, w: 90, h: 42 },
    preview: { x: Math.max(134, width * 0.36 - 55), y: 115, w: 112, h: 46 },
  };
  const targetY = includeOther ? [13, 78, 143, 208] : [28, 105, 182];
  for (const [index, target] of targets.entries()) {
    nodes[target] = { x: width - 151, y: targetY[index], w: 137, h: 43 };
  }
  return { nodes, height: 267, vertical: false };
}

function edgePoints(source, target, vertical, stopped = false) {
  if (vertical) {
    const x1 = source.x + source.w / 2;
    const y1 = source.y + source.h;
    const x2 = target.x + target.w / 2;
    const y2 = target.y - (stopped ? 13 : 0);
    return { x1, y1, x2, y2 };
  }
  return {
    x1: source.x + source.w,
    y1: source.y + source.h / 2,
    x2: target.x - (stopped ? 13 : 0),
    y2: target.y + target.h / 2,
  };
}

function addEdge(svg, source, target, vertical, classes, stopped = false) {
  const points = edgePoints(source, target, vertical, stopped);
  svg.append(svgElement("line", { ...points, class: `network-edge ${classes}` }));
  if (stopped) {
    svg.append(svgElement("circle", {
      cx: points.x2,
      cy: points.y2,
      r: 5,
      class: "network-stop",
    }));
  }
}

function addHopLabel(svg, source, target, vertical, label) {
  const { x1, y1, x2, y2 } = edgePoints(source, target, vertical);
  const text = svgElement("text", {
    x: x1 + (x2 - x1) * 0.62,
    y: y1 + (y2 - y1) * 0.62 - 7,
    class: "network-hop-label",
  });
  text.textContent = label;
  svg.append(text);
}

function hopLabel(step) {
  return `${step.resource === "image" ? "image " : ""}${step.sequence + 1}`;
}

function addNode(svg, position, label, subtitle, classes) {
  svg.append(svgElement("rect", {
    x: position.x,
    y: position.y,
    width: position.w,
    height: position.h,
    rx: 5,
    class: `network-node ${classes}`,
  }));
  const center = position.x + position.w / 2;
  if (subtitle) {
    const title = svgElement("text", {
      x: center,
      y: position.y + 15,
      class: "network-label",
    });
    title.textContent = label;
    const detail = svgElement("text", {
      x: center,
      y: position.y + 31,
      class: "network-subtitle",
    });
    detail.textContent = subtitle;
    svg.append(title, detail);
  } else {
    const title = svgElement("text", {
      x: center,
      y: position.y + position.h / 2,
      class: "network-label",
    });
    title.textContent = label;
    svg.append(title);
  }
}

export function renderTopology(root, steps, selectedIndex, hasTrial) {
  const width = Math.max(280, root.clientWidth - 2);
  const includeOther = steps.some((step) => step.target === "other-address");
  const { nodes, height, vertical } = nodePositions(width, includeOther);
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, height });
  const selected = steps[selectedIndex] || null;
  const reached = new Set(
    steps.filter((step) => ["responded", "response_failed"].includes(step.outcome)).map((step) => step.target),
  );

  if (hasTrial) addEdge(svg, nodes.browser, nodes.preview, vertical, "reached");
  for (const target of ["external-page", "internal-report", "public-web", "other-address"]) {
    if (nodes[target] && reached.has(target)) {
      addEdge(svg, nodes.preview, nodes[target], vertical, "reached");
      const labels = steps
        .filter((step) => step.target === target && ["responded", "response_failed"].includes(step.outcome))
        .map(hopLabel);
      addHopLabel(svg, nodes.preview, nodes[target], vertical, labels.join(", "));
    }
  }
  if (selected && selected.outcome !== "unresolved") {
    const edgeClass = ["responded", "response_failed"].includes(selected.outcome)
      ? "reached"
      : selected.outcome === "blocked" ? "blocked" : "attempted";
    addEdge(
      svg,
      nodes.preview,
      nodes[selected.target],
      vertical,
      `${edgeClass} ${selected.resource === "image" ? "image" : ""}`,
      selected.outcome === "blocked",
    );
    if (!["responded", "response_failed"].includes(selected.outcome)) {
      addHopLabel(svg, nodes.preview, nodes[selected.target], vertical, hopLabel(selected));
    }
  }

  addNode(svg, nodes.browser, "Browser", "", hasTrial ? "reached" : "");
  addNode(svg, nodes.preview, "Preview", "service", hasTrial ? "reached" : "");
  const labels = {
    "external-page": ["External page", "lab network"],
    "internal-report": ["Internal report", "lab network"],
    "public-web": ["Public web", "egress"],
    "other-address": ["Other address", "unrecognized"],
  };
  for (const [target, [label, subtitle]] of Object.entries(labels)) {
    if (!nodes[target]) continue;
    addNode(
      svg,
      nodes[target],
      label,
      selected?.target === target && selected.address ? selected.address : subtitle,
      `${reached.has(target) ? "reached" : ""} ${selected?.target === target ? "selected" : ""}`,
    );
  }

  root.replaceChildren(svg);
  const summary = selected
    ? `${selected.resource} request ${selected.sequence + 1}: ${selected.outcome} toward ${selected.target}`
    : "Testbed topology with no selected request";
  root.setAttribute("aria-label", summary);
}
