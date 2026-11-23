# SSRF Link Preview Lab Presentation

Reveal.js source for the project presentation.

## Develop locally

Use Node.js 22.12 or newer, npm, and Python 3. Install the locked JavaScript dependency and serve the source deck locally:

```bash
npm ci
npm run serve
```

Open <http://127.0.0.1:8766/>. The source server is bound to loopback and serves the local Reveal.js dependency from `node_modules`. Do not open `index.html` with `file://`; the deck loads its slide sources over HTTP.

## Build and preview

Build the static site and serve the generated artifact locally:

```bash
npm run build
npm run preview
```

Open <http://127.0.0.1:8767/>. The generated `dist/` directory is ignored by Git. The build copies only the presentation, its assets, and the Reveal.js distribution needed to run it.

Use the arrow keys or Space to navigate. Press `S` to open Reveal.js speaker notes and `T` to cycle system, light, and dark themes. The theme button in the upper-right does the same. The print button opens a one-slide-per-page print view using the current theme; choose **Save to PDF** in the browser print dialog.

For detailed result tables and traces during questions, open the same presentation URL with `?deck=results-backup`, for example <http://127.0.0.1:8766/?deck=results-backup>. This separate deck contains the detailed HTTP, DNS, utility, and policy comparison slides.

## GitHub Pages

The presentation workflow builds the site for pull requests and deploys it from `main`. Enable GitHub Pages in the repository settings and select **GitHub Actions** as the deployment source. After the first successful deployment, the site will be available at <https://djh592.github.io/ssrf-link-preview-lab/>. Only the generated `dist/` site is uploaded.

Speaker notes are included in the published deck source and can be opened with the Reveal.js speaker view. Do not place material in speaker notes unless it is appropriate to publish.

## Structure

- `index.html` is the presentation shell.
- `slides/manifest.json` defines the slide order.
- `slides/` contains one Reveal.js section per slide.
- `assets/` contains images and diagrams used by the deck.
- `styles.css` defines shared presentation styles.

Keep speaker notes in each slide's `<aside class="notes">` element. Add sources for reused visuals to the relevant slide and maintain any detailed asset attribution beside the assets.
