const panels = [...document.querySelectorAll(".node-panel")];
const form = document.querySelector("#preview-form");
const urlInput = document.querySelector("#url");
const externalTarget = document.querySelector("#external-target-url");
const controls = [...document.querySelectorAll(".node-inspector input, .node-inspector select, .node-inspector button")];

export function createInspector({ onChange, onRun, onSelectNode }) {
  const draft = { url: urlInput.value, defense: "none", dns_mode: "stable" };
  let targets = {};

  function syncTargets() {
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
    onSelectNode("browser");
  }

  urlInput.addEventListener("input", () => {
    draft.url = urlInput.value;
    syncTargets();
    onChange();
  });
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
      for (const name of ["defense", "dns_mode"]) {
        document.querySelector(`input[name="${name}"][value="${draft[name]}"]`).checked = true;
      }
      syncTargets();
      onChange();
    },
    show(node) {
      for (const panel of panels) panel.hidden = panel.dataset.panel !== node;
      return panels.find((panel) => panel.dataset.panel === node);
    },
    setBusy(busy) {
      for (const control of controls) control.disabled = busy;
    },
  };
}
