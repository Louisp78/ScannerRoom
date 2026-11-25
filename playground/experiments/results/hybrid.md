# Hybrid SfM + LingBot-Map (step 2)

Question: does fixing the camera path with structure-from-motion (SfM, from
the step 1 probe) and correcting LingBot's dense depth towards the SfM points
give a more consistent cloud than LingBot alone?

The hybrid step writes a changed reconstruction; the unchanged export and metrics
score it. Variants, each adding to the previous one:

- `lingbot`: LingBot alone, trimmed to the frames SfM covers (the reference);
- `hybrid-poses`: SfM poses and focal, brought into LingBot's frame and scale;
- `hybrid-depth`: plus each frame's depth corrected towards the SfM points
  it sees, through a smooth field (scale and slow distortions only, the
  model's relief is kept);
- `hybrid-gate`: plus a confident pixel loses its confidence when the
  frames within ±1 s that see it mostly disagree with it.

A frame is trusted only when its SfM depths agree in scale with LingBot's
(within ×1.5 of the median ratio; since round 3, the median of the frames
within ±10 s); the others keep LingBot's motion, attached to the nearest
trusted frame.

| Excerpt | Variant | Trusted frames | depthError2 | depthError8 | jitter | thickness |
| --- | --- | --- | --- | --- | --- | --- |
| site 4 cleaned, 0-23.5 s | lingbot | | 3.9 % | 14.0 % | 0.69 | 0.57 |
| | hybrid-poses | 64 / 71 | 4.1 % | 11.6 % | 0.27 | 0.58 |
| | hybrid-depth | 64 / 71 | **2.0 %** | **4.7 %** | **0.27** | 0.59 |
| | hybrid-gate | 64 / 71 | 2.0 % | 4.7 % | 0.27 | 0.61 |
| site 4 raw, 0-30 s (divers) | lingbot | | 6.9 % | 9.2 % | 0.89 | 0.57 |
| | hybrid-poses | 85 / 90 | 7.2 % | 18.1 % | 0.57 | 0.56 |
| | hybrid-depth | 85 / 90 | **2.4 %** | **2.6 %** | **0.57** | 0.59 |
| | hybrid-gate | 85 / 90 | 2.1 % | 1.7 % | 0.57 | 0.59 |
| site 1 raw, 195-225 s (diver crossing) | lingbot | | 4.0 % | 9.8 % | 0.93 | 0.54 |
| | hybrid-poses | 59 / 90 | 4.7 % | 12.3 % | 1.02 | 0.59 |
| | hybrid-depth | 59 / 90 | 4.4 % | 8.8 % | 1.02 | 0.51 |
| | hybrid-gate | 59 / 90 | 3.4 % | 6.9 % | 1.02 | 0.54 |

Noise floor (README): ±1.6 points on `depthError2`; `depthError8` swings
9-22 % on the same input.

## Findings

- **Poses and depth must be corrected together.** SfM poses alone gain
  nothing on depth consistency: LingBot's depth was made for LingBot's poses.
  With the depth correction, cross-view error halves on both site 4
  excerpts, far beyond the noise, and the path is 1.5-2.5× smoother.
- **Site 1 stays within the noise.** SfM "registered" all 90 frames, but
  stacked the first 33 (diver crossing) on one camera position with no
  depth; the trust check drops them (59 / 90 kept), so there is less to fix.
- **The agreement gate removes the diver's ghost** on site 1 (side view),
  but not the fan of streaks seen from above on every excerpt: neighbours
  within ±1 s do not move the camera enough to expose haze.
- **Thickness rises slightly** (0.57 → 0.59-0.61 voxel) on site 4: the voxel
  follows the median depth, which the correction changes, so this is not yet
  read as a loss.

## Limits

- The depth is fitted to SfM points triangulated with the same poses, so
  part of the consistency gain is by construction. A reference independent
  of both (e.g. SQUID-5) is still needed.
- On site 4 raw, LingBot is confident on 0.1 % of pixels: its depth errors
  rest on very few pixels.
- One seed, three excerpts on two sites, 23-30 s each.

## Round 2 — Old Kona site 3, the hardest stretches

Picked by eye as the worst reconstructions: transect 2 north leg 0:28-1:00
and 1:30-2:00, transect 3 2:00-2:21 (raw videos, level swims along a wall
with much open water in frame). One driver runs the whole chain per excerpt.

First run: SfM reconstructed nothing on two of the three excerpts (plenty of
matches, ~900 per pair, but "no good initial image pair"). COLMAP's default
16° start angle is meant for photo sets; consecutive video frames on a slow,
level swim never reach it. Lowered to 8° for every video in the probe,
all three register 100 % in one model; the table uses that setting.

| Excerpt | Variant | Trusted frames | depthError2 | depthError8 | jitter | thickness |
| --- | --- | --- | --- | --- | --- | --- |
| T2 north, 28-60 s | lingbot | | 2.1 % | 4.8 % | 0.60 | 0.55 |
| | hybrid-depth | 97 / 97 | 1.6 % | 3.9 % | **0.17** | 0.55 |
| | hybrid-gate | 97 / 97 | 1.6 % | 3.8 % | 0.17 | 0.55 |
| T2 north, 90-120 s | lingbot | | 3.2 % | 8.4 % | 0.48 | 0.60 |
| | hybrid-depth | 91 / 91 | 1.8 % | **3.7 %** | **0.12** | 0.61 |
| | hybrid-gate | 91 / 91 | 1.7 % | 3.4 % | 0.12 | 0.61 |
| T3, 120-141 s | lingbot | | 2.7 % | 5.8 % | 0.54 | 0.61 |
| | hybrid-depth | 64 / 64 | **1.4 %** | **2.1 %** | **0.18** | 0.59 |
| | hybrid-gate | 64 / 64 | 1.4 % | 2.1 % | 0.18 | 0.59 |

- Every frame trusted, SfM and LingBot agree within 1-1.6° and 1-2 % of the
  path: the cleanest case so far.
- The camera path is 3-4× smoother on all three; cross-view depth error
  drops on all three, beyond the noise on T2 1:30 and T3, within it on T2 0:28
  (already LingBot's best excerpt, 83 % confident).
- Renders: T2 0:28 comes out narrower and its floor more continuous in side
  view. The fan of streaks seen from above and the stacked vertical layers in
  T3's side view are still there in every variant.

## Round 3 — Old Kona site 3, transect 3 in full

The whole video (11 min 25 s) at 1.45 fps, 994 frames, as production
samples it (under LingBot's 1000-frame limit). About 80 min end to end:
LingBot ~60 min, SfM matching and mapping ~20 min.

SfM registers all 994 frames in one model (200 k points, 1.3 px). The swim is
an out-and-back: SfM finds two straight, parallel legs; LingBot's path
wanders, dives and loops, and its orientation drifts up to 110° from SfM's
(`baseline/sfm-raw/probe.png`). Over a full transect, drift is LingBot's
main defect, and it does not show on 20-30 s excerpts.

The first hybrid run trusted only 665 / 994 frames: the trust check compared
each frame's SfM / LingBot depth ratio with the global median, and LingBot's
depth scale itself drifts along the transect, which is exactly what the
hybrid has to correct. With a local median (±10 s) it trusts 991 / 994.

| Variant | Trusted | depthError2 | depthError8 | jitter | thickness | points |
| --- | --- | --- | --- | --- | --- | --- |
| lingbot | | 8.7 % | 21.0 % | 1.17 | 0.49 | 1.86 M |
| hybrid-depth | 991 / 994 | **2.1 %** | **4.8 %** | **0.26** | 0.54 | 1.51 M |
| hybrid-gate | 991 / 994 | 1.9 % | 4.3 % | 0.26 | 0.54 | 1.51 M |

- **The hypothesis holds on a full transect.** Cross-view error is divided
  by 4, the path is 4× smoother, and the render changes in kind: LingBot's
  tangled shape becomes the two parallel legs of the swim, seen from above
  (`hybrid-compare.jpg`).
- On 20-30 s excerpts, the gain is in the numbers but small to the eye, and
  LingBot alone was judged better looking: short excerpts do not drift enough
  for the hybrid to matter, while its changes (SfM focal, depth warp) show.
- Fewer points (1.51 M against 1.86 M) and slightly thicker surfaces:
  to check in the viewer, together with the veil.
- The excerpt rounds above ran with the global trust median; not re-run.

## Round 4 — colours, detail and the blue veil (export filters)

Full T3: the hybrid's cloud is bluer (44 % water-blue points against 35 %)
and has less local contrast (0.041 against 0.053). Ruled out: the SfM focal
(keeping LingBot's changes nothing on the T3 excerpt) and the averaging of
close and distant views in a voxel (weighting towards close views: +4 %
contrast only, reverted). Cause found: the export recovers low-confidence
pixels that neighbouring frames agree with, and with consistent poses it
recovers twice as many (15.5 % of pixels against 7.9 %), mostly distant,
hazy reef or haze itself.

Two generic tests on those pixels, in the export:
- haze colour: closer to the frame's open-water colour than half the reef's
  typical distance to it;
- free space: a frame 3 s away sees further than the point, i.e. through
  it (seeing nearer is an occlusion and proves nothing).

Screening, hybrid-depth, water-blue points / kept pixels:

| Excerpt | none | haze | free space | both, recovered | both, all pixels |
| --- | --- | --- | --- | --- | --- |
| T3 2:00-2:21 | 32 % / 49 % | 21 % / 45 % | 26 % / 46 % | **17 % / 43 %** | 18 % / 41 % |
| T2 north 1:30-2:00 | 35 % / 46 % | 19 % / 42 % | 29 % / 42 % | **17 % / 39 %** | 17 % / 35 % |
| site 4 cleaned | 30 % / 40 % | 27 % / 40 % | 20 % / 35 % | **18 % / 35 %** | 19 % / 31 % |

Applying them to confident pixels too removes no more blue, only reef.

Full T3, both filters on recovered pixels:

| Run | water-blue | local contrast | kept | thickness |
| --- | --- | --- | --- | --- |
| lingbot | 35 % → 24 % | 0.053 → 0.057 | 54 % → 51 % | 0.51 |
| hybrid-depth | 44 % → 28 % | 0.041 → 0.044 | 59 % → 55 % | 0.50 |

Water-blue share is a proxy (blue-lit sand counts too). Judged satisfying
in the viewer: both filters, on recovered pixels, are now on by default.

## Next

1. Blue veil: test agreement against frames several seconds apart (wider
   baseline), and the absence of SfM points as a water cue.
2. Catch SfM's collapsed stretches in the probe itself (step 1 reported them
   as registered).
3. Longer excerpts, to see whether drift correction grows with length.
