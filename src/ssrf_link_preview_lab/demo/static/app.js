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
let selectedStep = -1;

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

function pathDescription(step) {
  const outcome = {
    responded: `HTTP ${step.status_code} from ${step.target}`,
    response_failed: `HTTP ${step.status_code} from ${step.target}; transfer failed`,
    blocked: `Blocked before connection to ${step.target}`,
    attempted: `Connection attempted toward ${step.target}; delivery unconfirmed`,
    unresolved: "Address preparation failed before connection",
  }[step.outcome];
  const facts = [outcome, step.detail];
  if (step.checked_address) facts.push(`Checked ${step.checked_address}`);
  if (step.selected_address) facts.push(`Selected ${step.selected_address}`);
  if (step.address) facts.push(`${["responded", "response_failed"].includes(step.outcome) ? "Peer" : "Address"} ${step.address}`);
  if (step.redirect_url) facts.push(`Redirect to ${step.redirect_url}`);
  return facts.join(" · ");
}

function drawTopology() {
  const steps = latestTrial?.path || [];
  renderTopology(topology, steps, selectedStep, latestTrial !== null);
  document.querySelector("#path-count").textContent = `${steps.length} step${steps.length === 1 ? "" : "s"}`;
  document.querySelector("#path-detail").textContent = selectedStep >= 0
    ? pathDescription(steps[selectedStep])
    : latestTrial ? "No HTTP path was observed." : "Select a request below to inspect its route.";
}

function renderEvidence(trial) {
  evidence.replaceChildren();
  const list = appendText(evidence, "div", "", "event-list");
  const entries = [
    ...(trial.path || []).map((step, index) => ({ kind: "path", step, index, time: step.observed_at })),
    ...(trial.dns_answers || []).map((answer) => ({ kind: "dns", answer, time: answer.observed_at })),
  ].sort((left, right) => (left.time ?? 0) - (right.time ?? 0));

  for (const [number, entry] of entries.entries()) {
    const selectable = entry.kind === "path";
    const row = document.createElement(selectable ? "button" : "div");
    if (selectable) row.type = "button";
    row.className = `event ${selectable && entry.index === selectedStep ? "active" : ""}`;
    appendText(row, "span", String(number + 1), "event-number");
    const content = appendText(row, "span", "", "event-content");
    if (selectable) {
      const { step, index } = entry;
      const title = step.outcome === "responded"
        ? `${step.resource} · HTTP ${step.status_code}`
        : step.outcome === "response_failed"
          ? `${step.resource} · HTTP ${step.status_code}, incomplete`
        : `${step.resource} · ${step.outcome}`;
      appendText(content, "span", title, "event-title");
      appendText(content, "span", `${step.url}\n${pathDescription(step)}`, "event-details");
      row.addEventListener("click", () => {
        selectedStep = index;
        drawTopology();
        for (const button of list.querySelectorAll("button.event")) button.classList.remove("active");
        row.classList.add("active");
      });
    } else {
      appendText(content, "span", `DNS answer #${entry.answer.query}`, "event-title");
      appendText(content, "span", `${entry.answer.hostname} → ${entry.answer.address}`, "event-details");
    }
    list.append(row);
  }
  if (!entries.length) appendText(list, "p", trial.message || "No network events observed");
  document.querySelector("#evidence-count").textContent = `${entries.length} events`;

  const answers = document.querySelector("#dns-answers");
  answers.hidden = !trial.dns_answers?.length;
  answers.textContent = trial.dns_answers?.length
    ? `DNS: ${trial.dns_answers.map((answer) => `#${answer.query} ${answer.address}`).join(" → ")}`
    : "";
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
    const steps = trial.path || [];
    selectedStep = steps.reduce((index, step, current) => step.resource === "page" ? current : index, -1);
    if (selectedStep < 0) selectedStep = steps.length - 1;
    renderPreview(trial);
    drawTopology();
    renderEvidence(trial);
    document.querySelector("#download").disabled = false;
  } catch (error) {
    latestTrial = null;
    selectedStep = -1;
    document.querySelector("#download").disabled = true;
    document.querySelector("#trial-id").textContent = "";
    result.replaceChildren();
    result.className = "preview-error";
    const status = document.querySelector("#preview-status");
    status.textContent = "Service error";
    status.className = "minor-label status-failed";
    appendText(result, "h3", "Demo service error");
    appendText(result, "p", String(error));
    drawTopology();
    evidence.textContent = "No request evidence";
    document.querySelector("#evidence-count").textContent = "0 events";
    document.querySelector("#dns-answers").hidden = true;
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
new ResizeObserver(drawTopology).observe(topology);
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
