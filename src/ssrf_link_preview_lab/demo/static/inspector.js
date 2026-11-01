const panels = [...document.querySelectorAll(".node-panel")];
const inspector = document.querySelector(".node-inspector");
const inspectorContent = document.querySelector(".inspector-content");
const inspectorKicker = document.querySelector("#inspector-kicker");
const inspectorTitle = document.querySelector("#inspector-title");
const closeButton = document.querySelector("#close-inspector");
const mobileLayout = window.matchMedia("(max-width: 979px)");
const form = document.querySelector("#preview-form");
const urlInput = document.querySelector("#url");
const exampleTargets = [...document.querySelectorAll(".example-target")];
const selectedExample = document.querySelector("#selected-example");
const selectedExampleUrl = document.querySelector("#selected-example-url");
const externalTarget = document.querySelector("#external-target-url");
const controls = [...document.querySelectorAll(".node-panel input, .node-panel select, .node-panel button")];

export function createInspector({ onChange, onRun, onSelectNode }) {
  const draft = { url: urlInput.value, defense: "none", dns_mode: "stable" };
  let targets = {};
  let selectedNode = "browser";
  let mobileOpen = false;

  function syncVisibility() {
    inspector.dataset.open = String(!mobileLayout.matches || mobileOpen);
    inspector.inert = mobileLayout.matches && !mobileOpen;
  }

  function close() {
    mobileOpen = false;
    inspectorContent.scrollTop = 0;
    syncVisibility();
    document.querySelector(`.node-hit[data-node="${selectedNode}"]`)?.focus({ preventScroll: true });
  }

  closeButton.addEventListener("click", close);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && mobileLayout.matches && mobileOpen) close();
  });
  mobileLayout.addEventListener("change", syncVisibility);
  syncVisibility();

  function syncTargets() {
    let matchedExample = false;
    for (const button of exampleTargets) {
      const selected = draft.url === targets[button.dataset.target];
      button.setAttribute("aria-pressed", String(selected));
      matchedExample ||= selected;
    }
    selectedExample.hidden = !matchedExample;
    selectedExampleUrl.textContent = matchedExample ? draft.url : "";
    for (const control of document.querySelectorAll('input[name="external_response"]')) {
      control.checked = draft.url === targets[control.value];
    }
    externalTarget.textContent = ["page", "redirect_page", "redirect_internal"]
      .some((key) => draft.url === targets[key])
      ? draft.url : "No attacker-web target selected";
  }

  function setTarget(key) {
    if (!targets[key]) return;
    draft.url = targets[key];
    urlInput.value = draft.url;
    syncTargets();
    onChange();
  }

  function chooseTarget(key) {
    setTarget(key);
    onSelectNode("browser", true);
  }

  urlInput.addEventListener("input", () => {
    draft.url = urlInput.value;
    syncTargets();
    onChange();
  });
  for (const button of exampleTargets) {
    button.addEventListener("click", () => setTarget(button.dataset.target));
  }
  for (const control of document.querySelectorAll('input[name="defense"], input[name="dns_mode"]')) {
    control.addEventListener("change", () => {
      draft[control.name] = control.value;
      onChange();
    });
  }
  for (const control of document.querySelectorAll('input[name="external_response"]')) {
    control.addEventListener("change", () => chooseTarget(control.value));
  }
  document.querySelector("#use-rebind").addEventListener("click", () => chooseTarget("rebind"));
  document.querySelector("#use-internal").addEventListener("click", () => chooseTarget("internal"));
  document.querySelector("#use-public").addEventListener("click", () => chooseTarget("public"));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (form.reportValidity()) onRun({ ...draft });
  });

  return {
    getDraft: () => ({ ...draft }),
    getTargets: () => targets,
    initialize(setup) {
      targets = setup.targets;
      draft.defense = setup.defaults.defense;
      draft.dns_mode = setup.defaults.dns_mode;
      draft.url = targets.page;
      urlInput.value = draft.url;
      for (const button of exampleTargets) button.title = targets[button.dataset.target];
      for (const name of ["defense", "dns_mode"]) {
        document.querySelector(`input[name="${name}"][value="${draft[name]}"]`).checked = true;
      }
      syncTargets();
      onChange();
    },
    show(node, { open = true } = {}) {
      selectedNode = node;
      if (mobileLayout.matches) mobileOpen = open;
      syncVisibility();
      for (const panel of panels) panel.hidden = panel.dataset.panel !== node;
      const panel = panels.find((entry) => entry.dataset.panel === node);
      inspectorKicker.textContent = panel.querySelector(".panel-kicker").textContent;
      inspectorTitle.textContent = panel.querySelector("h2").textContent;
      inspectorContent.scrollTop = 0;
    },
    focusPanel() {
      panels.find((panel) => panel.dataset.panel === selectedNode)?.focus({ preventScroll: true });
    },
    align(topology) {
      if (mobileLayout.matches) return;
      const viewport = topology.querySelector(".topology-viewport");
      const node = topology.querySelector(`.node-hit[data-node="${selectedNode}"]`);
      const panel = panels.find((entry) => entry.dataset.panel === selectedNode);
      if (!viewport || !node || !panel) return;
      const map = viewport.getBoundingClientRect();
      const selected = node.getBoundingClientRect();
      const panelHeight = panel.getBoundingClientRect().height;
      const center = selected.top + selected.height / 2 - map.top;
      const top = Math.max(0, Math.min(center - panelHeight / 2, map.height - panelHeight));
      inspector.style.height = `${Math.max(map.height, top + panelHeight)}px`;
      inspector.style.setProperty("--panel-top", `${top}px`);
      inspector.style.setProperty("--pointer-top", `${Math.max(18, Math.min(center - top, panelHeight - 18))}px`);
    },
    setBusy(busy) {
      for (const control of controls) control.disabled = busy;
    },
  };
}
