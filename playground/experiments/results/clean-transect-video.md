# Cutting divers and gear out of the video (`clean-transect-video` skill)

The `clean-transect-video` skill cuts the parts of a transect
video that show divers, an unstable camera or moving non-environmental objects.
Each cut is scored on an excerpt around it: `run.sh <key> baseline` on the
original window, then on the same reef in the cleaned video (3 fps, one seed).

## Round 1 — Old Kona site 3, south leg

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

## Round 2 — three more sites (Puakō 1, Old Kona 4, Mahukona 6)

One transect per area not tested yet, all NOAA diver swims (1440×1080,
10-12 min). Same method; each excerpt covers one cut or two close ones.
`confident` drops when a close diver is removed, since the diver's body was
itself confident surface: read it together with the render.

| Excerpt | What was cut | confident | depthError2 | depthError8 | jitter |
| --- | --- | --- | --- | --- | --- |
| site 1, 0-60 s | diver laying the tape, filling the frame, 0-39 s | 0.424 → 0.439 | 3.8 → 3.6 % | 8.7 → 8.1 % | 1.10 → **0.67** |
| site 4, 0-60 s | two divers setting the start marker, filling the frame, 0-36.5 s | 0.017 → **0.200** | 6.2 → **3.9 %** | 9.2 → 14.0 % | 0.96 → **0.69** |
| site 6, 0-40 s | diver filling the frame 0-9.5 s, then at the edge 15-21 s | 0.133 → 0.066 | 5.4 → **3.4 %** | 12.1 → 10.0 % | 0.93 → **0.70** |
| site 4, 540-600 s | two divers working, filling the frame, 551-577 s; hand at the edge 587-591 s | 0.577 → 0.572 | 5.0 → 4.2 % | 12.0 → 8.1 % | 1.08 → **0.78** |
| site 6, 155-185 s | diver crossing, filling the frame, 166.5-170.5 s | 0.522 → 0.461 | 2.8 → 2.3 % | 7.1 → 4.6 % | 1.05 → 1.08 |
| site 1, 195-240 s | diver crossing 203.5-210.5 s, reel at the edge 225.5-230.5 s | 0.300 → 0.334 | 4.1 → 4.2 % | 10.1 → 8.0 % | 1.10 → 0.99 |
| site 4, 185-225 s | blur, then a diver over half the frame, 199.5-207.5 s | 0.323 → 0.385 | 4.7 → 4.7 % | 9.9 → 10.1 % | 0.98 → 0.80 |
| site 1, 375-405 s | hand and reel at the edge, 385-394.5 s | 0.357 → 0.299 | 3.9 → 4.3 % | 7.0 → 11.3 % | 0.83 → 0.80 |
| site 1, 545-580 s | hand and reel, large then at the edge, 557-566.5 s | 0.628 → 0.571 | 2.5 → 2.8 % | 6.6 → 6.4 % | 0.82 → 0.66 |
| site 6, 465-500 s | diver at the top edge, 478.5-484.5 s | 0.443 → 0.402 | 3.6 → 3.5 % | 6.2 → 8.2 % | 0.77 → 0.59 |
| site 4, 285-310 s | motion blur only, 295.5-298.5 s | 0.871 → 0.836 | 3.6 → 3.8 % | 9.6 → 10.5 % | 0.61 → 0.58 |

Not scored: site 1's last cut (two divers at the end marker, 713 s to the
end), with no reef after it to compare.

- **Every one of these transects opens with divers setting up the tape and
  marker, and cutting that is the consistent win.** On all three sites the
  diver's dark ghost is gone from the side view and the camera path is much
  smoother (jitter −0.23 to −0.43, against ~0.1 run-to-run). Depth error drops
  beyond the noise on two of three. The top-view fan of smeared surfaces seen
  in round 1 does **not** go away here: the cleaned excerpts still show it, so
  it comes from the wide, water-heavy opening shots, not from the diver.
- **Divers crossing in the middle of the transect**: within the noise on
  coverage and depth error, smoother path on three of four. A small but
  steady gain, as in round 1.
- **A hand or reel at the frame edge** (three excerpts, plus round 1's diver
  at the edge): no gain on any metric, and `confident` falls by 4-6 points
  twice. These cuts cost frames for nothing measurable.
- **A 3 s blur-only cut** changes nothing.
- **Cuts never broke the path**: jitter did not rise beyond the noise in any
  of the 11 pairs.

Limits: one seed per excerpt, and the noise floor was measured on tab-south,
not on these transects. The cleaned excerpts are shorter than the originals
(the cut frames are gone), which may lower `confident` and `jitter` on their
own.

Skill change after this round: a hand, reel or part of a diver that stays at
the frame edge (under about a quarter of the frame, reef visible behind) is
now kept; only divers that block the reef are cut. The three cleaned videos
were regenerated under that rule (four edge-only cuts dropped). The scores
above use the earlier cuts.
