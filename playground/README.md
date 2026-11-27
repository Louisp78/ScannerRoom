# Playground — from transect video to point cloud

How a diver's transect video becomes the point cloud and trajectory shown in the
3D viewer, and why each step is there. Nothing here is imported by the Vue app:
the only link with it is the folder exported to `public/transects/<key>/`, which
the viewer loads on the `/transects/<key>` route.

To add and publish a transect, see [CONTRIBUTING.md](../CONTRIBUTING.md#add-a-transect).

## Data source

[NOAA NCEI, accession 0172858](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.nodc:0172858) —
*Video transects of coral reefs on the west coast of the island of Hawaii*
(February 2017). 27 MP4 videos filmed by divers along marked transects, on 7
sites between Kona and North Kohala, 0.2 to 1.7 GB each.

Why this source: it is exactly the capture gesture the product targets (a diver
swimming along a coral coast, camera facing the reef), the data is public (US
government work, no restrictions), and each file can be downloaded on its own
over HTTP, without an account.

Each site has a precise position (degrees and decimal minutes, ~2 m) in the
accession's `Hawaii Fish Video Metadata.docx`, next to the site folders; the
transects of a site share it. `01-fetch-transect.sh --list` prints the catalog
used here: 12 transects over 6 sites, picked from contact sheets of the 27 files
for clear water and full swims (10 to 12 min each, ~100 m and more along the
tape). Site 5 is left out: murky, and its three transects sit in a single 20 min
file. Videos are 1440×1080 at 30 fps, about 1.5 MB per second.

A second catalog source, [NOAA NCEI, accession 0239376](https://www.ncei.noaa.gov/archive/accession/0239376)
(Stetson Bank, Flower Garden Banks National Marine Sanctuary, Gulf of Mexico,
July 2018), adds 3 files from permanent 100 m transects, filmed at 1440×1080
with the camera held at a constant height above the line. Its readme gives the
start and end point of each transect. The water is greener and less clear than
in Hawaii.

## Pipeline

```bash
cd playground/scripts
./00-setup-lingbot.sh             # install LingBot-Map (once)
./01-fetch-transect.sh            # download the video (--list for the catalog)
./02-extract-frames.sh            # video -> image sequence
./03-reconstruct.sh               # images -> camera poses + depth (LingBot-Map)
./04-export-web.sh                # cleaning -> public/transects/<key>/
```

`./build-catalog.sh [key ...]` chains the four steps for catalog transects (all
of them by default), adds each one to the site catalog with its site position,
and deletes the transect's intermediates (video, frames, `.npz`: 3 to 4 GB)
before starting the next. Strictly one at a time: a full-length reconstruction
uses most of the RAM of a 16-18 GB Mac. Count ~45 min per 12 min transect on an
M3 Pro.

A cleaned video, `transects/<key>-clean.mp4` (divers blocking the reef cut out
by the `clean-transect-video` skill), replaces the original wherever it exists:
frames are extracted from it, the viewer's video and timestamps follow its
timeline, and the build skips the download and keeps it afterwards. Measured
gains are in [the experiment results](experiments/results/clean-transect-video.md).

Each step writes to its own folder (`transects/`, `frames/`, `out/`), all ignored
by git: these artefacts are heavy and can be reproduced from the scripts. Any
sub-folder of `frames/` is a valid key.

By default the **whole video** is extracted: the longer the swim, the more reef
the 3D covers. The frame rate follows the length, to stay under LingBot-Map's
limit of 1024 frames (kept at 1000): 2 fps up to 8 min 20, about 1.4 fps for a
12 min transect, which still leaves a diver's slow swim well overlapped. Both can
be forced through environment variables:

```bash
FPS=3 START=30 DURATION=90 ./02-extract-frames.sh
```

It also writes `frames/<key>.json` (fps, window start, source video length and
whether the frames are portrait), which step 04 uses to timestamp each frame in the source video and, for
phone videos filmed upright, to undo the 90° turn LingBot-Map applies to portrait
frames. The file sits **next to** the image
folder, not inside it, so the reconstruction only sees images.

## Step 03 — LingBot-Map

[LingBot-Map](https://github.com/robbyant/lingbot-map) (Ant Group, Apache 2.0) is
a streaming 3D reconstruction model derived from VGGT. We use its
[MLX](https://github.com/uqer1244/mlx_lingbot-map) port for Apple Silicon, pinned
to a specific commit by `00-setup-lingbot.sh` and installed in `vendor/` (ignored
by git, 2.2 GB of FP16 weights downloaded on first run).

How it works, in short:

1. a DINOv2 encoder cuts each image (resized to 518×378) into 14 px patches and
   describes them;
2. a transformer compares the patches of the current image with a memory of past
   images (sliding window of 16 images, plus the first 4 kept as a scale
   reference);
3. output heads predict the camera pose, a per-pixel depth and a per-pixel
   **confidence** (1.0 = "no idea");
4. pixel + depth + pose give a 3D point, by plain geometry.

It is a **direct prediction**, with no feature matching or bundle adjustment:
about 2 s per image on an M3 Pro, where classic photogrammetry often failed on
underwater haze and blur.

The reconstruct step runs our own script rather than the port's map
builder: same model, settings and streaming inference, but memory stays
bounded on ~1000 frames. Frames are loaded as uint8 (the port goes through
float32 copies, ~7 GB at 1000 frames), MLX's buffer cache is capped (it otherwise
keeps every freed buffer), and the port's exports are skipped: they unproject
every pixel with the wrong pose reading (see the trap below) into a ~90 M point
`.ply` that nothing uses. The GPU peak, ~13 GB, is set by the 16-frame attention
window, not by the length of the video.

What this means for the data:

- **Arbitrary scale.** No metric reference; distances are relative.
- **Short range.** Far away, the reef fades into the blue: the model says so
  (confidence near 1.0). Step 04 recovers part of it (see below).
- **Possible drift** on long sequences, since the memory only covers the latest
  images.
- **Never trained underwater.** Step 04 compensates for the main side effects
  (depth scale, range, fog), with no guarantee on every video.

## Step 04 — export for the viewer

`export-web.py` turns the `.npz` archive from step 03 into two files:

| File | Content |
| --- | --- |
| `cloud.ply` | Coloured binary point cloud, at most 2 M points (~32 MB) whatever the length of the transect. |
| `path.json` | One camera position per frame and its timestamp in the video (the diver's trajectory), plus the reconstruction parameters shown in the viewer's info panel. |

Before cleaning, the depth scale is **realigned frame by frame**. The model never
saw underwater footage: when the diver rises or sinks, the depth predicted for a
frame can disagree with its neighbours' (up to ±25 % between nearby frames on
`tab-south`), and each frame lays the seabed at a different height — hence
stacked "layers" in the cloud. The poses are kept; every pair of frames up to 8
apart measures how much their depths disagree (median ratio of one frame's
depth over the other's reprojected into it), and a least-squares solve finds the
per-frame scales that best explain these disagreements, with a weak pull towards
the model's own scale.

That pull is what keeps long transects sound. The first version rescaled each
frame against the already rescaled previous ones; on a 1000-frame transect the
chain ran away (some frames ×500 deeper), because inflating depth against
unscaled camera moves makes frames agree trivially. Median depth error between
frames 2 and 8 apart, before → after:

| Transect | Frames | Before | After | Scales p10–p90 |
| --- | --- | --- | --- | --- |
| `tab-south` | 111 | 7.8 / 9.8 % | 3.3 / 7.1 % | 0.81–1.22 |
| `site3` 60 s | 120 | 2.2 / 5.4 % | 1.8 / 3.5 % | 0.95–1.05 |
| `site3-transect3` | 1000 | 7.4 / 19.0 % | 6.1 / 13.5 % | 0.70–1.49 |

Cleaning chains four filters:

1. **Confidence** above `CONF` (1.05 by default): keeps ~57 % of the pixels.
   Far away, the model is unsure (trained in air, it does not know the blue
   haze) and the cloud used to stop at about twice the median depth. A
   low-confidence pixel is therefore **recovered when neighbouring frames agree**
   with it: projected into frames k−3 to k+3, its depth matches theirs within
   5 % in at least 3 of them. These points are about twice less accurate than
   confident ones (checked against frames ±5, outside the vote): good enough
   for distant reef.

   The **fog** trap: in murky water, the model predicts the haze as a smooth
   wall that every frame "agrees" with, which creates artefacts. Agreement only
   means something where there is something to see: a recovered pixel must
   therefore be at least as textured (local contrast) as the least textured
   10 % of the confident surface **of the same frame**. The threshold follows
   each frame's lighting and visibility, with no per-transect tuning (haze: 1 to
   8 grey levels, distant reef: 20 to 27 on `tab-south`).
2. **Open water**: blue-dominant, textureless pixels, with the mask widened by a
   few pixels because depth is unreliable on the reef silhouette ("flying"
   points).
3. **Voxel grid**: one averaged point per voxel. Since the scale is arbitrary and
   differs between reconstructions, the voxel edge is the footprint of one depth
   pixel at the median depth of the confident pixels: as fine as the depth maps
   go, the same relative detail whatever the transect, and far points do not
   coarsen it. The detail budget grows with the video's length
   (`DETAIL_POINTS_PER_SECOND`, 250 k points, ~2.3 MB on disk, per second of
   video), so a full transect keeps the detail of a short excerpt; it is capped
   by the machine's memory. Past the budget the voxels are merged into coarser
   ones until the cloud fits. Frames are merged
   into the grid as they come, and the grid is coarsened as soon as it holds
   twice the budget, so peak RAM follows the budget, not the length of the
   transect: ~7.4 GB on both 111 and 463 frames (10 GB on 463 frames when
   coarsening waited for the end).
4. **Isolated points**: statistical removal based on the distance to the 8
   nearest neighbours.

**Fine depth.** LingBot-Map sees 518 px wide frames whatever the video. When the
source frames are still in `frames/<key>/`, each depth map is refined at twice
that resolution with Depth Anything V2 Small (Apache-2.0, ~0.4 s per frame on
MPS) and the points are coloured from the source frames. The monocular depth is
fitted to LingBot's per frame, LingBot keeps the shape above one 14 px model
patch, and the result stays within 5 % of LingBot's depth (unclamped, the
monocular model rebuilds low-confidence areas its own way). Cross-frame depth
error is unchanged (site3 2.22 → 2.19 %, `tab-south` 8.93 → 8.88 %); coral
branches and rock rims come out in relief. Without frames, the export falls back
to the model's resolution.

**Overview and detail tiles.** A browser cannot hold a full-detail transect, so
the export writes two levels: `cloud.ply`, the detail regrouped into coarser
voxels until it fits `MAX_POINTS` (2 M by default), loaded first; and
`tiles/<i>.bin`, the full detail cut into tiles of at most 250 k points by
recursive median splits along the longest side (9 bytes per point: uint16
position within the tile box, uint8 sRGB colour). `path.json` lists each tile's
box and the overview points it replaces. The viewer streams the tiles in view
whose overview voxel covers more than 2 px on screen, nearest first, up to 4 M
detail points at once. Before tiles, every deployed full-length transect hit the
2 M budget at voxels of 1.4–3.2 % of the viewing distance, 5 to 10 model pixels
per side; the detail level is now one model pixel (~0.3 %), or half of one with
fine depth, within the storage budget.

```bash
CONF=1.2 DETAIL_POINTS_PER_SECOND=100000 ./04-export-web.sh
```

### Trap: the MLX port inverts the camera poses

At the pinned commit, `create_map.py` decodes the poses as "world → camera" and
inverts them, whereas the model predicts "camera → world". Its `extrinsic_w2c` is
therefore the true camera → world pose, and its `world_points` are wrong.
Symptoms: the diver swims backwards, the transect appears **mirrored**, and
successive frames register poorly (blurry cloud, doubled surfaces).

Checked by reprojecting each frame k into frame k+2: median depth error of
**2.2 %** with the right reading, against **11.7 %** with the port's.
`export-web.py` therefore rebuilds the 3D points itself from the depth, the
intrinsics and the corrected poses. Welcome side effect: at equal voxel size, the
number of points halves, a sign that views finally overlap on the same surfaces
— hence a finer default voxel.

The trajectory is smoothed here, not in the viewer: camera position and viewing
direction go through a Gaussian filter whose width is expressed in **seconds of
video** (`PATH_SMOOTH`, 1 s, and `HEADING_SMOOTH`, 1.5 s, by default). The setting
therefore works for any transect and any extraction `FPS`. The viewer only
interpolates (Catmull-Rom spline for the position, linear interpolation for the
direction): during playback, the camera follows the path and looks where the
diver was filming.

Coordinates stay in the reconstruction's frame (OpenCV convention: x right,
y down, z forward); the viewer converts them.

## Leads tested and discarded

Ongoing tests (pre-processing with AI and image filters, with every run kept
and compared) live in [`experiments/`](experiments/README.md).

**Colour correction before inference** (per-channel stretch + CLAHE), measured on
the 40 images of the smoke set: kept pixels 63 % → 57 %, typical range 1.61× →
1.16× the median depth. The model seems to use the blue haze as a distance cue;
removing it makes the model less confident. Raw images give a better result.

## History

The first version of this pipeline relied on NodeODM/OpenDroneMap (CPU
photogrammetry in a container). Abandoned: slow, hard to tune for underwater
footage, and not good enough.
