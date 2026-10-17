const state = { defense: "none", dns_mode: "stable", urls: {} };
const defenseNames = {
  none: "No address check",
  initial: "Initial URL only",
  each_hop: "Every redirect hop",
  bound: "Check and bind",
};

const input = document.querySelector("#url");
const result = document.querySelector("#result");
const evidence = document.querySelector("#evidence");
const form = document.querySelector("#preview-form");
const submitButton = form.querySelector("button[type='submit']");
const stateControls = document.querySelectorAll(
  'input[name="defense"], input[name="dns_mode"]',
);
const exampleControls = document.querySelectorAll(
  'input[name="redirect"], [data-preset]',
);
let latestTrial = null;

function setDisabled(controls, disabled) {
  for (const control of controls) control.disabled = disabled;
}

setDisabled(stateControls, true);
setDisabled(exampleControls, true);
submitButton.disabled = true;

async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail) || response.statusText,
    );
  }
  return data;
}

function syncControls() {
  for (const name of ["defense", "dns_mode"]) {
    const selected = document.querySelector(
      `input[name="${name}"][value="${state[name]}"]`,
    );
    if (selected) selected.checked = true;
  }
  document.querySelector("#active-policy").textContent = defenseNames[state.defense];
}

function updateState(next) {
  Object.assign(state, next);
  syncControls();
}

function selectedValue(name) {
  return document.querySelector(`input[name="${name}"]:checked`).value;
}

async function saveState(changedName) {
  const next = {
    defense: selectedValue("defense"),
    dns_mode: selectedValue("dns_mode"),
  };
  setDisabled(stateControls, true);
  try {
    const updated = await request("/demo/state", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
    updateState(updated);
  } catch (error) {
    syncControls();
    throw error;
  } finally {
    setDisabled(stateControls, false);
  }

  if (changedName === "dns_mode" && next.dns_mode === "rebind") {
    input.value = state.urls.rebind;
  }
}

function selectRedirect(mode) {
  input.value = state.urls[mode === "off" ? "page" : `redirect_${mode}`];
  input.focus();
}

function appendText(parent, tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function renderResult(trial) {
  result.replaceChildren();
  result.className = trial.ok ? "outcome" : "outcome blocked";
  document.querySelector("#trial-id").textContent = `Trial ${trial.trial_id.slice(0, 8)}`;
  appendText(
    result,
    "span",
    `${trial.ok ? "Preview generated" : "Request stopped"} · ${defenseNames[trial.defense]}`,
    "outcome-label",
  );
  appendText(result, "h3", trial.ok ? trial.title || "Untitled page" : "No preview generated");
  const description = appendText(
    result,
    "p",
    trial.ok ? trial.description || "No description provided" : trial.message,
  );
  if (trial.ok && trial.description?.includes("SSRF_LAB_INTERNAL_REPORT")) {
    description.className = "secret";
  }
  if (trial.ok) appendText(result, "p", `Final URL: ${trial.final_url}`, "final-url");
}

function trialEvents(trial) {
  const events = [];
  const trace = trial.trace || {};
  for (const decision of trace.address_decisions || []) {
    events.push({
      observedAt: decision.observed_at,
      title: decision.allowed ? "Address check · allowed" : "Address check · blocked",
      details: `${decision.url}\nResolved: ${decision.resolved_addresses.join(", ") || "none"} · ${decision.reason}`,
    });
  }
  for (const hop of trace.hops || []) {
    events.push({
      observedAt: hop.observed_at,
      title: `HTTP ${hop.status_code} · hop ${hop.sequence + 1}`,
      details: `${hop.url}\nConnected to: ${hop.peer_ip || "unknown"}${hop.redirect_url ? ` · Redirected to ${hop.redirect_url}` : ""}`,
    });
  }
  for (const answer of trial.dns_answers || []) {
    events.push({
      observedAt: answer.observed_at,
      title: `DNS query #${answer.query}`,
      details: `${answer.hostname} → ${answer.address} · TTL 0`,
    });
  }
  return events.sort((left, right) => left.observedAt - right.observedAt);
}

function renderEvidence(trial) {
  const events = trialEvents(trial);
  evidence.replaceChildren();
  const list = appendText(evidence, "div", "", "event-list");
  for (const [index, event] of events.entries()) {
    const row = appendText(list, "div", "", "event");
    appendText(row, "span", String(index + 1), "event-number");
    const content = appendText(row, "div", "");
    appendText(content, "div", event.title, "event-title");
    appendText(content, "div", event.details, "event-details");
  }
  if (!events.length) {
    appendText(list, "div", trial.message || "No network events", "evidence-empty");
  }
  document.querySelector("#evidence-count").textContent = `${events.length} events`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = "Requesting…";
  try {
    const trial = await request("/demo/trial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value }),
    });
    latestTrial = trial;
    renderResult(trial);
    renderEvidence(trial);
    document.querySelector("#download").disabled = false;
  } catch (error) {
    latestTrial = null;
    document.querySelector("#download").disabled = true;
    document.querySelector("#trial-id").textContent = "";
    result.replaceChildren();
    result.className = "outcome blocked";
    appendText(result, "h3", "Demo service error");
    appendText(result, "p", String(error));
    evidence.replaceChildren();
    appendText(evidence, "div", "No request evidence", "evidence-empty");
    document.querySelector("#evidence-count").textContent = "0 events";
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Generate preview →";
  }
});

for (const control of document.querySelectorAll('input[type="radio"]')) {
  control.addEventListener("change", () => {
    if (control.name === "redirect") {
      selectRedirect(control.value);
      return;
    }
    saveState(control.name).catch((error) => window.alert(String(error)));
  });
}
for (const button of document.querySelectorAll("[data-preset]")) {
  button.addEventListener("click", () => {
    input.value = state.urls[button.dataset.preset];
    input.focus();
  });
}

document.querySelector("#download").addEventListener("click", () => {
  if (!latestTrial) return;
  const blob = new Blob([JSON.stringify(latestTrial, null, 2)], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `ssrf-trial-${latestTrial.trial_id}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

request("/demo/state")
  .then((initialState) => {
    updateState(initialState);
    setDisabled(stateControls, false);
    setDisabled(exampleControls, false);
    submitButton.disabled = false;
  })
  .catch((error) => {
    result.replaceChildren();
    appendText(result, "p", `Could not load lab state: ${error}`);
  });
