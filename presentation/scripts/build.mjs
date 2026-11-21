import {
  access,
  copyFile,
  cp,
  mkdir,
  readFile,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outputDirectory = join(projectDirectory, "dist");
const runtimeDirectory = join(projectDirectory, "node_modules/reveal.js/dist");
const runtimePathPrefix = "node_modules/reveal.js/dist/";

async function copyPresentationSources() {
  await rm(outputDirectory, { force: true, recursive: true });
  await mkdir(outputDirectory, { recursive: true });

  for (const entry of ["deck.js", "styles.css", "slides", "assets"]) {
    await cp(join(projectDirectory, entry), join(outputDirectory, entry), {
      recursive: true,
    });
  }

  const sourceHtml = await readFile(join(projectDirectory, "index.html"), "utf8");
  if (!sourceHtml.includes(runtimePathPrefix)) {
    throw new Error(`index.html must reference ${runtimePathPrefix}.`);
  }

  const outputHtml = sourceHtml.replaceAll(runtimePathPrefix, "vendor/reveal.js/");
  await writeFile(join(outputDirectory, "index.html"), outputHtml);
}

async function copyRevealRuntime() {
  await access(runtimeDirectory);
  const vendorDirectory = join(outputDirectory, "vendor/reveal.js");
  await cp(runtimeDirectory, vendorDirectory, { recursive: true });
  await copyFile(
    join(projectDirectory, "node_modules/reveal.js/LICENSE"),
    join(vendorDirectory, "LICENSE"),
  );
}

async function validateSlideManifest() {
  const slidesDirectory = join(outputDirectory, "slides");
  const manifestPath = join(slidesDirectory, "manifest.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  if (
    !manifest ||
    !Array.isArray(manifest.slides) ||
    manifest.slides.length === 0 ||
    manifest.slides.some((path) => typeof path !== "string" || path.length === 0)
  ) {
    throw new Error("slides/manifest.json must contain a non-empty slides array.");
  }

  for (const path of manifest.slides) {
    const slidePath = resolve(outputDirectory, path);
    const relativePath = relative(slidesDirectory, slidePath);
    if (isAbsolute(relativePath) || relativePath.startsWith("..")) {
      throw new Error(`Slide path must stay inside slides/: ${path}`);
    }

    if (!(await stat(slidePath)).isFile()) {
      throw new Error(`Slide file does not exist: ${path}`);
    }
  }
}

await copyPresentationSources();
await copyRevealRuntime();
await validateSlideManifest();

console.log(`Built ${join(outputDirectory, "index.html")} successfully.`);
