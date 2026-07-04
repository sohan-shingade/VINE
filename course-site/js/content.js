/* ============================================================
   COURSE CONTENT. Markdown bodies use ~~~ code fences (so they
   don't collide with JS template-literal backticks). Inline
   code uses escaped backticks \` \`.
   ============================================================ */
window.COURSE = {
  title: "The VINE Course",
  parts: [
    {
      title: "Part 1 — Foundations",
      blurb: "The bedrock: a reproducible Python toolchain, the ETL mindset, time-series, and remote sensing.",
      modules: [
        {
          num: 1, slug: "python-toolchain", title: "Python & the modern toolchain",
          hook: "Before any model, you need an environment you can rebuild byte-for-byte and a repo that stays clean on its own.",
          body: `
## Objectives
After this module you can:
- Explain *why* reproducible environments matter and rebuild VINE's with one command.
- Use \`uv\` to manage the venv, dependencies, and optional extras.
- Run the project's quality gate (\`make check\`) and understand each tool in it.
- Navigate the \`src/\` layout and the branch convention.

## Concepts

### Why this comes first
A model is only as trustworthy as the environment that produced it. "Works on my machine" is the enemy of science. The whole VINE project is built on a rule: **a run is determined by a config + a seed + a locked environment.** This module is the environment half.

### uv — the package manager
\`uv\` is a fast, modern replacement for pip + virtualenv + poetry. We use **only** uv (never pip/poetry/conda directly). It does two jobs:

- **Resolves + locks** every dependency to an exact version in \`uv.lock\`, so anyone can reproduce the exact same library set.
- **Runs** commands inside the project venv with \`uv run <cmd>\` — no manual "activate" needed.

Heavy/optional libraries (torch, rasterio, geopandas) live in **extras** so the core installs light:

~~~bash
uv add influxdb-client --optional sensors   # add a dep to the 'sensors' extra
uv run python -c "import vine; print(vine.__file__)"
~~~

:::warn Never hand-edit dependency versions in \`pyproject.toml\`. Use \`uv add\` so the lockfile stays consistent.
:::

### The quality gate
\`make check\` is **the gate** — run it before every commit. It chains three tools:

| Tool | Job | Analogy |
|------|-----|---------|
| **ruff** | lint + format (line length 100) | spell-check + grammar for code |
| **mypy** | static type checking | catches "you passed a string where an int goes" before runtime |
| **pytest** | runs the tests | proves the math still works |

\`pytest\` markers \`slow\` and \`gpu\` are skipped by default so the everyday loop is fast. **pre-commit** runs a subset automatically on every \`git commit\`, and blocks files larger than 1 MB (so you never commit a \`.tif\` or \`.pt\`).

### The src/ layout
Code lives under \`src/vine/\`, one subpackage per deliverable (\`d1_pipeline\`, \`d2_irrigation\`, … \`d6_serving\`, plus \`common\`). The \`src/\` layout forces you to install the package to import it — which means tests run against the *installed* code, not loose files. That catches packaging bugs early.

## In this repo
- [\`pyproject.toml\`](../pyproject.toml) — declares deps, extras, and tool config (ruff/mypy/pytest).
- [\`Makefile\`](../Makefile) — the commands you actually run: \`setup\`, \`check\`, \`fmt\`, \`test\`.
- [\`src/vine/common/\`](../src/vine/common/) — config, logging, seeding; import shared helpers from here.
- Branch convention: \`track/<deliverable>-<short-desc>\` e.g. \`irrigation/d2-lstm-encoder\`.

## Hands-on
1. Run \`make setup\`. Watch uv build the venv and install every extra. This is your "rebuild from scratch" button — it should *always* work.
2. Run \`make check\`. Read the output: which tool ran, what passed. This is the bar every PR must clear.
3. Break something on purpose: add an unused import to any \`.py\` file, run \`make check\`, watch ruff catch it, then \`make fmt\` to autofix.
4. Run a single test file: \`uv run pytest tests/d1_pipeline/test_indices.py -q\`. Note how fast the pure-math tests are.
5. Open \`pyproject.toml\` and find the \`[project.optional-dependencies]\` table. List which extra each model track pulls in.

## Self-test
- Why does the project forbid \`pip install\` directly?
- What does \`uv.lock\` guarantee that \`pyproject.toml\` alone does not?
- Which three tools does \`make check\` run, and what class of bug does each catch?
- Why are torch and rasterio in extras instead of core dependencies?
- Where would you add a new dependency used only by the harvest model?

## References
- uv docs — astral.sh/uv · ruff — docs.astral.sh/ruff · mypy — mypy.readthedocs.io
- This repo: ADR-0002 (why uv), ADR-0001 (monorepo src layout).
`,
        },
        {
          num: 2, slug: "etl-fundamentals", title: "Big data & ETL fundamentals",
          hook: "Every model is downstream of data plumbing. Get the plumbing right and the rest is science; get it wrong and everything lies.",
          body: `
## Objectives
After this module you can:
- Define ETL/ELT and trace each stage on the VINE sensor data.
- Choose the right storage format and explain why Parquet beats CSV here.
- Explain idempotency and why re-running ingestion must be safe.
- Describe the raw → interim → processed layering and how DVC versions it.

## Concepts

### ETL in one sentence
**Extract** data from a source, **Transform** it into a clean usable shape, **Load** it where models can read it. (ELT just reorders: load raw first, transform later.)

For VINE, the sensor path is:
- **Extract** — pull rows from InfluxDB with a Flux query.
- **Transform** — tidy columns, regularize timestamps, flag gaps.
- **Load** — write one Parquet file per device into \`data/raw/sensors/\`.

### Batch vs streaming
- **Batch**: grab a chunk ("last 7 days") on a schedule. Simple, reproducible. This is what VINE does — a CronJob pulls a window.
- **Streaming**: process each reading as it arrives. Powerful but heavier; overkill for a vineyard that samples every several minutes.

### Why Parquet, not CSV
| | CSV | Parquet |
|--|-----|---------|
| Layout | row-by-row text | **columnar** binary |
| Read one column | scans whole file | reads just that column |
| Types | everything is a string | preserves int/float/timestamp |
| Size | big | compressed, often 5–10× smaller |

Columnar storage is the right call when you analyze a few columns across many rows — exactly the sensor case. CSV is for tiny human-readable handoffs only.

### Idempotency
**Re-running ingestion should produce the same result, not duplicate or corrupt data.** If the CronJob runs twice, you must not get double rows. We achieve this by writing deterministic, overwritable per-device files keyed by a time window — re-running the same window just rewrites the same file.

:::note Idempotency is what lets you retry safely. Pipelines fail constantly (network blips, pod evictions). A pipeline you can't re-run is a pipeline you can't trust.
:::

### The data lake layers
- **raw/** — exactly what the source gave us, untouched (the source of truth).
- **interim/** — cleaned, regularized, joined.
- **processed/** — model-ready feature tables.

Never edit raw. If a transform is wrong, you fix the code and regenerate interim/processed from raw. Raw + code = everything else.

### "Big data"? Right-size it.
VINE is gigabytes, not petabytes — no Spark cluster needed. But the *concepts* (partitioning, columnar formats, idempotent batch jobs, versioning) are exactly what scales later. Learn them here at a comfortable size.

### Versioning with DVC
Code is versioned by git. **Data is versioned by DVC** (which stores the bytes on NRP S3 and keeps a tiny pointer file in git). So a model's commit records the exact data version that trained it — full reproducibility.

## In this repo
- [\`src/vine/d1_pipeline/ingest.py\`](../src/vine/d1_pipeline/ingest.py) — \`ingest_all(start)\`: the orchestrator that writes Parquet per device.
- \`data/raw/sensors/\` — the load target (gitignored, DVC-tracked).
- The CronJob in [\`k8s/d1_ingest/cronjob.yaml\`](../k8s/d1_ingest/cronjob.yaml) runs this on a schedule.

## Hands-on
1. Run \`uv run vine ingest --start=-7d\`. Inspect \`data/raw/sensors/\` — note one Parquet file per device.
2. Run the exact same command again. Confirm you did **not** get duplicate data — that's idempotency in action.
3. Load one file: \`uv run python -c "import pandas as pd; print(pd.read_parquet('data/raw/sensors/<file>.parquet').head())"\`.
4. Compare sizes: re-save that frame as CSV and compare bytes. Quantify the Parquet win.
5. Read \`ingest.py\` and find where the time window becomes the file key. Explain why that makes re-runs safe.

## Self-test
- Trace the three ETL stages for the sensor pipeline, naming the tool at each.
- Give two concrete reasons Parquet is the right format here.
- What breaks if ingestion is *not* idempotent and the CronJob double-fires?
- Why must \`raw/\` never be edited by hand?
- What does a git commit + DVC pointer together let you reproduce?

## References
- Apache Parquet docs · DVC docs (dvc.org) · This repo: ADR-0005 (tracking), ADR-0008 (sensor source).
`,
        },
        {
          num: 3, slug: "time-series", title: "Time-series data",
          hook: "Sensor data is gappy, noisy, and irregular. Treating it like a clean spreadsheet is how you ship a model that lies.",
          body: `
## Objectives
After this module you can:
- Handle timestamps and timezones correctly (everything UTC).
- Resample irregular readings onto a regular grid.
- Build lag and rolling-window features.
- Distinguish a sensor gap from a real signal — and never silently impute.

## Concepts

### Time is the index
In a time-series, the timestamp *is* the primary key. Rule one: **store everything in UTC**, convert to local only for display. Mixed timezones silently corrupt joins and create phantom daily patterns.

### Tidy long vs wide
- **Long/tidy**: one row per (timestamp, device, measurement, value). Flexible, easy to filter.
- **Wide**: one row per timestamp, one column per measurement. What most models want.

You pivot from long to wide late in the pipeline, once you know which signals a model needs.

### Regular vs irregular sampling
Real sensors don't fire on a perfect clock — readings arrive every "roughly N minutes," with jitter and dropouts. Most models assume a **regular grid**. So you **resample**:
- **Downsample** (e.g. to hourly means) to smooth noise and align devices.
- **Upsample** only with explicit, flagged interpolation — never pretend you have data you don't.

~~~python
# conceptual: hourly mean, but track how many real readings backed each bucket
hourly = df.resample("1H").agg(value=("value","mean"), n=("value","size"))
hourly["is_gap"] = hourly["n"] == 0
~~~

### Lags and rolling windows
The past predicts the future, so features are built from history:
- **Lag features**: value 1h ago, 24h ago.
- **Rolling stats**: 6-hour mean soil moisture, 24-hour max temperature.

These turn a raw stream into the inputs D2 (irrigation) and D4 (harvest) forecast from.

### The gap problem — the rule that matters
Sensors fail. A flat-lined or missing stretch can mean (a) the sensor died, or (b) the real value genuinely didn't change. **You must distinguish these, and you must never silently fill gaps.** Silent imputation invents data and the model learns the imputation, not the vineyard.

:::warn VINE rule: flag gaps explicitly (see \`validation.py\`). A flagged gap is honest; a quietly interpolated one is a lie that survives all the way to a prediction.
:::

### Seasonality & stationarity (preview)
Soil moisture has daily cycles (irrigation, evapotranspiration) and seasonal trends. Many classical forecasters assume **stationarity** (stable mean/variance) and need you to remove trend/seasonality first. You'll use this in Module 13.

## In this repo
- [\`src/vine/d1_pipeline/influx.py\`](../src/vine/d1_pipeline/influx.py) — \`InfluxReader\` pulls the raw stream; \`tidy\` mode drops metadata columns.
- [\`src/vine/d1_pipeline/validation.py\`](../src/vine/d1_pipeline/validation.py) — gap flagging; the place that enforces "never silently impute."
- [\`src/vine/d1_pipeline/features.py\`](../src/vine/d1_pipeline/features.py) — lag/rolling feature construction.

## Hands-on
1. Pull a week: \`uv run vine ingest --start=-7d\`, load one device, and \`print(df.index.tz)\` — confirm UTC.
2. Resample raw readings to hourly means and count readings per bucket. Find the buckets with zero readings — those are gaps.
3. Build a 24-hour rolling mean of soil moisture. Plot raw vs smoothed (mentally or with matplotlib).
4. Read \`validation.py\`. Find how a gap is represented. Why is a boolean flag better than a filled value?
5. Construct a lag-24h feature for one signal. Confirm the first 24 hours are correctly marked unknown, not zero.

## Self-test
- Why store timestamps in UTC even though the vineyard is in California?
- When would you downsample vs upsample, and what's the danger of upsampling?
- Give a real scenario where a flat sensor reading is signal, and one where it's failure.
- What does the project forbid you from doing to a gap, and why?
- Which two deliverables consume the lag/rolling features built here?

## References
- pandas time-series guide · "Forecasting: Principles and Practice" (otexts.com/fpp3) ch. on stationarity.
- This repo: the D1 datasheet, ADR-0008.
`,
        },
        {
          num: 4, slug: "geospatial", title: "Geospatial & remote sensing",
          hook: "A drone photo is just numbers in a grid — until you know which numbers are 'near-infrared' and what 'healthy plant' looks like in that band.",
          body: `
## Objectives
After this module you can:
- Explain rasters, bands, and multispectral vs RGB imagery.
- Compute and interpret vegetation indices (NDVI, NDRE).
- Reason about coordinate reference systems (CRS) and why alignment matters.
- Align imagery to vineyard-block polygons with geopandas.

## Concepts

### A raster is a grid of numbers
An image is a grid of pixels; each pixel holds one number **per band**. A normal photo has 3 bands (Red, Green, Blue). A **multispectral** camera captures more — the DJI Mavic 3 Multispectral on this project records **Green, Red, Red-edge, and Near-Infrared (NIR)** plus an RGB "visual."

### Why extra bands matter
Plants don't care about looking green to us. **Healthy leaves strongly reflect near-infrared** (their cell structure bounces it back) and **absorb red** (chlorophyll eats it for photosynthesis). Stressed plants reflect *less* NIR and *more* red. Your eyes can't see NIR — the camera can. That invisible band is where plant health hides.

### Vegetation indices
An index combines bands into one number that tracks a physical property.

- **NDVI** = (NIR − Red) / (NIR + Red). Ranges −1…+1. Near 0 = bare soil/water; high = dense healthy canopy.
- **NDRE** = (NIR − RedEdge) / (NIR + RedEdge). Uses red-edge, which is more sensitive in dense canopy where NDVI "saturates" — good for an established vineyard.

[[ndvi]]

### Coordinate reference systems (CRS)
A pixel's row/column means nothing until you know *where on Earth* it sits. A **CRS** maps pixels to coordinates (e.g. lat/lon in EPSG:4326, or a meters-based UTM zone). **Every layer must share a CRS before you can combine them** — overlaying a raster and block polygons in different CRSs silently misaligns everything.

### Orthomosaics & stitching
A drone takes thousands of overlapping photos. To analyze a field you **stitch** them into one geometrically-corrected **orthomosaic** (overhead, true-to-scale). VINE's imagery is **raw per-photo, not yet stitched** — 9,295 captures across 11 flights — so D1 must stitch + georeference before block analysis. That's real work, not a given.

### Vector data & block alignment
Vineyard **blocks** (Cd, H5, H4, E, H2, Q, Ce) are polygons — vector geometry, not pixels. With **geopandas** you load these polygons and "clip"/"zonal-stat" the raster to each block, so every prediction is reported **per block** (the contract the whole project keeps).

## In this repo
- [\`src/vine/d1_pipeline/indices.py\`](../src/vine/d1_pipeline/indices.py) — pure \`ndvi()\` / \`ndre()\` functions (unit-tested, no I/O).
- [\`src/vine/d1_pipeline/imagery.py\`](../src/vine/d1_pipeline/imagery.py) — raster loading (rasterio/rioxarray, lazy-imported).
- [\`src/vine/d1_pipeline/geo.py\`](../src/vine/d1_pipeline/geo.py) — block-polygon alignment with geopandas.
- The imagery inventory (STAC): 9,295 captures, DJI Mavic 3M, blocks Cd/H5/H4/E/H2/Q/Ce.

## Hands-on
1. Use the NDVI slider above. Set NIR high + Red low (healthy) then flip them (stressed). Watch the value and color.
2. Read \`indices.py\`. Confirm the functions are pure (no file reads) — why does that make them easy to test?
3. Run \`uv run pytest tests/d1_pipeline/test_indices.py -q\`. Note how indices are validated against known inputs.
4. Sketch the pipeline from "9,295 raw photos" to "one NDVI value per block." Which steps are missing in the repo today?
5. Look up the vineyard's CRS needs: coordinates are 38.457 N, −122.896 W. Which UTM zone is that, and why might you reproject into it?

## Self-test
- Physically, why does healthy vegetation read high on NDVI?
- When would NDRE beat NDVI for an established vineyard?
- What goes wrong if a raster and the block polygons are in different CRSs?
- Why is "stitch into an orthomosaic" a required step here, not optional?
- Why are the index functions kept pure and I/O-free?

## References
- rasterio & rioxarray docs · geopandas.org · USGS Landsat NDVI explainer.
- This repo: D1 datasheet (imagery inventory), ADR on imagery source.
`,
        },
      ],
    },
    {
      title: "Part 2 — Platform & infrastructure",
      blurb: "Where it runs: containers, Kubernetes, the free NRP/Nautilus cluster, and every data source you'll pull from.",
      modules: [
        {
          num: 5, slug: "docker", title: "Containers & Docker",
          hook: "A model that runs on your laptop is a demo. A model in a container runs anywhere — including a GPU node you've never logged into.",
          body: `
## Objectives
After this module you can:
- Explain what a container is and how it differs from a VM.
- Read a Dockerfile and describe what each instruction builds.
- Explain layers, caching, and image tags.
- Say why we containerize VINE models before deploying them.

## Concepts

### Container vs VM
A **virtual machine** ships a whole guest operating system — heavy, slow to boot. A **container** shares the host kernel and packages just your app + its dependencies — light, starts in milliseconds. Think "shipping container": a standard box that fits any ship (any machine with a container runtime).

### Image vs container
- An **image** is the frozen blueprint (your code + Python + libs).
- A **container** is a running instance of that image.

Build once (image), run many (containers).

### The Dockerfile
A recipe, top to bottom:

~~~dockerfile
FROM python:3.11-slim          # base image
WORKDIR /app
COPY pyproject.toml uv.lock ./ # copy dep manifests first (caching!)
RUN pip install uv && uv sync --extra serve
COPY src/ src/                 # then copy code
CMD ["uv", "run", "vine", "serve"]  # what runs when the container starts
~~~

### Layers & caching
Each instruction creates a **layer**. Docker caches layers and reuses them if nothing changed. That's why you copy dependency files *before* source code: deps change rarely, so the expensive \`install\` layer stays cached while you edit code. Order your Dockerfile cheapest-changing → most-changing.

### Tags & registries
An image is named like \`registry/path:tag\`, e.g. \`gitlab-registry.nrp-nautilus.io/ihv/vine-serving:v1\`. You **push** images to a **registry**; the cluster **pulls** them to run. Tags version your images — never rely on \`:latest\` in production.

### Why containerize models
- **Reproducible deps** — the locked environment travels with the code.
- **Portability** — same image on your laptop, CI, and an A100 GPU node.
- **Isolation** — D2's torch version can't break D3's.

VINE has one Dockerfile per deliverable that needs to run on the cluster.

## In this repo
- [\`docker/\`](../docker/) — \`d1_ingest\`, \`d2_irrigation\`, \`d3_vision\`, \`d4_harvest\` Dockerfiles.
- Images target the GitLab registry \`gitlab-registry.nrp-nautilus.io\`.
- Each image installs only the extra it needs (e.g. serving installs \`--extra serve\`).

## Hands-on
1. Read \`docker/d1_ingest.Dockerfile\`. List its layers top to bottom and predict which are cached on a code-only change.
2. If Docker is installed locally: \`docker build -f docker/d1_ingest.Dockerfile -t vine-ingest:dev .\` and watch the layers build.
3. Edit a comment in a \`.py\` file and rebuild. Note which layers are reused (cache hits) vs rebuilt.
4. Explain why the Dockerfile copies \`pyproject.toml\` before \`src/\`.
5. Find where the run command (\`CMD\`/\`ENTRYPOINT\`) is set and map it to a \`vine\` CLI subcommand.

## Self-test
- One sentence: container vs VM.
- Why copy dependency manifests before source code?
- What's the difference between an image and a container?
- Why is \`:latest\` a bad tag to deploy?
- Why does each deliverable get its own image instead of one big shared one?

## References
- Docker docs (docs.docker.com) · "Dockerfile best practices."
- This repo: the \`docker/\` directory, ADR-0007 (NRP infra).
`,
        },
        {
          num: 6, slug: "kubernetes", title: "Kubernetes fundamentals",
          hook: "Kubernetes is how you tell a cluster 'keep this running' and walk away. Learn five objects and the rest is detail.",
          body: `
## Objectives
After this module you can:
- Explain what Kubernetes does and the cluster mental model.
- Identify the core objects: Pod, Deployment, Job, CronJob, Service, ConfigMap, Secret, PVC.
- Read VINE's manifests and predict what they create.
- Reason about namespaces and GPU resource requests.

## Concepts

### What problem it solves
You have many machines and many containers. Who decides which container runs where, restarts crashes, and exposes a stable address? **Kubernetes (K8s)** — a container orchestrator. You describe the *desired state* in YAML; K8s makes reality match and keeps it there.

### The mental model
- **Control plane** — the brain that schedules and reconciles.
- **Nodes** — the worker machines (some with GPUs).
- You almost never touch nodes directly; you submit objects and let K8s place them.

### The objects you need
| Object | What it is | VINE use |
|--------|-----------|----------|
| **Pod** | one or more containers running together (smallest unit) | a model process |
| **Deployment** | keeps N identical pods alive, handles rollouts | the serving API |
| **Job** | run-to-completion task | a one-off batch vision inference |
| **CronJob** | a Job on a schedule | the D1 sensor ingestion every N hours |
| **Service** | stable network address + load-balancing over pods | reach the API at one URL |
| **ConfigMap** | non-secret config (endpoints, params) | VINE settings |
| **Secret** | sensitive values (tokens) | the InfluxDB / S3 tokens |
| **PersistentVolumeClaim (PVC)** | durable storage that outlives a pod | model checkpoints on CephFS |

### Declarative, not imperative
You don't run "start container." You declare "I want 2 replicas of this image" and \`kubectl apply -f deployment.yaml\`. If a pod dies, K8s restarts it to match your declared count. This is the whole philosophy: **describe the destination, not the steps.**

### Namespaces
A namespace is a walled section of the cluster. VINE lives in namespace **\`ihv\`**. Every command is scoped: \`kubectl get pods -n ihv\`.

### Requests, limits, and GPUs
A pod **requests** CPU/memory/GPU and the scheduler finds a node that fits. GPUs are requested explicitly:

~~~yaml
resources:
  limits:
    nvidia.com/gpu: 1      # ask for one GPU
~~~

On a shared cluster, request only what you need and release it — Module 7 covers the etiquette.

:::warn Secrets are **never** baked into images or committed to git. They're K8s Secrets, injected as env vars at runtime. The InfluxDB token in particular stays out of the repo.
:::

## In this repo
- [\`k8s/base/configmap.yaml\`](../k8s/base/configmap.yaml) + \`pvc.yaml\` — shared config + storage.
- [\`k8s/d1_ingest/cronjob.yaml\`](../k8s/d1_ingest/cronjob.yaml) — scheduled sensor ingestion.
- [\`k8s/d6_serving/\`](../k8s/d6_serving/) — the irrigation Deployment + Service, and a vision batch Job.
- All manifests set \`namespace: ihv\`.

## Hands-on
1. Read \`k8s/d1_ingest/cronjob.yaml\`. What schedule does it run on, and which image + command does it launch?
2. Read \`k8s/d6_serving/irrigation-deployment.yaml\` and \`-service.yaml\`. How does traffic reach a pod through the Service?
3. Find where env vars come from — trace a config value back to the ConfigMap, and a token back to a Secret reference.
4. (If you have kubeconfig) \`kubectl get pods -n ihv\` and \`kubectl describe cronjob -n ihv\`. Note: kubeconfig is mentor-sponsored and pending per the project state — until then, dry-run by reading.
5. Predict: if you delete a pod from the Deployment, what does K8s do, and why?

## Self-test
- Desired-state vs imperative: what does \`kubectl apply\` actually promise?
- When do you use a CronJob vs a Deployment vs a Job? Give a VINE example of each.
- What's the role of a Service if pods already run the container?
- How does a pod ask for a GPU?
- Why are tokens K8s Secrets and not ConfigMap entries or image layers?

## References
- kubernetes.io "Concepts" · "Kubernetes in 100 seconds" for intuition.
- This repo: the \`k8s/\` directory, ADR-0007.
`,
        },
        {
          num: 7, slug: "nrp-platform", title: "The NRP / Nautilus platform",
          hook: "NRP is a free, nationwide research supercomputer you reach with kubectl. Knowing its storage tiers and etiquette is the difference between fast work and a blocked PR.",
          body: `
## Objectives
After this module you can:
- Describe what NRP/Nautilus is and how access works.
- Match each storage need to the right NRP tier.
- Get and use the portal tokens (S3, LLM) safely.
- Be a good citizen on a shared GPU cluster.

## Concepts

### What NRP is
The **National Research Platform (Nautilus)** is a free, NSF/DOE/DoD-funded Kubernetes cluster — 400+ nodes across 70+ sites, led by UC San Diego. VINE runs **entirely** on it: no cloud bill, no hardware. You interact with it exactly like Module 6's Kubernetes, because it *is* Kubernetes.

### Getting access
Access is by **namespace**, sponsored by your mentor — VINE's is \`ihv\`. You get a **kubeconfig** file that points \`kubectl\` at the cluster with your credentials. (In VINE's current state this kubeconfig is still pending from the mentor — you scope and build locally until it lands.)

### GPU pods
Training runs **interactively on GPU pods** (A100 / L40 / RTX A6000), not in CI. You launch a pod requesting a GPU, do your training, and **release it** when done. CI only lints and runs fast tests — never trains.

### Storage tiers — pick the right one
| Need | Tier | Why |
|------|------|-----|
| Datasets, MLflow artifacts | **S3 (Ceph)** at \`s3-west.nrp-nautilus.io\` | object storage, accessed with boto3; bucket \`ihv-vine\` |
| Model checkpoints, large files | **CephFS** PVC | high parallel throughput for big writes |
| Small files, pip caches | **RBD** PVC | low latency |

Using S3 for tiny files or RBD for huge checkpoints will hurt — match the tier to the access pattern.

### The registry & the managed LLM
- **GitLab registry** \`gitlab-registry.nrp-nautilus.io\` holds your built images (Module 5).
- An **OpenAI-compatible LLM** lives at \`ellm.nrp-nautilus.io/v1\` (11 models). Optional for VINE — handy if you later add natural-language block-health summaries. Not required by any core track.

### Portal tokens — handle with care
You mint tokens from the NRP portal:
- \`/s3token/\` → \`AWS_ACCESS_KEY_ID\` / \`AWS_SECRET_ACCESS_KEY\` for S3 + DVC.
- \`/llmtoken/\` → the LLM API key.

:::warn Tokens go in \`.env\` (gitignored), never in code or git. The starter repo once shipped a live InfluxDB token publicly — that's exactly the mistake to avoid; rotate anything that leaks.
:::

### Shared-cluster etiquette
Hundreds of researchers share NRP. Request only the GPUs you'll use, don't leave idle pods holding A100s, set resource limits, and clean up Jobs. Good citizenship keeps your namespace in good standing.

## In this repo
- [\`docs/infrastructure.md\`](../docs/infrastructure.md) — the canonical NRP/NDP map.
- [\`src/vine/common/config.py\`](../src/vine/common/config.py) — reads \`VINE_*\` / \`AWS_*\` settings from env.
- DVC remote points at \`s3://ihv-vine/dvc\` on NRP S3.
- Verified endpoints + access live in [\`docs/STATE.md\`](../docs/STATE.md).

## Hands-on
1. Read \`docs/infrastructure.md\` and list which storage tier each VINE artifact type belongs in.
2. Open \`.env.example\` (or the config) and identify every token the project expects. Where does each come from?
3. Confirm S3 access conceptually: the DVC remote is \`s3://ihv-vine/dvc\` — trace how creds flow from \`.env\` → boto3 → DVC.
4. List the access still pending per \`docs/STATE.md\` (hint: kubeconfig, storage classes). Why can you still do most D1 work without it?
5. Decide: you need to store 40 GB of model checkpoints during training. Which tier, and why not S3?

## Self-test
- What is NRP, who can use it, and what does it cost?
- Match: datasets, checkpoints, pip cache → S3 / CephFS / RBD.
- Where do training runs happen, and where do they *not*?
- How do you obtain S3 credentials, and where must they never appear?
- Name two shared-cluster etiquette rules.

## References
- NRP docs portal (docs.nrp.ai) · nrp.ai.
- This repo: ADR-0006 (NDP), ADR-0007 (NRP infra), STATE.md.
`,
        },
        {
          num: 8, slug: "data-sources", title: "The data sources",
          hook: "Four inputs feed everything. Knowing which is the live source and which is just a catalog saves you from chasing data that was never there.",
          body: `
## Objectives
After this module you can:
- Distinguish a live data source from a catalog/publishing layer.
- Query InfluxDB with Flux via the project's reader.
- Explain CKAN (NDP) and STAC, and what each indexes.
- Pull weather from Open-Meteo and object data from S3.

## Concepts

### The four inputs
| # | Input | Source | Status |
|---|-------|--------|--------|
| 1 | Sensors | InfluxDB bucket \`ihv\` | ✅ live, verified |
| 2 | Drone imagery | NextCloud files + STAC index | ✅ scoped (files behind maintenance) |
| 3 | Historical harvest/yield | not in InfluxDB/NDP — mentor | ⚠️ pending |
| 4 | Weather | Open-Meteo archive API | ✅ verified |

### Live source vs catalog — the key distinction
- **InfluxDB is the live source.** Sensors → ThingsBoard → InfluxDB. The actual numbers live here.
- **NDP (National Data Platform) is a catalog**, built on **CKAN**. A catalog stores *metadata* — "this dataset exists, here's where to get it" — not necessarily the bytes. Confusing the two sends you hunting for data in the wrong place. NDP points you *to* InfluxDB and *to* the imagery; it isn't the data itself.

### InfluxDB + Flux
InfluxDB is a **time-series database**. You query it in **Flux**, a pipe-based language:

~~~flux
from(bucket: "ihv")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "soil_moisture")
~~~

VINE's \`InfluxReader\` builds these queries for you and returns a tidy DataFrame. The endpoint is public HTTPS but **token-gated** (\`VINE_INFLUX_TOKEN\`).

### CKAN (NDP)
**CKAN** is open-source data-catalog software (think "library card catalog for datasets"). Its API lives at \`nationaldataplatform.org/catalog/api/3/action/\`. VINE found 2 Iron Horse datasets there: one pointing to the IoT sensors, one to the drone imagery.

### STAC
**STAC = SpatioTemporal Asset Catalog** — a standard for indexing geospatial assets (satellite/drone imagery) with location + time metadata. VINE used the STAC catalog at \`ndp-test.sdsc.edu/stac/...\` to inventory **9,295 drone captures** across 11 flights without downloading them all first.

### Object storage (S3) & weather
- **S3** (boto3): buckets hold objects keyed by path; VINE's bucket is \`ihv-vine\`. Used for datasets, MLflow artifacts, and the DVC remote.
- **Open-Meteo**: a free, keyless weather API. The archive endpoint gives historical tmax/tmin/precip and **ET₀** (reference evapotranspiration — how thirsty the atmosphere is) right at the vineyard's coordinates.

## In this repo
- [\`src/vine/d1_pipeline/influx.py\`](../src/vine/d1_pipeline/influx.py) — \`InfluxReader\`, the DEVICES catalog, Flux query builder.
- [\`src/vine/d1_pipeline/ndp.py\`](../src/vine/d1_pipeline/ndp.py) — \`NDPClient\` (CKAN: search, list org datasets, download resource).
- Verified endpoints + tokens map in [\`docs/STATE.md\`](../docs/STATE.md) and [\`docs/infrastructure.md\`](../docs/infrastructure.md).

## Hands-on
1. Read \`influx.py\`. Find the DEVICES catalog and the Flux range/filter logic. Which measurements can it pull?
2. Run \`uv run vine ingest --start=-1d\` and confirm rows come back — that's the live source working.
3. Read \`ndp.py\`. What does \`list_org_datasets\` return — data, or pointers to data? Tie that back to "catalog vs source."
4. Hit Open-Meteo's archive API in a browser for the vineyard coords (38.457, −122.896) for last week. Confirm ET₀ is present.
5. In one paragraph, explain to a teammate why you'd never expect the raw sensor numbers to live "inside NDP."

## Self-test
- Live source vs catalog: which is InfluxDB, which is NDP, and why does the distinction matter?
- What language queries InfluxDB, and what shape does \`InfluxReader\` return?
- What does STAC let you do that downloading every image first would not?
- What is ET₀ and which model track most wants it?
- Which of the four inputs is still blocked, and which deliverable does that affect?

## References
- InfluxDB Flux docs · CKAN API docs · stacspec.org · open-meteo.com/en/docs.
- This repo: ADR-0006 (NDP), ADR-0008 (InfluxDB), ADR-0009 (weather), STATE.md.
`,
        },
      ],
    },
    {
      title: "Part 3 — ML & MLOps",
      blurb: "The discipline: climb the complexity ladder, prove you beat baselines, and make every run reproducible.",
      modules: [
        {
          num: 9, slug: "ml-foundations", title: "ML foundations for VINE",
          hook: "Fancy models are easy to start and hard to trust. The rule here: nothing ships until it provably beats something dumb.",
          body: `
## Objectives
After this module you can:
- Frame each VINE track as a concrete ML task (forecast / classify / regress).
- Climb the complexity ladder: naive → classical → deep.
- Split time-series data without leaking the future.
- Spot the most common ways an evaluation lies to you.

## Concepts

### Three tasks, one discipline
- **D2 irrigation** — *forecasting*: predict future soil moisture (regression over time).
- **D3 vision** — *classification*: label blocks/leaves as healthy/stressed/pest from imagery.
- **D4 harvest** — *regression/ranking*: days-to-harvest or readiness per block.

### The complexity ladder
Always start at the bottom rung and only climb when the data says the climb pays:

1. **Naive baseline** — "tomorrow = today" (persistence); "predict the mean." Costs nothing.
2. **Rule-based** — domain heuristics ("irrigate if soil moisture < threshold").
3. **Classical ML** — ARIMA/Prophet, XGBoost, logistic regression.
4. **Deep learning** — LSTM, CNN — only when there's data + signal to justify it.

:::note Each rung must beat the rung below on held-out data, or you don't climb. A neural net that ties the persistence baseline is a worse choice (more cost, more risk, no gain).
:::

### Splitting time-series correctly
You cannot shuffle time. Random train/test splits **leak the future into the past** and inflate scores. For VINE's time tracks you split **chronologically**: train on earlier data, validate on later — ideally **walk-forward** (Module 10).

### Leakage — the silent killer
**Leakage** is when information that wouldn't be available at prediction time sneaks into training. Examples:
- A feature computed using future rows (e.g. a centered rolling mean).
- Normalizing with statistics computed over the whole dataset (including test).
- The imputation problem from Module 3 — a filled gap that encodes the answer.

A leaky model looks brilliant in evaluation and fails in the field.

### Features vs labels
Be ruthless about *when* each value is known. A feature is only legal if it would exist at the moment you'd actually make the prediction. Write that timestamp down for every feature.

## In this repo
- \`*/baselines.py\` — every track ships baselines: [\`d2_irrigation/baselines.py\`](../src/vine/d2_irrigation/baselines.py), [\`d4_harvest/baselines.py\`](../src/vine/d4_harvest/baselines.py).
- [\`src/vine/d5_evaluation/\`](../src/vine/d5_evaluation/) — the metrics models are judged by.
- Project rule (CLAUDE.md): "No model ships without beating naive + rule-based baselines on held-out data."

## Hands-on
1. Read \`d2_irrigation/baselines.py\`. What is the persistence baseline doing, exactly?
2. For each track, write one sentence: what's the input, what's the label, when is each known?
3. Take the sensor data and design a *legal* chronological split. Mark the cutoff timestamp.
4. Find one feature idea that would leak (use future info) and rewrite it to be legal.
5. Argue, in two lines, when an LSTM is *not* worth it for D2.

## Self-test
- Name the four rungs of the complexity ladder with a VINE example each.
- Why is a random train/test split wrong for soil-moisture forecasting?
- Define leakage and give two concrete sources of it in this project.
- What's the bar a new model must clear before it "ships"?
- How do you decide whether to climb from classical to deep learning?

## References
- "Forecasting: Principles and Practice" (otexts.com/fpp3) · scikit-learn "Common pitfalls."
- This repo: ADR-0003 (track priority + ladder), the \`baselines.py\` files.
`,
        },
        {
          num: 10, slug: "evaluation", title: "Evaluation done right",
          hook: "The model isn't the deliverable — the *evidence* is. D5 is where every claim gets put on trial.",
          body: `
## Objectives
After this module you can:
- Pick the right metric for each task and explain its failure modes.
- Run walk-forward validation for time-series.
- Compare honestly against baselines and report uncertainty.
- Recognize an evaluation that's fooling you.

## Concepts

### Match the metric to the decision
| Task | Metric | Watch out for |
|------|--------|---------------|
| Soil-moisture forecast | **MAE / RMSE** | RMSE punishes big misses more; report both |
| Irrigation trigger (yes/no) | **precision / recall** | a missed dry-out (low recall) can cost a crop |
| Stress classification | precision/recall, **confusion matrix** | class imbalance hides poor minority-class performance |
| Days-to-harvest | MAE in **days** | report in units a grower understands |

A single accuracy number almost always hides the failure that matters. For triggers, ask: what's the cost of a false alarm vs a miss? Choose the metric that reflects that cost.

### Walk-forward validation
For time-series you simulate real deployment: train on \[t0…t1\], predict \[t1…t2\], then slide the window forward and repeat. This **respects time order** and gives many test windows instead of one lucky split.

~~~text
train ────────▶ | test |
      train ────────────▶ | test |
            train ──────────────▶ | test |
~~~

### Honest comparison
- Always report the **baseline's** score next to the model's. "RMSE 0.04" means nothing; "RMSE 0.04 vs persistence 0.07" means something.
- Report **spread**, not just a point estimate — variance across walk-forward windows, or a confidence interval.
- Use **held-out** data the model never saw during any tuning.

### Ways evaluation lies
- **Leakage** (Module 9) — inflated scores that won't reproduce.
- **Cherry-picking** the one good window or seed.
- **Metric mismatch** — optimizing RMSE when the grower cares about catching dry-outs.
- **No baseline** — impressive-sounding numbers with nothing to compare to.

:::warn "Quantitative evidence or it didn't happen." A model card with no baseline comparison and no held-out protocol is marketing, not evaluation.
:::

## In this repo
- [\`src/vine/d5_evaluation/metrics.py\`](../src/vine/d5_evaluation/metrics.py) — the shared metrics, written once for all tracks.
- \`*/baselines.py\` — what every model is measured against.
- The \`eval-reviewer\` agent exists to *adversarially* check your evaluation (leakage, split, honest metrics).

## Hands-on
1. Read \`d5_evaluation/metrics.py\`. Which metrics are implemented? For which task is each appropriate?
2. Sketch a walk-forward split over the 7-day sensor pull: list the train/test windows.
3. Take any forecast (even a dumb one) and report it *with* the persistence baseline side by side.
4. Build a confusion matrix by hand for a tiny stress/healthy example. Compute precision and recall.
5. Run the \`eval-reviewer\` agent mentally over a fake claim: "our LSTM gets RMSE 0.03." What three questions does it ask?

## Self-test
- Why report both MAE and RMSE for a forecast?
- For an irrigation trigger, is recall or precision more costly to get wrong, and why?
- What does walk-forward validation simulate that a single split cannot?
- Why is a metric meaningless without a baseline next to it?
- List three ways an evaluation can look great and still be wrong.

## References
- scikit-learn metrics guide · fpp3 ch. on evaluation.
- This repo: \`d5_evaluation/\`, the \`eval-reviewer\` agent, ADR-0003.
`,
        },
        {
          num: 11, slug: "reproducibility", title: "Reproducibility & tracking",
          hook: "A result you can't reproduce is a rumor. A run = config + seed + tracked data + logged metrics — every time.",
          body: `
## Objectives
After this module you can:
- Make a run fully determined by a YAML config + a seed.
- Log params and metrics to MLflow.
- Version data and models with DVC.
- Tie a model back to the exact code + data + config that made it.

## Concepts

### A run is a function of its inputs
The VINE law: **every run is determined by a YAML config + a seed.** No hyperparameters hardcoded in Python — they live in \`configs/\`. Same config + same seed → same result. This is what makes science out of training.

~~~python
from vine.common import seed_everything
seed_everything(cfg.seed)   # first line of any training run
~~~

### Configs as the source of truth
Hyperparameters, data windows, model choices — all in \`configs/<track>/<name>.yaml\`, validated by a pydantic model. To change an experiment you change the config, not the code. The config *is* the experiment.

### MLflow — the lab notebook
**MLflow** records each run: parameters, metrics, and artifacts. You get a searchable history — "which config got the best held-out MAE?" — instead of scrollback and memory. Artifacts (plots, model files) land in NRP S3.

### DVC — version control for data
Git is terrible at large binaries. **DVC** stores the bytes on the S3 remote and keeps a tiny \`.dvc\` pointer in git. So:
- \`git checkout <commit>\` + \`dvc pull\` → the **exact** data that commit used.
- A trained model traces to (code commit) + (DVC data version) + (config + seed).

:::warn Never \`git add\` a \`.tif\`, \`.pt\`, or large CSV — pre-commit blocks >1 MB. Use \`dvc add\`. Code in git, data in DVC.
:::

### Putting it together — the reproducibility chain
\`config.yaml\` + \`seed\` + \`dvc pull\` (exact data) + code commit → run → metrics + artifacts in MLflow. Anyone, later, on any machine, can rebuild it.

## In this repo
- [\`src/vine/common/seed.py\`](../src/vine/common/seed.py) — \`seed_everything()\`.
- [\`src/vine/common/config.py\`](../src/vine/common/config.py) — settings + config loading.
- \`configs/\` — YAML experiment configs, grouped \`d1_..d6_\`.
- DVC remote: \`s3://ihv-vine/dvc\`. The \`new-experiment\` command scaffolds a config + reminds you to log to MLflow.

## Hands-on
1. Read \`common/seed.py\`. What sources of randomness does it pin (python, numpy, torch)?
2. Open a config in \`configs/\`. Identify every value that would change the result if edited.
3. Run \`dvc status\` and \`dvc remote list\`. Confirm the remote points at NRP S3.
4. Trace the chain for the committed sensor snapshot: which git file is the DVC pointer, and where do the bytes live?
5. Use the \`new-experiment\` flow to scaffold a config (don't train) — note it refuses to start training, by design.

## Self-test
- What two things fully determine a VINE run?
- Why are hyperparameters banned from Python code?
- What does MLflow give you that a folder of result files does not?
- Why store data in DVC instead of git, and what's the size rule?
- Describe the full chain that lets someone reproduce a model six months later.

## References
- MLflow docs (mlflow.org) · DVC docs (dvc.org) · pydantic-settings.
- This repo: ADR-0004 (config), ADR-0005 (tracking), \`common/\`.
`,
        },
      ],
    },
    {
      title: "Part 4 — Building the deliverables",
      blurb: "Apply everything: build the pipeline and the three model tracks, prove them, and serve them.",
      modules: [
        {
          num: 12, slug: "d1-pipeline", title: "D1 — the data pipeline",
          hook: "One pipeline feeds all three tracks. Build it once, build it honest, and the models inherit clean inputs.",
          body: `
## Objectives
After this module you can:
- Describe D1's stages: ingest → indices → features → validation → block alignment.
- Run the working sensor path end to end.
- Explain the data-flow contracts every track relies on.
- Identify what's built vs still scoped.

## Concepts

### One pipeline, three tracks
Feature engineering and ingestion are written **once** in \`vine.d1_pipeline\`; D2/D3/D4 never re-implement them. This is the architectural keystone — change a feature in one place and every track sees it.

[[pipeline]]

### The stages
1. **Ingest** — pull sensors (InfluxDB/Flux), imagery (STAC/NextCloud), weather (Open-Meteo); snapshot to \`data/raw/\`, pin with DVC.
2. **Indices** — compute NDVI/NDRE from multispectral rasters (pure functions).
3. **Features** — regularize time-series, lag/rolling features, join weather.
4. **Validation** — flag gaps and bad values; never silently impute.
5. **Geo / block alignment** — clip rasters + predictions to vineyard-block polygons.

### Data-flow contracts (memorize these)
- **Sensors** → tidy frame indexed by UTC timestamp, on a regular grid, with explicit **gap flags**.
- **Imagery** → 7-channel patches \[R, G, B, NIR, RedEdge, NDVI, NDRE\] aligned to block polygons.
- **Predictions** → always reported **per vineyard block**, with confidence where available.

If every track honors these contracts, evaluation and serving are written once.

### What's real today
- ✅ **Sensor ingestion works** — \`vine ingest\` pulls live InfluxDB → Parquet → DVC → S3.
- ◐ Imagery scoped (9,295 captures inventoried; files behind maintenance; stitching TBD).
- ◐ Weather source confirmed (Open-Meteo); reader is the next build.
- ⚠️ Historical harvest records pending mentor.

Build on the confirmed sources; don't invent the missing ones.

## In this repo
- [\`src/vine/d1_pipeline/\`](../src/vine/d1_pipeline/) — \`influx.py\`, \`ingest.py\`, \`indices.py\`, \`imagery.py\`, \`geo.py\`, \`features.py\`, \`validation.py\`, \`ndp.py\`.
- [\`docs/STATE.md\`](../docs/STATE.md) — the live status of each input.

## Hands-on
1. Run \`uv run vine ingest --start=-7d\`; confirm Parquet per device in \`data/raw/sensors/\`.
2. Walk the module map above against the files in \`d1_pipeline/\` — which stages have code, which are stubs?
3. Take a raw sensor frame and apply: regularize → gap-flag (validation) → one lag feature. That's the D1 sensor path in miniature.
4. Read \`indices.py\` + \`geo.py\` and describe how a stitched raster would become "NDVI per block."
5. List, from \`STATE.md\`, the exact next build steps for D1 and which are blocked.

## Self-test
- Why is feature engineering centralized in D1 instead of per-track?
- State the three data-flow contracts from memory.
- Which D1 stage is fully working today, end to end?
- What must happen to the raw drone photos before block-level NDVI is possible?
- Which input is blocked, and which deliverable does that gate?

## References
- This repo: \`d1_pipeline/\`, \`docs/architecture.md\`, \`docs/data/index.md\`, STATE.md.
- Modules 2–4 and 8 (their concepts converge here).
`,
        },
        {
          num: 13, slug: "d2-irrigation", title: "D2 — irrigation forecasting",
          hook: "When will soil moisture drop too low? Start with 'tomorrow looks like today' and only climb when the data earns it.",
          body: `
## Objectives
After this module you can:
- Frame irrigation as soil-moisture forecasting + a decision layer.
- Build the baseline and classical/deep forecasters.
- Turn a forecast into an irrigation trigger and evaluate it on the right metric.

## Concepts

### The task
Two parts:
1. **Forecast** soil moisture forward (a regression over time, per sensor/block).
2. **Decide** — convert the forecast into "irrigate / don't" via a threshold or rule.

### The ladder for D2
- **Naive**: persistence — next value = last value. Surprisingly hard to beat short-horizon.
- **Rule-based**: irrigate when forecast crosses a moisture threshold.
- **Classical**: **ARIMA / Prophet** — model trend + daily/seasonal cycles. Prophet is robust to gaps and easy to start; ARIMA needs stationarity (differencing).
- **Deep**: **LSTM** — learns nonlinear multi-sensor dependencies; worth it only with enough clean history.

### Features (all D1 outputs)
Lagged soil moisture, rolling means, temperature/humidity, and crucially **weather + ET₀** (atmospheric thirst from Module 8). ET₀ is a strong driver of how fast soil dries.

### Evaluating it
- Forecast quality: **MAE / RMSE** on a **walk-forward** split.
- Trigger quality: **precision / recall** — a missed dry-out (low recall) is the expensive error. Pick the threshold with that cost in mind.

:::note Iron Horse already cut water ~10% with data-driven irrigation. The bar isn't "be clever" — it's "beat persistence and the threshold rule on held-out data, in days a grower trusts."
:::

## In this repo
- [\`src/vine/d2_irrigation/baselines.py\`](../src/vine/d2_irrigation/baselines.py) — persistence + rule baselines.
- [\`src/vine/d2_irrigation/config.py\`](../src/vine/d2_irrigation/config.py) — the track's pydantic config.
- Features come from \`d1_pipeline/features.py\`; metrics from \`d5_evaluation\`.

## Hands-on
1. Read \`d2_irrigation/baselines.py\`. Implement (on paper) how you'd score persistence on a walk-forward split.
2. Scaffold an experiment config for a Prophet run with the \`new-experiment\` flow (don't train).
3. List the features you'd feed the model — mark which come from sensors, which from weather.
4. Choose an irrigation threshold and define precision/recall for the trigger. Which matters more here?
5. Write the one-sentence hypothesis a deep model must beat to justify itself.

## Self-test
- What are the two parts of the D2 task?
- Why is persistence a strong baseline at short horizons?
- What does ET₀ contribute to a soil-moisture forecast?
- Which metric governs the *trigger*, and which error is costliest?
- State the bar D2 must clear to ship.

## References
- Prophet docs · statsmodels ARIMA · fpp3.
- This repo: \`d2_irrigation/\`, ADR-0003, ADR-0009 (weather).
`,
        },
        {
          num: 14, slug: "d3-vision", title: "D3 — plant-health computer vision",
          hook: "The drone sees what your eyes can't. D3 turns multispectral pixels into 'which blocks are stressed.'",
          body: `
## Objectives
After this module you can:
- Frame plant-health as multispectral image classification.
- Assemble the 7-channel input the architecture consumes.
- Choose a backbone (ResNet/EfficientNet) and handle scarce labels.
- Evaluate classification honestly and report per block.

## Concepts

### The task
Classify vineyard blocks (or image patches) as **healthy / stressed / pest-damaged** from multispectral imagery — and ideally localize where. Output, per the project contract, is **per block**.

### The input: 7 channels
From Module 4 + D1, each patch is \[R, G, B, NIR, RedEdge, NDVI, NDRE\] aligned to block polygons. The index channels (NDVI/NDRE) hand the network the plant-health signal directly, so it doesn't have to rediscover it.

### Architectures
- **CNN backbones** — **ResNet / EfficientNet**, adapted to 7 input channels (not the default 3). Start from pretrained RGB weights, extend the first conv to the extra bands.
- **Transfer learning** is essential because labels are scarce.

### The hard part: labels
Labeled stress/pest imagery may not exist yet (an open mentor question). Strategies when labels are thin:
- **Weak/index-based labels** — threshold NDVI/NDRE to bootstrap "low-vigor" regions.
- **Self/semi-supervised** pretraining on the unlabeled captures.
- Be honest in scope: without labels, D3 may start as **anomaly detection** ("which blocks look unlike the rest?") rather than supervised pest ID.

### Evaluation
- **Precision / recall / confusion matrix**, not bare accuracy — classes are imbalanced (most of the field is healthy).
- Beat a trivial baseline ("everything healthy" or "threshold NDVI") on held-out blocks/flights.
- Mind the **flight timing**: useful growing-season flights (Aug pre-harvest, Oct harvest) are few; don't test on winter dormancy and claim growing-season skill.

:::warn Heavy libs (torch, rasterio) are lazy-imported inside functions so the core stays light. Training runs on an NRP GPU pod, never in CI.
:::

## In this repo
- [\`src/vine/d3_vision/model.py\`](../src/vine/d3_vision/model.py) — the model definition.
- [\`src/vine/d3_vision/config.py\`](../src/vine/d3_vision/config.py) — architecture/training config.
- Inputs from \`d1_pipeline\` (indices + geo); batch inference manifest in \`k8s/d6_serving/vision-batch-job.yaml\`.

## Hands-on
1. Read \`d3_vision/model.py\`. How is the first layer adapted for 7 channels instead of 3?
2. Build the channel stack for one patch on paper: list all 7 and where each comes from.
3. Propose a weak-label scheme from NDVI/NDRE thresholds to bootstrap training without hand labels.
4. Given class imbalance, pick the metric you'd optimize and the baseline you must beat.
5. From the imagery inventory, choose which flights are valid for a growing-season test and justify it.

## Self-test
- Why feed NDVI/NDRE as channels instead of letting the CNN learn them?
- Why does a 7-channel input require modifying a standard ResNet?
- What do you do when labeled pest data doesn't exist?
- Why is accuracy a misleading metric here?
- Where does D3 training run, and why not in CI?

## References
- torchvision models · "Transfer learning" tutorials · remote-sensing CV papers.
- This repo: \`d3_vision/\`, the imagery datasheet, ADR-0003.
`,
        },
        {
          num: 15, slug: "d4-harvest", title: "D4 — harvest timing",
          hook: "When is each block ready? The hardest track — because the labels (actual harvest dates) may not exist yet.",
          body: `
## Objectives
After this module you can:
- Frame harvest timing as per-block readiness / days-to-harvest.
- Combine sensor, weather, and imagery features for it.
- Handle sparse labels and know when to descope to exploratory.

## Concepts

### The task
Predict, **per block**, either days-to-harvest or a readiness score. This drives picking decisions — high stakes, but **label-poor**.

### Features
A fusion of everything D1 produces:
- **Weather accumulation** — especially **growing degree days (GDD)**, the heat-sum that paces ripening.
- **Sensor** trends (soil moisture, temperature).
- **Imagery** — canopy vigor (NDVI/NDRE) over the season.

### The label problem (the crux)
Harvest dates / yields / irrigation logs are **historical records not found in InfluxDB or NDP** — an open mentor question. Without them you cannot do supervised days-to-harvest.

Honest paths:
- **If labels arrive**: XGBoost (tabular, few samples, strong baseline) or an LSTM over the season.
- **If they don't**: descope to **exploratory** — GDD-based heuristics, ripeness proxies from imagery, and an analysis framework ready to train the moment labels exist.

:::note This is why the project ranks D4 third (ADR-0003): most impactful per pick, but sparse labels make it the riskiest. Plan for the exploratory fallback up front.
:::

### Evaluation
- If supervised: **MAE in days** (a unit growers feel), walk-forward, vs a GDD/calendar baseline.
- If exploratory: clearly labeled as such — no inflated claims without labels.

## In this repo
- [\`src/vine/d4_harvest/baselines.py\`](../src/vine/d4_harvest/baselines.py) — calendar/GDD baselines.
- [\`src/vine/d4_harvest/config.py\`](../src/vine/d4_harvest/config.py) — track config.
- Open question #1 in [\`docs/STATE.md\`](../docs/STATE.md): do historical harvest records exist, and where?

## Hands-on
1. Read \`d4_harvest/baselines.py\`. What naive timing rule does it encode?
2. Define growing degree days and sketch how you'd compute GDD from the weather feed.
3. List the features you'd fuse for D4 and tag each by source (sensor/weather/imagery).
4. Write the two-branch plan: what D4 becomes *with* labels vs *without*.
5. Draft the exact question to send the mentor about historical records (see STATE.md open questions).

## Self-test
- What does D4 predict, and at what granularity?
- Why is D4 the riskiest track despite high impact?
- What is GDD and why does it pace harvest timing?
- What's the principled fallback when labels are missing?
- What metric and baseline govern the supervised version?

## References
- Viticulture GDD references · XGBoost docs · fpp3.
- This repo: \`d4_harvest/\`, ADR-0003, STATE.md open questions.
`,
        },
        {
          num: 16, slug: "d5-evaluation", title: "D5 — the evaluation report",
          hook: "D5 is the courtroom. Every model from D2–D4 stands trial against its baseline, on held-out data, with the receipts.",
          body: `
## Objectives
After this module you can:
- Assemble a cross-track evaluation with shared metrics.
- Run walk-forward / held-out protocols consistently.
- Write a model card that survives an adversarial review.

## Concepts

### Why a dedicated deliverable
Evaluation written per-track drifts and flatters. D5 centralizes **metrics, validation protocol, and baseline comparison** so every track is judged the same honest way. It's the enforcement arm of "evaluation-driven."

### What goes in the report
- Per track: the **baseline**, the **best model**, the **delta**, on **held-out** data.
- The **protocol** (walk-forward windows, the split timestamp, the seed).
- **Ablations** — which features/choices actually mattered.
- **Limitations** — where the model fails, honestly.

### Model cards
Each shipped model gets a card: training data + window, intended use, the baseline it beats and **by how much** (pulled from MLflow), evaluation protocol, limitations, and operational caveats (e.g. "do not use to override grower judgment on frost nights"). Missing numbers are written "TBD — pending run," never invented.

### The adversary
The \`eval-reviewer\` agent (and any good reviewer) tries to **refute** your result: Is there leakage? Is the split walk-forward? Right metric? Pinned to config + seed + MLflow? If your evaluation can't survive that, it isn't done.

:::warn The deliverable is the evidence, not the model. A great model with a sloppy eval is a failed D5.
:::

## In this repo
- [\`src/vine/d5_evaluation/metrics.py\`](../src/vine/d5_evaluation/metrics.py) — shared metrics.
- \`docs/models/_template.md\` — the model-card template; the \`model-card\` command fills it from MLflow.
- The \`eval-reviewer\` agent — adversarial check before you claim a win.

## Hands-on
1. Read \`d5_evaluation/metrics.py\` and list which tasks it already covers.
2. Open \`docs/models/_template.md\`. Which sections force honesty (baseline delta, limitations, caveats)?
3. Draft a model card for a hypothetical D2 Prophet model — use "TBD — pending run" wherever you lack a number.
4. Run the \`eval-reviewer\` checklist against that card. What would it flag?
5. Define the held-out protocol you'd use across all three tracks so results are comparable.

## Self-test
- Why centralize evaluation instead of letting each track self-report?
- What four things must a model card state about the baseline comparison?
- What does the \`eval-reviewer\` try to do to your result, and why is that good?
- When is it correct to write "TBD — pending run"?
- Why is "the evidence, not the model" the right framing for D5?

## References
- Google "Model Cards" paper · scikit-learn metrics.
- This repo: \`d5_evaluation/\`, \`docs/models/\`, the \`eval-reviewer\` agent, Module 10.
`,
        },
        {
          num: 17, slug: "d6-serving", title: "D6 — serving on NRP",
          hook: "A model nobody can call is a paperweight. D6 wraps it in an API, containers it, and runs it on the cluster.",
          body: `
## Objectives
After this module you can:
- Wrap a model in a FastAPI inference service.
- Containerize it and push to the NRP registry.
- Deploy it as a K8s Deployment + Service in namespace \`ihv\`.
- Expose per-block predictions to the dashboard and digital twin.

## Concepts

### The shape of serving
\`FastAPI\` app → \`Docker\` image → \`Kubernetes\` Deployment + Service on NRP. This is Modules 5–7 applied to a trained model.

### FastAPI
A lightweight Python web framework. You define endpoints that load a model and return predictions:

~~~python
@app.get("/healthz")
def healthz(): return {"ok": True}

@app.post("/irrigation")
def irrigation(req: BlockRequest) -> BlockForecast:
    # load features, run model, return per-block forecast + confidence
    ...
~~~

Endpoints mirror the tracks: \`/irrigation\`, \`/health\`, \`/harvest\`, plus \`/healthz\` for K8s liveness probes.

### Containerize + register
Build the serving image (\`--extra serve\`), tag it, push to \`gitlab-registry.nrp-nautilus.io\`. The cluster pulls it to run.

### Deploy on NRP
- A **Deployment** keeps the API pod(s) alive and handles rollouts.
- A **Service** gives a stable address and load-balances.
- \`/healthz\` backs the **liveness/readiness probes** so K8s restarts a wedged pod.
- Batch jobs (e.g. nightly vision inference) run as **Jobs**, not the always-on Deployment.

### The contract D6 must honor
Predictions are **per vineyard block**, with confidence where the model supports it — because Track 3 (digital twin) and Track 4 (dashboard) consume this API. The output contract from D1 carries all the way through.

:::note Serving needs only CPU for the lightweight models; GPU is for training. Right-size the pod's resource requests (Module 7 etiquette).
:::

## In this repo
- [\`src/vine/d6_serving/app.py\`](../src/vine/d6_serving/app.py) — the FastAPI app + endpoints.
- [\`docker/\`](../docker/) — serving image build.
- [\`k8s/d6_serving/\`](../k8s/d6_serving/) — Deployment, Service, batch Job (namespace \`ihv\`).
- \`make serve\` runs the API locally.

## Hands-on
1. Run \`make serve\` and hit \`/healthz\` in a browser/curl. Confirm the app boots.
2. Read \`d6_serving/app.py\`. Which endpoints exist, and what shape do they return?
3. Read \`k8s/d6_serving/irrigation-deployment.yaml\` + \`-service.yaml\`. Trace a request from the Service to a pod.
4. Map each endpoint to its model track and to the per-block output contract.
5. Explain why the vision job is a K8s \`Job\` while irrigation is a \`Deployment\`.

## Self-test
- What three layers turn a trained model into a running NRP service?
- What is \`/healthz\` for, and which K8s feature uses it?
- Why per-block outputs with confidence — who consumes them?
- Why CPU for serving but GPU for training?
- When do you use a Job vs a Deployment for inference?

## References
- FastAPI docs (fastapi.tiangolo.com) · kubernetes.io probes.
- This repo: \`d6_serving/\`, \`docker/\`, \`k8s/d6_serving/\`, Modules 5–7.
`,
        },
      ],
    },
    {
      title: "Part 5 — Capstone",
      blurb: "Put it all together end to end, and learn the workflow that keeps a long project on the rails.",
      modules: [
        {
          num: 18, slug: "capstone", title: "Capstone & working across sessions",
          hook: "You've learned every piece. Now build a vertical slice end to end — and learn the discipline that keeps a 13-week project from drifting.",
          body: `
## Objectives
After this module you can:
- Build one vertical slice from raw data to a served, evaluated prediction.
- Work the way a GSoC contributor must: small slices, evidence, documentation.
- Keep state across sessions so no context is ever lost.

## Concepts

### The capstone: a vertical slice
Don't boil the ocean — ship **one thin slice all the way through**, end to end:

1. **Ingest** a week of sensors (\`vine ingest\`) → Parquet → DVC.
2. **Feature**-engineer the D1 sensor path (regularize → gap-flag → lags + weather).
3. **Model** D2 with the persistence baseline + one classical forecaster.
4. **Evaluate** walk-forward vs baseline; log to MLflow.
5. **Serve** it behind \`/irrigation\` with \`make serve\`.
6. **Document** it: a model card + a devlog entry.

That slice exercises every module. Everything after is widening it (more tracks, deeper models, imagery).

### How we work (the rules that matter)
- **Explore → plan → implement.** For anything touching >1 file, plan first.
- **Evaluation-driven.** No model ships without beating baselines on held-out data.
- **Reproducible by construction.** Config + seed + DVC + MLflow, every run.
- **Small, shippable slices.** Each 2-week phase ends with a working, testable component — no big-bang integration.
- **Verify, then claim.** Run the check and show output before saying it works.

### Keeping state across sessions
A long project outlives any single work session. VINE keeps durable state so you (or a teammate, or an AI assistant) can always resume cold:

| Artifact | Holds | When to update |
|----------|-------|----------------|
| \`docs/STATE.md\` | current state, verified endpoints, open questions, next actions | end of any session that changes status |
| \`CLAUDE.md\` | lean project memory; points new sessions to STATE.md | rarely; keep it short |
| \`docs/adr/\` | **decisions** + their rationale | whenever you choose/change an approach |
| \`docs/devlog/\` | **narrative** progress (GSoC bi-weekly) | every two weeks |

:::note The rule: when status changes (input verified, deliverable advanced, decision made), update STATE.md and commit it. Decisions become ADRs. Narrative becomes devlog posts. Future-you starts every session by reading STATE.md.
:::

### Secrets, always
Tokens live in \`.env\` (gitignored) — never in code, never committed. Data in DVC, code in git. This never relaxes.

## In this repo
- [\`docs/STATE.md\`](../docs/STATE.md) — the resume-here file. Read it first, every session.
- [\`docs/adr/\`](../docs/adr/index.md) — the decision log (0001–0009 so far).
- [\`docs/devlog/\`](../docs/devlog/index.md) — the narrative log; \`devlog\` command drafts a post.
- \`CLAUDE.md\` — how the repo and the AI assistant stay aligned.

## Hands-on
1. Do the vertical slice, steps 1–6 above. Stop at the first place you lack data and note it (don't invent).
2. After it works, run \`make check\` — green before you claim done.
3. Write a model card for your D2 slice (use the \`model-card\` flow) with real or "TBD" numbers.
4. Update \`docs/STATE.md\`: move the deliverable status, log what you did, add any new open question.
5. Draft a devlog entry (\`devlog\` flow) describing the slice honestly — including what didn't work.

## Self-test
- Why build a vertical slice instead of finishing D1 fully before touching D2?
- State the five "how we work" rules in your own words.
- Which file do you read first when resuming, and what does it contain?
- Where do decisions go vs narrative progress?
- What's the one rule about secrets that never relaxes?

## References
- This repo: \`docs/STATE.md\`, \`CLAUDE.md\`, \`docs/adr/\`, \`docs/devlog/\`, the proposal timeline.
- Every prior module — this is where they converge.

---

🎉 **That's the course.** Mark this complete to finish, then go build the slice for real. The repo is waiting.
`,
        },
      ],
    },
  ],
};
