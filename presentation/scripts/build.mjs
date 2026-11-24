import {
  access,
  copyFile,
  cp,
  mkdir,
  readdir,
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

async function validateSlideManifest(manifestName) {
  const slidesDirectory = join(outputDirectory, "slides");
  const manifestPath = join(slidesDirectory, manifestName);
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  if (
    !manifest ||
    !Array.isArray(manifest.slides) ||
    manifest.slides.length === 0 ||
    manifest.slides.some((path) => typeof path !== "string" || path.length === 0)
  ) {
    throw new Error("slides/manifest.json must contain a non-empty slides array.");
  }

  const referencedFiles = new Set();

  for (const [index, path] of manifest.slides.entries()) {
    const expectedPrefix = `${String(index + 1).padStart(3, "0")}-`;
    const fileName = path.slice("slides/".length);
    if (!path.startsWith("slides/") || !fileName.startsWith(expectedPrefix)) {
      throw new Error(
        `Slide ${index + 1} must use the ${expectedPrefix} filename prefix: ${path}`,
      );
    }

    if (referencedFiles.has(fileName)) {
      throw new Error(`Slide manifest contains a duplicate entry: ${path}`);
    }
    referencedFiles.add(fileName);

    const slidePath = resolve(outputDirectory, path);
    const relativePath = relative(slidesDirectory, slidePath);
    if (isAbsolute(relativePath) || relativePath.startsWith("..")) {
      throw new Error(`Slide path must stay inside slides/: ${path}`);
    }

    if (!(await stat(slidePath)).isFile()) {
      throw new Error(`Slide file does not exist: ${path}`);
    }
  }

  const slideFiles = (await readdir(slidesDirectory))
    .filter((fileName) => fileName.endsWith(".html"))
    .sort();
  const unreferencedFiles = slideFiles.filter(
    (fileName) => !referencedFiles.has(fileName),
  );
  if (unreferencedFiles.length > 0) {
    throw new Error(
      `Slide files are not referenced by ${manifestName}: ${unreferencedFiles.join(", ")}`,
    );
  }
}

await copyPresentationSources();
await copyRevealRuntime();
await validateSlideManifest("manifest.json");

console.log(`Built ${join(outputDirectory, "index.html")} successfully.`);
