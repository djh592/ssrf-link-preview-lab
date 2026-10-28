import { createInspector } from "./inspector.js";
import { renderTopology } from "./topology.js";
import {
  renderEvidence, renderPreview, renderServiceError, selectEvidence, trialEvents,
} from "./results.js";

const topology = document.querySelector("#topology");
const setupStatus = document.querySelector("#setup-status");
const trialError = document.querySelector("#trial-error");
const download = document.querySelector("#download");
const state = {
  node: "browser",
  trial: null,
  events: [],
  eventIndex: -1,
  busy: false,
  ready: false,
  requestFailed: false,
};

async function request(path, options) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Demo service returned HTTP ${response.status} without JSON`);
  }
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail) || response.statusText);
  }
  return data;
}

function selectedEvent() {
  return state.events[state.eventIndex] || null;
}

function renderMap() {
  const configuration = state.trial
    ? { ...state.trial.configuration, url: state.trial.requested_url }
    : inspector.getDraft();
  renderTopology(topology, {
    trial: state.trial,
    selectedEvent: selectedEvent(),
    selectedNode: state.node,
    configuration,
    targets: inspector.getTargets(),
    onSelectNode: selectNode,
  });
}

function updateSetupStatus() {
  if (!state.ready) return;
  if (state.busy) {
    setupStatus.textContent = "Running trial";
    setupStatus.className = "minor-label";
    return;
  }
  if (state.requestFailed) {
    setupStatus.textContent = state.trial
      ? "Trial request failed · previous trial retained" : "Trial request failed";
    setupStatus.className = "minor-label status-failed";
    return;
  }
  if (!state.trial) {
    setupStatus.textContent = "Ready for a trial";
    setupStatus.className = "minor-label";
    return;
  }
  const draft = inspector.getDraft();
  const recorded = state.trial.configuration;
  const changed = draft.url !== state.trial.requested_url ||
    draft.defense !== recorded.defense || draft.dns_mode !== recorded.dns_mode;
  setupStatus.textContent = changed
    ? "Settings changed · topology shows previous trial" : "Showing recorded trial";
  setupStatus.className = `minor-label ${changed ? "status-pending" : ""}`;
}

function selectNode(node) {
  state.node = node;
  const panel = inspector.show(node);
  renderMap();
  if (panel && window.matchMedia("(max-width: 1360px)").matches) {
    panel.scrollIntoView({ block: "start" });
    panel.focus({ preventScroll: true });
  }
}

function selectEvent(index) {
  state.eventIndex = index;
  selectEvidence(state.events, index, state.trial);
  renderMap();
}

async function runTrial(configuration) {
  if (state.busy || !state.ready) return;
  state.busy = true;
  state.requestFailed = false;
  trialError.hidden = true;
  inspector.setBusy(true);
  updateSetupStatus();
  try {
    const trial = await request("/demo/trial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(configuration),
    });
    const events = trialEvents(trial);
    let eventIndex = events.findLastIndex((entry) =>
      entry.kind === "request" && entry.observation.resource === "page");
    if (eventIndex < 0) eventIndex = events.length - 1;
    state.trial = trial;
    state.events = events;
    state.eventIndex = eventIndex;
    document.querySelector("#trial-id").textContent = `Trial ${trial.trial_id.slice(0, 8)}`;
    renderPreview(trial);
    renderEvidence(state.events, selectEvent);
    selectEvent(state.eventIndex);
    download.disabled = false;
  } catch (error) {
    state.requestFailed = true;
    trialError.textContent = `Trial request failed: ${error instanceof Error ? error.message : String(error)}`;
    trialError.hidden = false;
  } finally {
    state.busy = false;
    inspector.setBusy(false);
    updateSetupStatus();
  }
}

const inspector = createInspector({
  onChange() {
    renderMap();
    updateSetupStatus();
  },
  onRun: runTrial,
  onSelectNode: selectNode,
});
inspector.setBusy(true);
inspector.show(state.node);
renderMap();

download.addEventListener("click", () => {
  if (!state.trial) return;
  const blob = new Blob([JSON.stringify(state.trial, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `ssrf-trial-${state.trial.trial_id}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

let previousWidth = 0;
new ResizeObserver(() => {
  if (topology.clientWidth !== previousWidth) {
    previousWidth = topology.clientWidth;
    renderMap();
  }
}).observe(topology);

request("/demo/setup")
  .then((setup) => {
    inspector.initialize(setup);
    state.ready = true;
    inspector.setBusy(false);
    updateSetupStatus();
  })
  .catch((error) => {
    setupStatus.textContent = "Setup unavailable";
    setupStatus.className = "minor-label status-failed";
    renderServiceError(error);
  });
