# Model card: plant-health/cnn-pseudolabel

> Pipeline-validation run. The labels are derived from the imagery itself, so
> this run demonstrates that the D3 training path works end to end. It does not
> demonstrate that plant stress can be detected.

## Model details

- **Track / deliverable:** Plant health (D3)
- **Architecture:** ImageNet-pretrained ResNet-50 with the stem conv replaced by a 2-channel conv and the classifier head replaced by 3 outputs. The adapter (`vine.d3_vision.model.adapt_stem`) is generic over channel count: kernels for channels 0 to 2 are copied from the pretrained RGB kernels (or as many as the run has), and any remaining channels are Kaiming-normal initialized.
- **Version / run:** MLflow experiment `d3_vision`, run name `cnn-pseudolabel-2026-06-01`. Checkpoint at `models/d3_vision/cnn_pseudolabel.pt` (gitignored, not pinned with DVC).
- **Config:** `configs/d3_vision/resnet50.yaml`
- **Runner:** `scripts/d3_pseudolabel_train.py`
- **Author & date:** Sohan Shingade, 2026-08-05

## Intended use

- **Primary use:** Validating the D3 training path (patch dataset, channel adapter, block-level split, training and evaluation loop) and providing a warm-start checkpoint for the first run on field-verified labels.
- **Users:** VINE researchers only.
- **Out of scope:** Every operational use. This checkpoint must not be used to call a block stressed, to trigger inspection, or to inform treatment. The label-free NDVI/NDRE screening in `docs/models/plant-health/stress-screening.md` remains the only D3 artifact intended for field review, and it is a review queue rather than a diagnosis.

## Training data

No field-verified plant-stress labels exist (see the open mentor questions in `docs/STATE.md`). The proposal's stated fallback for that case is to start from NDVI thresholding as pseudo-labels and refine later with manual annotations. This run executes that fallback.

**Channel set actually used: NDVI and NDRE (2 channels).** The proposal's target input is 7 channels (R,G,B,NIR,RedEdge,NDVI,NDRE). The 2026-06-01 whole-vineyard products downloaded to `data/raw/imagery/rasters/` are two single-band Pix4DFields index rasters, `NDVI.data.tif` and `NDRE.data.tif`, each `float32`, 35,613 by 40,828 pixels at 4.42 cm ground sampling distance in EPSG:32610. Neither carries a separate red, green, blue, NIR, or red-edge band. The matching 10.2 GB `Orthomosaic.data.tif` exists on the NextCloud `GIS/` share but was not downloaded, so the RGB channels were cut from this run rather than fabricated. The channel adapter and the config schema both remain generic, so adding the five missing channels is a config change and a download, not a code change.

**Patches.** Block interiors come from the 39 polygons in `IHV-2026-05-26.kmz` via `vine.d1_pipeline.geo.load_blocks_kmz`. Each block is tiled on a non-overlapping 256 by 256 pixel grid (about 11.3 m on the ground), a tile is kept only if the polygon fully contains it, and each tile is read windowed with rasterio, so the two roughly 4 GB rasters are never loaded whole. Tiles below 98% valid pixels after nodata handling are rejected, and at most 32 tiles per block are kept using a seeded shuffle. Result: **1,209 patches across all 39 blocks** (9 blocks contributed fewer than 32 because their interiors admit fewer full tiles; the smallest contributed 9).

**Pseudo-labels.** Each patch is labelled by which tertile its mean NDVI falls into: class 0 `stressed`, class 1 `mid`, class 2 `healthy`. The quantile boundaries are recorded in the config (`label_quantiles: [1/3, 2/3]`) and the resulting NDVI cut values are computed on the training patches only, then applied unchanged to validation, so the boundaries carry no validation information.

**Split.** By block, never by patch. Blocks are partitioned with a seeded permutation at `val_block_fraction: 0.25`, so every validation patch sits inside a block the model never saw.

**Gaps.** Nodata (`−10000`) and non-finite pixels are masked, counted, and zeroed after the validity gate. Nothing is interpolated.

## Evaluation

All numbers below come from the training run of 2026-08-05 (MLflow run `cnn-pseudolabel-2026-06-01`, run ID `bda91ff80de54b1bb6b4f98f304ff2d8`). The split placed 905 patches from 29 blocks in training and 304 patches from 10 held-out blocks (C1, C3, C5, H6, J1, M, N, O, P7, Triangle A) in validation. The training-set NDVI tertile boundaries were 0.5186 and 0.5923. The run took 19.3 minutes over 8 epochs on CPU.

**Held-out block results (final epoch).** Validation accuracy **0.806**, macro F1 **0.800**. Validation accuracy over the epochs ranged from 0.648 to 0.895; the final epoch ended at 0.806 rather than the peak, and the checkpoint is the final-epoch model. Per class:

| class    | support | accuracy | precision | F1    |
|----------|---------|----------|-----------|-------|
| stressed | 148     | 0.764    | 1.000     | 0.866 |
| mid      | 74      | 0.865    | 0.566     | 0.684 |
| healthy  | 82      | 0.829    | 0.872     | 0.850 |

Confusion matrix (rows are pseudo-labels, columns are predictions):

| pseudo-label | pred stressed | pred mid | pred healthy |
|--------------|---------------|----------|--------------|
| stressed     | 113           | 35       | 0            |
| mid          | 0             | 64       | 10           |
| healthy      | 0             | 14       | 68           |

Every confusion is with the adjacent tertile; the model never swapped the stressed and healthy ends.

**Baseline comparison.** The trivial baseline applies the training-set NDVI tertile rule directly to each validation patch's mean NDVI. Its accuracy is **1.000**, exactly, by construction: it is the rule that generated the labels, so it is the ceiling for this task rather than a bar the CNN is expected to clear. The CNN's 0.806 against a perfectly reproducible target measures how well the fine-tuning loop recovers a known function of its input from 905 examples in 8 CPU epochs. It says nothing about detecting stress.

## Limitations & caveats

- **The task is close to circular.** The label is a function of patch mean NDVI, and NDVI is input channel 0. A model that learns to spatially average one input channel scores near the ceiling. The accuracy figure above is a statement about the optimization loop, not about vine physiology.
- **The pseudo-labels are not stress.** Low NDVI can reflect phenology, soil and background exposure, shadows, pruning, irrigation, sensor calibration, or Pix4D processing. Calling the low tertile `stressed` is a naming convention for the weak label, not a claim about the vines.
- **One acquisition, one date.** Every patch comes from 2026-06-01. Nothing here establishes stability across dates, seasons, or flight conditions.
- **Two channels, not seven.** The RGB, NIR, and red-edge channels the proposal specifies were unavailable locally and are absent from this run.
- **Tertiles are an arbitrary partition.** The class boundaries are population quantiles of one flight, so they move with the acquisition and carry no agronomic threshold.
- **CPU-scale run.** A few hundred training patches over a handful of epochs is a smoke test of the pipeline, not a converged fine-tune.

## Ethical & operational considerations

The failure mode to guard against here is presentation, not prediction: a checkpoint named "plant-stress classifier" reporting high accuracy invites the reader to conclude that stress detection works. It does not, and the registry row, this card, and the runner's own console output all say so explicitly. No block should be inspected, irrigated, treated, or characterized on the basis of this model. When field-verified labels arrive, this checkpoint is a warm start and the pseudo-label accuracy is not a baseline to beat, because it measures agreement with a rule rather than agreement with the field.
