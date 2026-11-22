function appendText(parent, tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function outcomeLabel(observation) {
  switch (observation.outcome) {
    case "responded": return `HTTP ${observation.status_code} response`;
    case "response_failed": return `HTTP ${observation.status_code} · incomplete body`;
    case "blocked": return "Blocked before connection";
    case "attempted": return "Connection outcome unconfirmed";
    case "unresolved": return "DNS lookup failed";
    default: return "Address preparation failed";
  }
}

export function trialEvents(trial) {
  if (!Array.isArray(trial?.observations) || !Array.isArray(trial?.dns_answers)) {
    throw new Error("Demo service returned an incomplete trial");
  }
  return [
    ...trial.observations.map((observation) => ({
      kind: "request", observation, time: observation.observed_at,
    })),
    ...trial.dns_answers.map((answer) => ({ kind: "dns", answer, time: answer.observed_at })),
  ].sort((left, right) => (left.time ?? 0) - (right.time ?? 0));
}

export function renderPreview(trial) {
  const result = document.querySelector("#result");
  const status = document.querySelector("#preview-status");
  result.replaceChildren();
  const elapsed = typeof trial.duration_seconds === "number"
    ? ` · ${Math.round(trial.duration_seconds * 1000)} ms` : "";
  const restricted = trial.ok && trial.preview_kind === "restricted";
  const unverified = trial.ok && trial.preview_kind === "unverified";
  const statusLabel = restricted
    ? "Restricted data exposed"
    : unverified
      ? "Generated · identity unverified"
      : trial.ok ? "Generated" : "Unavailable";
  status.textContent = `${statusLabel}${elapsed}`;
  status.className = `minor-label ${restricted || unverified
    ? "status-exposed" : trial.ok ? "status-ok" : "status-failed"}`;

  if (!trial.ok) {
    result.className = "preview-error";
    appendText(result, "h3", "No preview generated");
    appendText(result, "p", trial.message);
    return;
  }

  result.className = `link-preview${restricted ? " link-preview--restricted" : ""}`;
  const media = appendText(result, "div", "", "preview-media");
  if (trial.image_data_url) {
    const image = document.createElement("img");
    image.src = trial.image_data_url;
    image.alt = "";
    media.append(image);
  } else {
    renderImageFallback(media, trial, { restricted });
  }
  const copy = appendText(result, "div", "", "preview-copy");
  if (restricted) {
    appendText(copy, "span", "INTERNAL / RESTRICTED", "preview-classification");
  }
  appendText(copy, "span", trial.site_name || new URL(trial.final_url).hostname, "preview-site");
  appendText(copy, "h3", trial.title || "Untitled page");
  appendText(copy, "p", trial.description || "No description provided");
  appendText(copy, "p", trial.final_url, "final-url");
}

function renderImageFallback(parent, trial, { restricted }) {
  parent.classList.add("preview-media-unavailable");
  const imageObservation = trial.observations
    .filter((observation) => observation.resource === "image")
    .at(-1);
  const [title, detail] = imageFallbackCopy(imageObservation);
  if (restricted) {
    parent.classList.add("preview-media-restricted");
    const placeholder = appendText(
      parent, "div", "", "preview-image-placeholder preview-restricted-placeholder",
    );
    appendText(placeholder, "span", "", "preview-restricted-glyph");
    appendText(placeholder, "strong", "Report body exposed", "preview-image-title");
    appendText(placeholder, "span", detail, "preview-image-detail");
    return;
  }
  const placeholder = appendText(parent, "div", "", "preview-image-placeholder");
  appendText(placeholder, "span", "", "preview-image-glyph");
  appendText(placeholder, "strong", title, "preview-image-title");
  appendText(placeholder, "span", detail, "preview-image-detail");
}

function imageFallbackCopy(observation) {
  if (!observation) {
    return ["No cover image", "The page did not provide a fetchable image URL."];
  }
  switch (observation.outcome) {
    case "blocked":
      return [
        "Cover image blocked",
        "The page loaded, but its separate image request was stopped by the address defense.",
      ];
    case "attempted":
      return [
        "Cover image unconfirmed",
        "The page loaded, but the image connection has no recorded response.",
      ];
    case "unresolved":
      return [
        "Cover image unavailable",
        "The page loaded, but the image hostname could not be resolved.",
      ];
    case "response_failed":
      return [
        "Cover image incomplete",
        "The page loaded, but the image response was incomplete.",
      ];
    default:
      return [
        "Cover image unavailable",
        "The image response was not a supported preview image.",
      ];
  }
}

export function renderServiceError(error) {
  const result = document.querySelector("#result");
  result.replaceChildren();
  result.className = "preview-error";
  appendText(result, "h3", "Demo service error");
  appendText(result, "p", String(error));
  const status = document.querySelector("#preview-status");
  status.textContent = "Service error";
  status.className = "minor-label status-failed";
}

export function renderEvidence(events, onSelect) {
  const root = document.querySelector("#evidence");
  root.replaceChildren();
  document.querySelector("#evidence-count").textContent =
    `${events.length} ${events.length === 1 ? "event" : "events"}`;
  if (!events.length) {
    root.textContent = "No request evidence recorded";
    return;
  }
  for (const [index, entry] of events.entries()) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "event";
    row.setAttribute("aria-pressed", "false");
    appendText(row, "span", String(index + 1), "event-number");
    const content = appendText(row, "span", "", "event-content");
    if (entry.kind === "request") {
      const { observation } = entry;
      appendText(content, "span", `${observation.resource === "image" ? "Image" : "Page"} ${observation.sequence + 1} · ${outcomeLabel(observation)}`, "event-title");
      appendText(content, "span", observation.url, "event-details");
      if (observation.redirect_url) {
        appendText(content, "span", `Location: ${observation.redirect_url}`, "event-details");
      }
    } else {
      appendText(content, "span", `DNS answer ${entry.answer.query}`, "event-title");
      appendText(content, "span", `${entry.answer.hostname} → ${entry.answer.address}`, "event-details");
    }
    row.addEventListener("click", () => onSelect(index));
    root.append(row);
  }
}

function addFact(parent, label, value, warning = false) {
  if (value == null) return;
  const fact = appendText(parent, "div", "", `path-fact ${warning ? "warning" : ""}`);
  appendText(fact, "span", label, "fact-label");
  appendText(fact, "span", String(value), "fact-value");
}

export function selectEvidence(events, index, trial) {
  for (const [rowIndex, button] of [...document.querySelectorAll("#evidence .event")].entries()) {
    const active = rowIndex === index;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  const title = document.querySelector("#path-title");
  const facts = document.querySelector("#path-facts");
  facts.replaceChildren();
  const entry = events[index];
  if (!entry) {
    title.textContent = "No event selected";
    facts.textContent = trial?.message || "Select an event to inspect its evidence.";
    return;
  }
  if (entry.kind === "dns") {
    title.textContent = `DNS answer ${entry.answer.query} · ${entry.answer.hostname}`;
    addFact(facts, "Returned IP", entry.answer.address);
    addFact(facts, "Source", "Preview's local UDP authority");
    return;
  }
  const selected = entry.observation;
  title.textContent = `${selected.resource === "image" ? "Image" : "Page"} request ${selected.sequence + 1} · ${outcomeLabel(selected)}`;
  addFact(facts, "URL", selected.url);
  addFact(facts, "Checked IP", selected.checked_address);
  addFact(facts, "Rejected IP", selected.rejected_address);
  addFact(facts, "Selected IP", selected.selected_address);
  addFact(facts, selected.outcome === "attempted" ? "Reported peer" : "HTTP peer", selected.peer_address);
  addFact(facts, "Responder", selected.responder_service, selected.identity_matches === false);
  addFact(facts, "Redirect location", selected.redirect_url);
  addFact(facts, "Evidence", selected.detail, selected.identity_matches === false);
}
