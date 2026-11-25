# Experiments — improving the 3D build

A bench to test changes to the reconstruction on a short excerpt, keep every
run, and compare them. Nothing here changes the production pipeline
(`scripts/`): a change graduates there only once it holds on at least two
transects (see the project's `CLAUDE.md`).

## Running

```bash
cd playground/experiments
./run.sh tab-south baseline                   # one variant on tab-south, 0-20 s, 3 fps
SEED=1 ./run.sh tab-south contrast+control    # same, with invisible noise (see below)
START=60 DURATION=20 ./run.sh site3-transect3 contrast
../vendor/.venv-lingbot/bin/python -I summarize.py ../out/experiments/tab-south-0s-20s
```

Each run keeps everything in `out/experiments/<key>-<start>s-<duration>s/<run>/`
(ignored by git): input frames, `recon.npz`, the exported `web/cloud.ply` and
`path.json` (default `export-web.py` settings), `metrics.json`, `render.png`
(cloud from above and from the side), `sample.jpg` (middle input frame) and
`log.txt`. Results worth keeping go to `results/`: tables and metrics are
versioned, images (comparison sheets) stay local only.

To look at two runs side by side in 3D, with one shared camera:

```bash
cd playground && python3 -m http.server 8000
# http://localhost:8000/experiments/compare.html?set=tab-south-0s-20s
```

Pre-processing needs its own Python env (PyTorch, transformers), kept apart
from LingBot-Map's:

```bash
cd playground/vendor
python3.10 -m venv .venv-enhance
.venv-enhance/bin/pip install torch torchvision transformers opencv-python scipy pillow
git clone --depth 1 https://github.com/xahidbuffon/FUnIE-GAN.git
```

The hybrid bench (photogrammetry fixing LingBot's camera path, see
`results/hybrid.md`) needs a third env, with COLMAP and learned feature
matching:

```bash
cd playground/vendor
python3.10 -m venv .venv-sfm
.venv-sfm/bin/pip install pycolmap torch opencv-python-headless scipy matplotlib \
  "git+https://github.com/cvg/LightGlue.git"
cd ../experiments
START=90 DURATION=30 ./hybrid-run.sh site3-transect2-north   # LingBot, SfM, hybrid, scores
```

## Metrics

All scale-free (`metrics.py`). Coverage: `confident` (pixels above the export's
confidence threshold) and `kept` (after the export's filters). Geometry:
`depthError2` / `depthError8`, how much the model's raw depth for frame k
disagrees with frame k+2 / k+8 once reprojected (before the export's scale
correction); `jitter`, how jerky the camera path is; `thickness`, how thick the
cloud's surfaces are, in voxels (doubled layers raise it).

**Noise floor.** LingBot-Map reacts strongly to invisible input changes: adding
±1 grey level of random noise (`control`) moves `confident` by 4 points,
`depthError2` by 1.6 points and `depthError8` from 9 % to 22 %. A single run
therefore proves nothing; a variant counts only when it leaves the band set by
`baseline` and `control` over several seeds (`+control`, `SEED=n`).
`depthError8` is too noisy to rank variants on a 20 s excerpt.

## Round 1 — AI / image pre-processing only (tab-south, 0-20 s)

Question: can editing the frames before LingBot-Map (no change to the model or
the export) make the reconstruction better? 60 frames at 3 fps, decoded at
1036 px (twice the model's input) for every variant.

| Variant | What it does |
| --- | --- |
| `baseline` | No filter. |
| `control` | ±1 grey level of seeded noise, invisible: the noise floor. |
| `sharpest` | For each output frame, the sharpest source frame (Laplacian variance) within ±0.1 s. |
| `denoise` | Non-local means, per frame. |
| `temporal` | Motion-compensated temporal median: source frames within ±0.05 s warped onto the frame with dense optical flow (DIS), per-pixel median. Targets noise, particles and caustics. |
| `clahe` | Gray-world white balance + CLAHE on lightness: the classical enhancement reported best for SfM ([Vrochidis et al., ISPRS 2025](https://isprs-archives.copernicus.org/articles/XLVIII-2-W10-2025/317/2025/)). |
| `contrast` | CLAHE on lightness only, hue untouched. |
| `funie` | [FUnIE-GAN](https://github.com/xahidbuffon/FUnIE-GAN), a GAN trained to restore underwater colour and contrast. |
| `fish` | Fish detected with OWLv2 (open-vocabulary, "a photo of a fish"), boxes inpainted. |

| Run | Confident | Kept | Depth err. k+2 | Depth err. k+8 | Jitter | Thickness | Points |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline` | 50.9 % | 59.4 % | 6.8 % | 9.2 % | 0.75 | 0.47 | 899,322 |
| `control` | 47.0 % | 57.3 % | 5.2 % | 11.2 % | 0.80 | 0.47 | 901,366 |
| `control-seed1` | 47.5 % | 57.3 % | 5.6 % | 15.4 % | 0.79 | 0.47 | 888,923 |
| `control-seed2` | 47.4 % | 57.1 % | 5.8 % | 22.3 % | 0.69 | 0.47 | 897,174 |
| `sharpest` | 52.0 % | 59.7 % | 7.1 % | 19.2 % | 0.81 | 0.48 | 874,345 |
| `denoise` | 25.0 % | 43.5 % | 4.8 % | n/a | 0.69 | 0.46 | 986,436 |
| `temporal` | 9.5 % | 27.2 % | 5.4 % | n/a | 0.64 | 0.40 | 796,041 |
| `clahe` | 78.6 % | 78.4 % | 5.2 % | 22.4 % | 0.52 | 0.48 | 1,697,547 |
| `contrast` | 62.2 % | 65.8 % | 5.1 % | 10.4 % | 0.89 | 0.50 | 1,024,912 |
| `contrast+control-seed1` | 62.1 % | 65.9 % | 5.0 % | 9.9 % | 0.89 | 0.50 | 1,038,955 |
| `funie` | 6.5 % | 21.5 % | 6.0 % | n/a | 1.29 | 0.39 | 642,313 |
| `fish` | 50.5 % | 59.4 % | 5.5 % | 8.2 % | 0.65 | 0.47 | 908,451 |
| `fish+control-seed1` | 47.5 % | 57.5 % | 5.5 % | 13.6 % | 0.70 | 0.47 | 918,784 |
| `fish+control-seed2` | 47.0 % | 57.3 % | 6.0 % | 13.1 % | 0.71 | 0.47 | 922,213 |

`n/a`: too few confident pixels overlap 8 frames apart to measure.
Comparison sheets (local only, not versioned) in `results/tab-south-0s-20s/`:
input frames per variant (`inputs.jpg`), clouds from above (`renders-all.jpg`),
`contrast` against the noise band (`renders-contrast.jpg`) and the fish
detections before / after inpainting (`fish-detections.jpg`).

### Findings

- **Smoothing the image hurts.** `denoise`, `temporal` and `funie` all remove
  fine texture, and LingBot-Map's confidence collapses (25 %, 10 %, 7 % against
  ~50 %). At the model's 518 px input, the 4K sensor noise is already averaged
  away; there is nothing left to denoise, only detail to lose. FUnIE-GAN
  also paints a strong orange cast with artefacts: this footage is far from
  its training data.
- **White balance breaks the water cue.** `clahe` looks like a big win (79 %
  confident) but the extra confidence is on the water: once the blue cast is
  gone, the export's open-water filter no longer recognises it, and the haze
  comes out as streaky surfaces (`renders-all.jpg`). Same lesson as the
  colour-correction lead in `playground/README.md`: the blue haze is
  information for the model.
- **Local contrast on lightness only is the one consistent gain.**
  `contrast` keeps 62 % confident pixels on both seeds (band 47-51 %), with
  `depthError2` at the good end of the band (5.0-5.1 %), 15 % more points, and a
  straighter, more continuous seabed in side view. Costs: a jerkier camera path
  (`jitter` 0.89 against 0.69-0.80) and slightly thicker surfaces (0.50 against
  0.47). Promising, not yet proven.
- **Fish removal works but does not show here.** OWLv2 finds real fish, even
  small ones over the reef, plus a few bubbles and one coral branch
  (`fish-detections.jpg`). But fish cover 0.09 % of the pixels in this excerpt:
  all metrics stay within the noise band. Telea inpainting also leaves blurry
  patches on the reef. Worth re-testing on a fish-rich excerpt, filling holes
  from neighbouring frames rather than inventing pixels (or masking them in
  the export instead).
- **Picking the sharpest frame does nothing.** This 4K 60 fps footage in
  sunlit shallow water has little motion blur, and the uneven spacing between
  picked frames slightly worsens consistency.

### Next steps

1. Validate `contrast` on a second transect (a NOAA one, deeper and bluer),
   with 2-3 seeds, and look at both clouds in `compare.html`.
2. Fish: pick a fish-rich excerpt; compare inpainting with masking the fish
   pixels out of the export (no invented texture).
3. Round 2: changes beyond pre-processing (model input size, frame rate,
   export-side filtering).
