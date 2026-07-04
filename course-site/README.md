# The VINE Course — interactive site

A self-contained, zero-dependency course website that teaches every
prerequisite to build VINE Track 2 (the GSoC project): ETL, time-series,
geospatial/remote sensing, Docker, Kubernetes, the NRP platform, ML/MLOps, and
each of the six deliverables (D1–D6).

**18 modules · 5 parts · ~10k words**, with animated diagrams, an interactive
NDVI calculator, scroll reveals, dark mode, and progress tracking saved in your
browser.

## Run it

No build step, no internet required (fonts load from Google Fonts if online).

~~~bash
# from the repo root — any static server works
cd course-site
python3 -m http.server 8000
# then open http://localhost:8000
~~~

Or just open `course-site/index.html` directly in a browser. (A local server is
recommended so the hash router and animations behave exactly like in production.)

## What's inside

| File | Role |
|------|------|
| `index.html` | page shell (sidebar, progress ring, content slot) |
| `css/style.css` | the vineyard design system + all animations |
| `js/content.js` | all 18 module bodies (markdown), the single source of content |
| `js/markdown.js` | tiny dependency-free markdown → HTML renderer |
| `js/diagrams.js` | animated data-pipeline SVG, ambient background, interactive NDVI widget, confetti |
| `js/app.js` | hash router, renderer, progress (localStorage), theme, scroll-reveal |

## Editing content

All teaching content lives in `js/content.js` as markdown strings. Code blocks
use `~~~` fences (not triple-backticks) so they don't collide with JS template
literals. Special widgets are dropped into markdown with `[[ndvi]]` or
`[[pipeline]]`.

Everything ties back to the real repo — file links point at the actual
`src/vine/...`, `k8s/...`, and `docs/...` paths, and the hands-on exercises run
real commands (`make setup`, `uv run vine ingest`, etc.).
