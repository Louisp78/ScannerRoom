# Playground — from transect video to point cloud

A sandbox **outside the application**: it produces realistic test data for the 3D
viewer from real underwater transect videos. Nothing here is imported by the Vue
app; the only link with it is the folder exported to `public/transects/<key>/`,
which the viewer loads on the `/transects/<key>` route.

## Data source

[NOAA NCEI, accession 0172858](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.nodc:0172858) —
*Video transects of coral reefs on the west coast of the island of Hawaii*
(February 2017). 27 MP4 videos filmed by divers along marked transects, on 7
sites between Kona and North Kohala, 0.2 to 1.7 GB each.

Why this source: it is exactly the capture gesture the product targets (a diver
swimming along a coral coast, camera facing the reef), the data is public (US
government work, no restrictions), and each file can be downloaded on its own
over HTTP, without an account.

Default video: `Old Kona Site 3 2017-02-05 Transect 2 South Leg Return full.MP4`
(219 MB, 1440×1080, 30 fps, 2 min 32 — the lightest of the accession).

## Pipeline

```bash
cd playground/scripts
./00-setup-lingbot.sh             # install LingBot-Map (once)
./01-fetch-transect.sh            # download the video (--list for the others)
./02-extract-frames.sh            # video -> image sequence
./03-reconstruct.sh               # images -> camera poses + depth (LingBot-Map)
./04-export-web.sh                # cleaning -> public/transects/<key>/
```

Each step writes to its own folder (`transects/`, `frames/`, `out/`), all ignored
by git: these artefacts are heavy and can be reproduced from the scripts. Any
sub-folder of `frames/` is a valid key.

Extraction is configured through environment variables:

```bash
FPS=3 START=30 DURATION=90 ./02-extract-frames.sh
```

It also writes `frames/<key>.json` (fps, window start and whether the frames are
portrait), which step 04 uses to timestamp each frame in the source video and, for
phone videos filmed upright, to undo the 90° turn LingBot-Map applies to portrait
frames. The file sits **next to** the image
folder, not inside it, so the reconstruction only sees images.

## Adding a transect from the interface (US-3.3)

For your own video, instead of chaining the scripts by hand:

```bash
npm run dev   # then http://localhost:5173/ingest ("Add a transect" link on the map)
```

The form takes the video, a name, a key (folder name, derived from the name),
the site position (latitude/longitude) and the excerpt to reconstruct (frames per
second, start, duration). The dev server copies the video to
`transects/<key>.mp4`, runs steps 02, 03 and 04, then adds the site to
`src/sites.json`: the point appears on the local map. To publish it, commit
`public/transects/<key>/` and `src/sites.json`; CI deploys as usual.

This interface only exists locally: the reconstruction needs the GPU of an Apple
Silicon Mac (MLX), which the VPS does not have. The HTTP entry point
(`vite-plugins/ingest.ts`) is only wired into the dev server, and the `/ingest`
page is excluded from the production build. One job at a time.

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
| `cloud.ply` | Coloured binary point cloud, ~1.4 M points (21 MB for 60 s of video, against 165 MB and 11 M points for the raw output). |
| `path.json` | One camera position per frame and its timestamp in the video: the diver's trajectory. |

Before cleaning, the depth scale is **realigned frame by frame**. The model never
saw underwater footage: when the diver rises or sinks, the depth predicted for a
frame no longer matches the predicted camera motion (up to ±25 % between nearby
frames on `tab-south`), and each frame lays the seabed at a different height —
hence stacked "layers" in the cloud. The poses are kept and each frame is
rescaled to the 3 previous (already corrected) frames, using the median ratio
between predicted and reprojected depth. No tuning involved: on `tab-south`, the
depth error between frames drops from about 10 % to 4 %; on `site3`, already
consistent, the correction stays small (p10–p90: 0.94–1.04).

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
   differs between reconstructions, the voxel edge is a fraction `VOXEL` (0.01 by
   default) of the median depth of the confident pixels: the same relative
   detail whatever the transect, and far points do not coarsen it.
4. **Isolated points**: statistical removal based on the distance to the 8
   nearest neighbours.

```bash
CONF=1.2 VOXEL=0.015 ./04-export-web.sh
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

**Colour correction before inference** (per-channel stretch + CLAHE), measured on
the 40 images of the smoke set: kept pixels 63 % → 57 %, typical range 1.61× →
1.16× the median depth. The model seems to use the blue haze as a distance cue;
removing it makes the model less confident. Raw images give a better result.

## History

The first version of this pipeline relied on NodeODM/OpenDroneMap (CPU
photogrammetry in a container). Abandoned: slow, hard to tune for underwater
footage, and not good enough.
