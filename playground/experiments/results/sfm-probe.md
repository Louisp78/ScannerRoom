# Photogrammetry feasibility (hybrid step 1)

Question: on these diver videos, can a classical structure-from-motion (SfM)
register the frames in one piece, and do its cameras agree with LingBot-Map's?
That decides whether a hybrid (SfM fixes the camera path, LingBot fills the
dense depth) is worth building.

Method: frames and `recon.npz` of existing bench runs (3 fps, 1036 px).
SuperPoint + LightGlue features; pairs follow the LingBot path (5 next
neighbours, plus up to 5 nearest revisits per frame); COLMAP incremental
mapping with one shared camera. The SfM path is then brought into LingBot's
frame by a similarity (rotation from the camera orientations) and compared.
Uncleaned excerpts were cut to their first 30 s to keep runs short.

| Excerpt | Frames | Registered, one model | Points | Reproj. | Focal SfM / LingBot | Position gap (of path) | Orientation gap | Time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| site 4 cleaned, 0-23.5 s | 71 | **100 %** | 11.2 k | 1.21 px | 744 / 723 | 1.9 % | 2.9° | 1 min |
| site 1 cleaned, 156-189 s | 100 | **100 %** | 14.4 k | 1.46 px | 937 / 816 | 7.0 % | 27° (cut, see below) | 3 min |
| site 4 raw, 0-30 s (divers setting the marker) | 90 | **100 %** | 9.6 k | 1.57 px | 683 / 762 | 2.8 % | 4.3° | 2.7 min |
| site 1 raw, 195-225 s (diver crossing) | 90 | **100 %** | 13.7 k | 1.47 px | 751 / 821 | 6.2 % | 13° | 2.7 min |

Variant `contrast` (CLAHE on what the feature extractor sees): no gain on
site 4 cleaned, and it split site 1 cleaned into two models (74 + 26 frames).
Dropped.

## Findings

- **SfM registers every frame in one model on all four excerpts**, including
  the ones with divers filling the frame. Fragmentation, the main risk, did
  not happen here. But "registered" overstates it: on site 1 raw, the first
  33 frames (diver crossing) sit on one camera position with no depth, a
  collapse this probe does not detect (found in step 2, see the hybrid results).
- **LingBot is right locally and drifts globally.** Frame-to-frame rotations
  agree closely (correlation 0.99 on site 4); the orientation gap is near
  zero mid-excerpt and grows towards both ends (5-7° after 23 s on site 4).
- **A cut in a cleaned video is a jump for both methods**: site 1 cleaned has
  one between frames 25 and 26 (90° for LingBot, 61° for SfM). They disagree
  on the jump, which inflates the median gap. A hybrid must treat the parts
  between cuts separately or let SfM link them through shared reef.
- **SfM is sparse**: 10-14 k points against ~900 k from LingBot on the same
  frames. It fixes the camera path, not the density.
- Agreement does not say which one is right. SfM is geometrically checked
  (reprojection ~1.2-1.6 px, points seen in 7-11 frames), but an external
  reference is still needed to call it ground truth.

## Pitfall

The field LingBot-Map names `extrinsic_w2c` is the true camera-to-world pose
(as the export script notes). Read the other way round, SfM and LingBot move
in opposite directions.
