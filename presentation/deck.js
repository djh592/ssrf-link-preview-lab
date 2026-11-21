const themeOrder = ["system", "light", "dark"];
const themeLabels = {
  system: "System",
  light: "Light",
  dark: "Dark",
};
const themeStorageKey = "ssrf-link-preview-theme";
const themeToggle = document.querySelector(".theme-toggle");
const printToggle = document.querySelector(".print-toggle");
const query = new URLSearchParams(window.location.search);
const singleSlidePdf = query.get("pdf-mode") === "slides";
const autoPrint = query.has("auto-print");
const systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");

function currentTheme() {
  return document.documentElement.dataset.theme || "system";
}

function resolvedTheme(theme = currentTheme()) {
  return theme === "system"
    ? systemThemeQuery.matches
      ? "dark"
      : "light"
    : theme;
}

function setTheme(theme, { updateUrl = true, persist = true } = {}) {
  const selectedTheme = themeOrder.includes(theme) ? theme : "system";
  const label = themeLabels[selectedTheme];
  document.documentElement.dataset.theme = selectedTheme;
  document.documentElement.dataset.resolvedTheme = resolvedTheme(selectedTheme);

  if (themeToggle) {
    const description = `Current theme: ${label}. Change slide theme.`;
    themeToggle.setAttribute("aria-label", description);
    themeToggle.title = description;
  }

  if (persist) {
    try {
      window.localStorage.setItem(themeStorageKey, selectedTheme);
    } catch {
      // Theme switching remains available when browser storage is unavailable.
    }
  }

  if (updateUrl) {
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set("theme", selectedTheme);
    window.history.replaceState({}, "", nextUrl);
  }
}

function cycleTheme() {
  const nextIndex = (themeOrder.indexOf(currentTheme()) + 1) % themeOrder.length;
  setTheme(themeOrder[nextIndex]);
}

setTheme(currentTheme(), { updateUrl: false, persist: false });
themeToggle?.addEventListener("click", cycleTheme);
systemThemeQuery.addEventListener("change", () => {
  if (currentTheme() === "system") {
    document.documentElement.dataset.resolvedTheme = resolvedTheme("system");
  }
});

window.addEventListener("keydown", (event) => {
  if (
    event.key.toLowerCase() !== "t" ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey
  ) {
    return;
  }

  const target = event.target;
  if (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  ) {
    return;
  }

  event.preventDefault();
  cycleTheme();
});

function openPrintView() {
  const printUrl = new URL(window.location.href);
  printUrl.hash = "";
  printUrl.searchParams.set("print-pdf", "");
  printUrl.searchParams.set("pdf-mode", "slides");
  printUrl.searchParams.set("theme", currentTheme());
  printUrl.searchParams.set("auto-print", "");
  window.open(printUrl.toString(), "_blank", "noopener");
}

printToggle?.addEventListener("click", openPrintView);

const revealConfig = {
  width: 1600,
  height: 900,
  margin: 0.06,
  hash: true,
  slideNumber: "c/t",
  progress: true,
  controls: true,
  keyboard: true,
  help: true,
  touch: true,
  center: true,
  navigationMode: "linear",
  transition: "none",
  backgroundTransition: "none",
  pdfSeparateFragments: !singleSlidePdf,
  pdfMaxPagesPerSlide: singleSlidePdf ? 1 : Infinity,
  plugins: [RevealNotes],
};

async function loadSlideSources() {
  const manifestResponse = await fetch("slides/manifest.json", {
    cache: "no-store",
  });
  if (!manifestResponse.ok) {
    throw new Error(
      `Could not load slides/manifest.json (HTTP ${manifestResponse.status}).`,
    );
  }

  const manifest = await manifestResponse.json();
  if (
    !manifest ||
    !Array.isArray(manifest.slides) ||
    manifest.slides.length === 0 ||
    manifest.slides.some((path) => typeof path !== "string" || path.length === 0)
  ) {
    throw new Error("slides/manifest.json must contain a non-empty slides array.");
  }

  const sources = await Promise.all(
    manifest.slides.map(async (path) => {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Could not load ${path} (HTTP ${response.status}).`);
      }
      return response.text();
    }),
  );

  const slides = document.querySelector(".slides");
  if (!slides) {
    throw new Error("The Reveal.js slides container is missing.");
  }

  slides.innerHTML = sources.join("\n");
  slides.removeAttribute("aria-busy");
}

function showDeckError(error) {
  const message = error instanceof Error ? error.message : String(error);
  const errorElement = document.querySelector("#deck-error");
  if (errorElement) {
    errorElement.textContent = `${message} Reload the page or verify the published presentation files.`;
    errorElement.hidden = false;
  }
  console.error("Presentation failed to start:", error);
}

async function startDeck() {
  try {
    await loadSlideSources();

    let printDialogOpened = false;
    const openPrintDialog = () => {
      if (!autoPrint || printDialogOpened) {
        return;
      }
      printDialogOpened = true;
      window.setTimeout(() => window.print(), 250);
    };

    Reveal.on("pdf-ready", openPrintDialog);
    await Reveal.initialize(revealConfig);
    if (autoPrint && document.documentElement.classList.contains("print-pdf")) {
      window.setTimeout(openPrintDialog, 750);
    }
  } catch (error) {
    showDeckError(error);
  }
}

void startDeck();
