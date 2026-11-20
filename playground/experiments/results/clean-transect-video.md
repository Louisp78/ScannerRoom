# Cutting divers and gear out of the video (`clean-transect-video` skill)

The `clean-transect-video` skill cuts the parts of a transect
video that show divers, an unstable camera or moving non-environmental objects.
Each cut is scored on an excerpt around it: `run.sh <key> baseline` on the
original window, then on the same reef in the cleaned video (3 fps, one seed).

| Excerpt | What was cut | confident | depthError2 | depthError8 | jitter |
| --- | --- | --- | --- | --- | --- |
| south-forward 0-40 s | diver + marker filling the frame, 0-20 s | 0.220 → **0.424** | 5.4 → **3.5 %** | 20.4 → **11.4 %** | 0.56 → 0.41 |
| south-forward 160-195 s | diver crossing the frame, 175-178 s | 0.570 → 0.542 | 4.3 → 4.0 % | 9.7 → 10.4 % | 0.78 → 0.68 |
| south-return 0-25 s | diver at the frame edge, 0-4 s | 0.615 → 0.558 | 1.7 → 1.8 % | 3.9 → 3.5 % | 0.79 → 0.74 |
| south-return 125-152 s | survey marker and its rope, 144-152 s | 0.818 → 0.846 | 2.1 → 2.0 % | 4.7 → 4.6 % | 0.35 → 0.38 |

tab-south (snorkel, 101 s) had nothing to cut: no false positive.

Noise floor (README): ±4 points of `confident`, ±1.6 points of `depthError2`.

- **A diver filling the frame for long is the clear win**: coverage doubles and
  depth error halves, far beyond the noise. The top view loses its fan of
  smeared surfaces.
- **A short crossing** stays within the noise on the numbers, but the dark
  ghost the diver left in the cloud is gone from the render. Cutting it does
  not break the path: jitter and depth error do not rise across the cut.
- **Static objects on the reef** (marker, tape) change nothing: they hold
  still and reconstruct like rock. The skill now keeps them, so it only loses
  frames when the scene moves on its own.
