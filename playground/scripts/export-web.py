"""Export a LingBot-Map .npz as web assets for the Vue viewer.

Usage: export-web.py <reconstruction.npz> <frames-meta.json> <out-dir> [--conf 1.05] [--voxel 0.01]

Writes into <out-dir>:
- cloud.ply: coloured point cloud, cleaned and downsampled to ~1-2 M points.
- path.json: per frame, the smoothed camera position, the smoothed viewing
  direction and the timestamp in the video. Smoothing is done here, in seconds
  of video, so the viewer only interpolates and works for any frame rate.

Before cleaning, each frame's depth is rescaled to agree with the previous
frames (see "depth scale correction" below).

Cleaning steps, in order:
1. Keep pixels above the depth-confidence threshold (1.0 means "no idea"),
   plus low-confidence but textured pixels that neighbouring frames agree
   with (far reef, not fog).
2. Drop open-water pixels: blue-dominant and textureless. The mask is widened a
   few pixels because depth at the reef/water silhouette is unreliable and
   produces "flying" points.
3. Voxel downsample: one averaged point per voxel. The scale is arbitrary and
   varies between reconstructions, so the voxel edge is a fraction of the
   median depth of the kept pixels, giving the same relative detail everywhere.
   Long transects would exceed what a browser loads comfortably, so the voxel
   grows (coarser detail) until the cloud fits the --max-points budget.
4. Statistical outlier removal on the downsampled cloud.

Frames are processed one at a time and merged into the voxel grid as they go,
so memory stays bounded on full-length transects (~1000 frames).

Coordinates are in the first camera's frame (OpenCV convention: x right,
y down, z forward, scale arbitrary); the viewer converts them. For portrait
videos that frame is first turned back upright (see "portrait frames" below).
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree

parser = argparse.ArgumentParser()
parser.add_argument("npz")
parser.add_argument("meta")
parser.add_argument("out_dir")
parser.add_argument("--conf", type=float, default=1.05)
# Voxel edge as a fraction of the median kept depth (0.01 ~ 0.008 on site3).
parser.add_argument("--voxel", type=float, default=0.01)
# Per-frame poses jitter (hand-held camera, 2 fps). Gaussian sigmas in seconds.
parser.add_argument("--path-smooth", type=float, default=1.0)
parser.add_argument("--heading-smooth", type=float, default=1.5)
# Web budget: ~16 bytes per point in cloud.ply, so 2 M points is ~32 MB.
parser.add_argument("--max-points", type=int, default=2_000_000)
args = parser.parse_args()

d = np.load(args.npz, allow_pickle=False)
meta = json.loads(Path(args.meta).read_text())
# reconstruct.py stores images as uint8, the port's create_map.py as float 0-1.
imgs, conf = d["images"], d["depth_conf"]


def image(k: int) -> np.ndarray:
    """Frame k as float32 RGB in 0-1."""
    im = imgs[k]
    return im.astype(np.float32) / 255 if im.dtype == np.uint8 else im


def local_contrast(img: np.ndarray) -> np.ndarray:
    """Grey-level standard deviation over a 9x9 window: how textured each pixel is."""
    gray = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    return np.sqrt(np.maximum(cv2.blur(gray**2, (9, 9)) - cv2.blur(gray, (9, 9)) ** 2, 0))


def water_mask(img: np.ndarray, contrast: np.ndarray) -> np.ndarray:
    mask = ((img[..., 2] - img[..., 0] > 0.25) & (contrast < 4)).astype(np.uint8)
    return cv2.dilate(mask, np.ones((7, 7), np.uint8)).astype(bool)




# The MLX port (commit a2fe95c) decodes the pose encoding as world-to-camera and
# inverts it, but the model actually predicts camera-to-world. Its
# "extrinsic_w2c" is therefore the true camera-to-world pose, and its
# "world_points" were built with inverted poses (diver swimming backwards,
# mirrored transect, frames misregistered). Measured on site3: reprojecting
# frame k into frame k+2 gives a 2.2 % median depth error with this reading,
# 11.7 % with the port's. So rebuild the world points from depth ourselves.
c2w = d["extrinsic_w2c"].astype(np.float64)
K = d["intrinsic"].astype(np.float64)
depth = d["depth"][..., 0].astype(np.float32)
H, W = depth.shape[1:]
u, v = np.meshgrid(np.arange(W), np.arange(H))
confident = conf > args.conf


def back_project(k: int) -> np.ndarray:
    """World points (H, W, 3) of frame k from its depth and pose."""
    z = depth[k].astype(np.float64)
    cam = np.stack([(u - K[k, 0, 2]) / K[k, 0, 0] * z, (v - K[k, 1, 2]) / K[k, 1, 1] * z, z], -1)
    return cam @ c2w[k, :, :3].T + c2w[k, :, 3]


def project(pts: np.ndarray, k: int):
    """Pixel (x, y) and depth z of world points pts (..., 3) in frame k, plus an
    inside-the-image mask; x and y are clamped to 0 outside it."""
    q = (pts - c2w[k, :, 3]) @ c2w[k, :, :3]
    z = q[..., 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.round(K[k, 0, 0] * q[..., 0] / z + K[k, 0, 2])
        y = np.round(K[k, 1, 1] * q[..., 1] / z + K[k, 1, 2])
    inside = (z > 0) & (x >= 0) & (x < W) & (y >= 0) & (y < H)
    return inside, np.where(inside, x, 0).astype(int), np.where(inside, y, 0).astype(int), z


def depth_ratio(pts: np.ndarray, k: int) -> float:
    """Median of frame k's predicted depth over the depth of pts seen from frame k."""
    inside, x, y, z = project(pts, k)
    ok = inside & confident[k, y, x]
    return float(np.median(depth[k, y[ok], x[ok]] / z[ok])) if ok.sum() >= 500 else 1.0


# The model was never trained underwater: when the diver rises or sinks, each
# frame's depth scale disagrees with the predicted camera motion (up to +-25 %
# between frames 2 apart on tab-south), so every frame lays the seabed at a
# different height and the cloud shows stacked layers. Keep the poses and
# rescale each frame's depth so it agrees with the previous, already corrected,
# frames: on tab-south the frame-to-frame depth error drops from ~10 % to ~4 %.
SCALE_REF = 3
scales = np.ones(len(depth))
for k in range(1, len(depth)):
    ref = np.concatenate([back_project(j)[confident[j]][::4] for j in range(max(0, k - SCALE_REF), k)])
    scales[k] = depth_ratio(ref, k)
    depth[k] /= scales[k]
print(f"depth scale correction: p10 {np.percentile(scales, 10):.3f}, p90 {np.percentile(scales, 90):.3f}")


# Far away the model is unsure (trained in air, never saw water haze) and its
# confidence drops below the threshold, so the cloud stopped about twice the
# median depth away. A low-confidence pixel is still kept when its neighbouring
# frames agree with it: projected into frames k-3..k+3, its depth matches
# theirs within 5 % in at least 3 of them (multi-view geometric consistency).
# Points checked against frames +-5, not used for the vote, are about twice
# less accurate than confident ones: fine for distant reef, not for close-up.
# Agreement only proves something where there is texture to match: in murky
# water the model predicts the fog as a smooth wall that every frame "agrees"
# with (local contrast 1-8 grey levels, against 20-27 for distant reef on
# tab-south). So a recovered pixel must be at least as textured as the least
# textured 10 % of the frame's confident surface; the bar follows each frame's
# lighting and visibility instead of a fixed value.
AGREE_FRAMES, AGREE_TOL, AGREE_VOTES = 3, 0.05, 3
water = np.stack([water_mask(image(k), local_contrast(image(k))) for k in range(len(depth))])
# Voxel from confident pixels only, so far points do not coarsen the detail.
median_depth = float(np.median(depth[confident & ~water]))
voxel = args.voxel * median_depth

# Voxel grid, filled frame by frame: one packed int64 key per voxel, with the
# sums of the positions and colours that fell in it and their count.
KEY_BITS = 21
KEY_HALF = 1 << (KEY_BITS - 1)


def voxel_keys(p: np.ndarray, edge: float) -> np.ndarray:
    q = np.floor(p / edge).astype(np.int64) + KEY_HALF
    assert q.min() >= 0 and q.max() < 1 << KEY_BITS, "cloud too large for the voxel key"
    return (q[:, 0] << 2 * KEY_BITS) | (q[:, 1] << KEY_BITS) | q[:, 2]


def merge(keys: np.ndarray, sums: np.ndarray, counts: np.ndarray):
    """Collapse rows sharing a key."""
    uniq, inv = np.unique(keys, return_inverse=True)
    return (uniq, np.stack([np.bincount(inv, sums[:, j], len(uniq)) for j in range(6)], 1),
            np.bincount(inv, counts, len(uniq)))


grid = (np.empty(0, np.int64), np.empty((0, 6)), np.empty(0))
pending, n_confident, n_agreeing, n_kept = [], 0, 0, 0
for k in range(len(depth)):
    world_k = back_project(k)
    votes = np.zeros((H, W), int)
    for j in range(max(0, k - AGREE_FRAMES), min(len(depth), k + AGREE_FRAMES + 1)):
        if j != k:
            inside, x, y, z = project(world_k, j)
            with np.errstate(divide="ignore", invalid="ignore"):
                votes += inside & (np.abs(np.log(depth[j, y, x] / z)) < AGREE_TOL)
    contrast = local_contrast(image(k))
    surface = contrast[confident[k] & ~water[k]]
    # A frame with no confident reef (diver looking at open water) recovers nothing.
    textured = contrast >= np.percentile(surface, 10) if surface.size else np.zeros((H, W), bool)
    agreeing = ~confident[k] & textured & (votes >= AGREE_VOTES)
    keep = (confident[k] | agreeing) & ~water[k]
    n_confident += int(confident[k].sum())
    n_agreeing += int(agreeing.sum())
    n_kept += int(keep.sum())
    pts = world_k[keep]
    pending.append((voxel_keys(pts, voxel), np.hstack([pts, image(k)[keep]]), np.ones(len(pts))))
    if len(pending) == 32 or k == len(depth) - 1:
        grid = merge(*(np.concatenate([g, *(p[i] for p in pending)]) for i, g in enumerate(grid)))
        pending = []

n_pixels = depth.size
print(f"confident pixels {n_confident / n_pixels * 100:.1f}%, + agreeing views {n_agreeing / n_pixels * 100:.1f}%, "
      f"after water removal {n_kept / n_pixels * 100:.1f}% -> {n_kept:,} points")
print(f"voxel {voxel:.5f} ({args.voxel} x median depth): {len(grid[0]):,} points")

# Over budget: regroup the voxels into coarser ones, weighted by their counts.
# The cloud is a surface, so the point count goes with 1 / edge^2.
while len(grid[0]) > args.max_points:
    voxel *= np.sqrt(len(grid[0]) / args.max_points) * 1.02
    _, sums, counts = grid
    grid = merge(voxel_keys(sums[:, :3] / counts[:, None], voxel), sums, counts)
    print(f"over the {args.max_points:,} point budget: voxel {voxel:.5f} -> {len(grid[0]):,} points")

_, sums, counts = grid
pts, cols = sums[:, :3] / counts[:, None], sums[:, 3:] / counts[:, None]
del grid, sums, counts

dist, _ = cKDTree(pts).query(pts, k=9)
mean_d = dist[:, 1:].mean(1)
inlier = mean_d < mean_d.mean() + 2 * mean_d.std()
pts, cols = pts[inlier], cols[inlier]
print(f"outliers removed {(~inlier).sum():,} -> {len(pts):,} points")

# Portrait frames: LingBot-Map turns them 90 deg clockwise before reconstructing
# (create_map.py, any image taller than wide), so its world frame, the first
# camera's, lies on its side: the image's up points along +x instead of -y,
# and the viewer would show the reef and the diver's-eye view rolled by 90 deg.
# Express everything in the upright camera's frame instead: a pixel turned
# clockwise maps (x, y) to (-y, x), hence upright = (y, -x, z) of the model's.
# Older sidecars predate the flag and come from landscape videos.
UPRIGHT = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]]) if meta.get("portrait") else np.eye(3)
pts = pts @ UPRIGHT.T

out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
trimesh.PointCloud(pts.astype(np.float32),
                   colors=(cols * 255).clip(0, 255).astype(np.uint8)).export(out / "cloud.ply")

# Frame k of the extraction sits at START + k / FPS in the source video.
fps = meta["fps"]
cams = gaussian_filter1d(c2w[:, :3, 3] @ UPRIGHT.T, args.path_smooth * fps, axis=0, mode="nearest")
# Optical axis (camera +z) in world coordinates: where the diver was filming.
forwards = gaussian_filter1d(c2w[:, :3, 2] @ UPRIGHT.T, args.heading_smooth * fps, axis=0, mode="nearest")
forwards /= np.linalg.norm(forwards, axis=1, keepdims=True)
times = meta["start"] + np.arange(len(cams)) / fps
(out / "path.json").write_text(json.dumps({
    "video": meta["video"],
    "positions": np.round(cams, 4).tolist(),
    "forwards": np.round(forwards, 4).tolist(),
    "times": np.round(times, 3).tolist(),
    # How the 3D was built, shown in the viewer's info panel. Lengths are in
    # scene units (arbitrary scale), the rest is relative.
    "reconstruction": {
        "model": "LingBot-Map (MLX, FP16)",
        "frames": len(cams),
        "fps": fps,
        # Length of the source video; older sidecars predate it.
        "videoLength": round(meta["length"], 1) if "length" in meta else None,
        "points": len(pts),
        "voxel": round(voxel, 6),
        "voxelOfMedianDepth": round(voxel / median_depth, 4),
        "confidence": args.conf,
        "keptPixels": round(n_kept / n_pixels, 3),
        "recoveredPixels": round(n_agreeing / n_pixels, 3),
        "depthScale": [round(float(np.percentile(scales, q)), 3) for q in (10, 90)],
        "pathLength": round(float(np.linalg.norm(np.diff(cams, axis=0), axis=1).sum()), 3),
        "medianDepth": round(median_depth, 4),
    },
}))
print(f"saved {out / 'cloud.ply'} ({(out / 'cloud.ply').stat().st_size / 1e6:.1f} MB) and {out / 'path.json'}")
