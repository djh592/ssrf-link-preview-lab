import { renderTopology } from "./topology.js";

const state = { defense: "none", dns_mode: "stable", urls: {} };
const defenseNames = {
  none: "No lab check",
  initial: "Initial URL",
  each_hop: "Each hop",
  bound: "Check & bind",
};

const input = document.querySelector("#url");
const form = document.querySelector("#preview-form");
const submitButton = form.querySelector("button[type='submit']");
const stateControls = document.querySelectorAll('input[name="defense"], input[name="dns_mode"]');
const exampleButtons = document.querySelectorAll("[data-preset]");
const result = document.querySelector("#result");
const topology = document.querySelector("#topology");
const evidence = document.querySelector("#evidence");
let latestTrial = null;
let selectedIndex = -1;

function setDisabled(controls, disabled) {
  for (const control of controls) control.disabled = disabled;
}

function appendText(parent, tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail) || response.statusText);
  }
  return data;
}

function syncControls() {
  for (const name of ["defense", "dns_mode"]) {
    const selected = document.querySelector(`input[name="${name}"][value="${state[name]}"]`);
    if (selected) selected.checked = true;
  }
}

function selectedValue(name) {
  return document.querySelector(`input[name="${name}"]:checked`).value;
}

async function saveState() {
  setDisabled(stateControls, true);
  submitButton.disabled = true;
  try {
    const updated = await request("/demo/state", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ defense: selectedValue("defense"), dns_mode: selectedValue("dns_mode") }),
    });
    Object.assign(state, updated);
    syncControls();
  } catch (error) {
    syncControls();
    window.alert(String(error));
  } finally {
    setDisabled(stateControls, false);
    submitButton.disabled = false;
  }
}

function renderPreview(trial) {
  result.replaceChildren();
  document.querySelector("#trial-id").textContent = `Trial ${trial.trial_id.slice(0, 8)}`;
  const status = document.querySelector("#preview-status");
  status.textContent = `${trial.ok ? "Generated" : "Unavailable"} · ${defenseNames[trial.defense]}`;
  status.className = `minor-label ${trial.ok ? "status-ok" : "status-failed"}`;

  if (!trial.ok) {
    result.className = "preview-error";
    appendText(result, "h3", "No preview generated");
    appendText(result, "p", trial.message);
    return;
  }

  result.className = `link-preview ${trial.image_data_url ? "" : "text-only"}`;
  if (trial.image_data_url) {
    const media = appendText(result, "div", "", "preview-media");
    const image = document.createElement("img");
    image.src = trial.image_data_url;
    image.alt = "";
    media.append(image);
  }
  const copy = appendText(result, "div", "", "preview-copy");
  appendText(copy, "span", trial.site_name || new URL(trial.final_url).hostname, "preview-site");
  appendText(copy, "h3", trial.title || "Untitled page");
  appendText(copy, "p", trial.description || "No description provided");
  appendText(copy, "p", trial.final_url, "final-url");
}

function outcomeLabel(observation) {
  switch (observation.outcome) {
    case "responded": return `HTTP ${observation.status_code} response`;
    case "response_failed": return `HTTP ${observation.status_code} · incomplete body`;
    case "blocked": return "Blocked before connection";
    case "attempted": return "Connection outcome unconfirmed";
    default: return "Address preparation failed";
  }
}

function addFact(parent, label, value, warning = false) {
  if (value == null) return;
  const fact = appendText(parent, "div", "", `path-fact ${warning ? "warning" : ""}`);
  appendText(fact, "span", label, "fact-label");
  appendText(fact, "span", String(value), "fact-value");
}

function renderSelectedRequest() {
  const observations = latestTrial?.observations || [];
  const selected = observations[selectedIndex];
  renderTopology(topology, observations, selectedIndex, latestTrial !== null, latestTrial?.dns_answers || []);
  document.querySelector("#request-count").textContent =
    `${observations.length} request${observations.length === 1 ? "" : "s"}`;

  const title = document.querySelector("#path-title");
  const facts = document.querySelector("#path-facts");
  facts.replaceChildren();
  if (!selected) {
    title.textContent = latestTrial ? "No HTTP request recorded" : "No request selected";
    facts.textContent = latestTrial?.message || "Select a request below to inspect its evidence.";
    return;
  }

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

function renderEvidence(trial) {
  evidence.replaceChildren();
  const list = appendText(evidence, "div", "", "event-list");
  const entries = [
    ...trial.observations.map((observation, index) => ({
      kind: "request", observation, index, time: observation.observed_at,
    })),
    ...trial.dns_answers.map((answer) => ({ kind: "dns", answer, time: answer.observed_at })),
  ].sort((left, right) => (left.time ?? 0) - (right.time ?? 0));

  for (const [number, entry] of entries.entries()) {
    const selectable = entry.kind === "request";
    const row = document.createElement(selectable ? "button" : "div");
    if (selectable) row.type = "button";
    row.className = `event ${selectable && entry.index === selectedIndex ? "active" : ""}`;
    appendText(row, "span", String(number + 1), "event-number");
    const content = appendText(row, "span", "", "event-content");
    if (selectable) {
      const { observation, index } = entry;
      appendText(content, "span", `${observation.resource === "image" ? "Image" : "Page"} ${observation.sequence + 1} · ${outcomeLabel(observation)}`, "event-title");
      appendText(content, "span", observation.url, "event-details");
      if (observation.redirect_url) {
        appendText(content, "span", `Location: ${observation.redirect_url}`, "event-details");
      }
      row.addEventListener("click", () => {
        selectedIndex = index;
        renderSelectedRequest();
        for (const button of list.querySelectorAll("button.event")) button.classList.remove("active");
        row.classList.add("active");
      });
    } else {
      appendText(content, "span", `rebind.lab DNS answer ${entry.answer.query}`, "event-title");
      appendText(content, "span", `${entry.answer.hostname} → ${entry.answer.address}`, "event-details");
    }
    list.append(row);
  }
  if (!entries.length) appendText(list, "p", trial.message || "No network events observed");
  document.querySelector("#evidence-count").textContent = `${entries.length} events`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  setDisabled(stateControls, true);
  submitButton.textContent = "Requesting…";
  try {
    const trial = await request("/demo/trial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value }),
    });
    latestTrial = trial;
    selectedIndex = trial.observations.reduce((index, item, current) =>
      item.resource === "page" ? current : index, -1);
    if (selectedIndex < 0) selectedIndex = trial.observations.length - 1;
    renderPreview(trial);
    renderSelectedRequest();
    renderEvidence(trial);
    document.querySelector("#download").disabled = false;
  } catch (error) {
    latestTrial = null;
    selectedIndex = -1;
    document.querySelector("#download").disabled = true;
    document.querySelector("#trial-id").textContent = "";
    result.replaceChildren();
    result.className = "preview-error";
    const status = document.querySelector("#preview-status");
    status.textContent = "Service error";
    status.className = "minor-label status-failed";
    appendText(result, "h3", "Demo service error");
    appendText(result, "p", String(error));
    renderSelectedRequest();
    evidence.textContent = "No request evidence";
    document.querySelector("#evidence-count").textContent = "0 events";
  } finally {
    submitButton.disabled = false;
    setDisabled(stateControls, false);
    submitButton.textContent = "Generate preview →";
  }
});

for (const control of stateControls) control.addEventListener("change", saveState);
for (const button of exampleButtons) {
  button.addEventListener("click", () => {
    input.value = state.urls[button.dataset.preset];
    document.querySelector("#examples").open = false;
    input.focus();
  });
}

document.querySelector("#download").addEventListener("click", () => {
  if (!latestTrial) return;
  const blob = new Blob([JSON.stringify(latestTrial, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `ssrf-trial-${latestTrial.trial_id}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

setDisabled(stateControls, true);
setDisabled(exampleButtons, true);
submitButton.disabled = true;
let previousWidth = 0;
new ResizeObserver(() => {
  if (topology.clientWidth !== previousWidth) {
    previousWidth = topology.clientWidth;
    renderSelectedRequest();
  }
}).observe(topology);
renderSelectedRequest();
request("/demo/state")
  .then((initialState) => {
    Object.assign(state, initialState);
    syncControls();
    setDisabled(stateControls, false);
    setDisabled(exampleButtons, false);
    submitButton.disabled = false;
  })
  .catch((error) => {
    result.textContent = `Could not load lab state: ${error}`;
  });
