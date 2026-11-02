"""Export a LingBot-Map .npz as web assets for the Vue viewer.

Usage: export-web.py <reconstruction.npz> <frames-meta.json> <out-dir> [--conf 1.05] [--voxel 0.008]

Writes into <out-dir>:
- cloud.ply: coloured point cloud, cleaned and downsampled to ~1 M points.
- path.json: per frame, the smoothed camera position, the smoothed viewing
  direction and the timestamp in the video. Smoothing is done here, in seconds
  of video, so the viewer only interpolates and works for any frame rate.

Cleaning steps, in order:
1. Keep pixels above the depth-confidence threshold (1.0 means "no idea").
2. Drop open-water pixels: blue-dominant and textureless. The mask is widened a
   few pixels because depth at the reef/water silhouette is unreliable and
   produces "flying" points.
3. Voxel downsample: one averaged point per voxel.
4. Statistical outlier removal on the downsampled cloud.

Coordinates stay in the reconstruction's world frame (OpenCV convention:
x right, y down, z forward, scale arbitrary); the viewer converts them.
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
parser.add_argument("--voxel", type=float, default=0.008)
# Per-frame poses jitter (hand-held camera, 2 fps). Gaussian sigmas in seconds.
parser.add_argument("--path-smooth", type=float, default=1.0)
parser.add_argument("--heading-smooth", type=float, default=1.5)
args = parser.parse_args()

d = np.load(args.npz, allow_pickle=False)
meta = json.loads(Path(args.meta).read_text())
imgs, conf = d["images"], d["depth_conf"]


def water_mask(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    local_std = np.sqrt(np.maximum(cv2.blur(gray**2, (9, 9)) - cv2.blur(gray, (9, 9)) ** 2, 0))
    mask = ((img[..., 2] - img[..., 0] > 0.25) & (local_std < 4)).astype(np.uint8)
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
depth = d["depth"][..., 0].astype(np.float64)
H, W = depth.shape[1:]
u, v = np.meshgrid(np.arange(W), np.arange(H))
world = np.empty(depth.shape + (3,))
for k in range(len(depth)):
    z = depth[k]
    cam = np.stack([(u - K[k, 0, 2]) / K[k, 0, 0] * z, (v - K[k, 1, 2]) / K[k, 1, 1] * z, z], -1)
    world[k] = cam @ c2w[k, :, :3].T + c2w[k, :, 3]

confident = conf > args.conf
keep = confident & ~np.stack([water_mask(im) for im in imgs])
pts = world[keep]
cols = imgs[keep].astype(np.float64)
print(f"confident pixels {confident.mean() * 100:.1f}%, after water removal {keep.mean() * 100:.1f}% -> {len(pts):,} points")

_, inv, counts = np.unique(np.floor(pts / args.voxel).astype(np.int64), axis=0,
                           return_inverse=True, return_counts=True)
inv = inv.ravel()
pts = np.stack([np.bincount(inv, pts[:, j]) for j in range(3)], 1) / counts[:, None]
cols = np.stack([np.bincount(inv, cols[:, j]) for j in range(3)], 1) / counts[:, None]
print(f"voxel {args.voxel}: {len(pts):,} points")

dist, _ = cKDTree(pts).query(pts, k=9)
mean_d = dist[:, 1:].mean(1)
inlier = mean_d < mean_d.mean() + 2 * mean_d.std()
pts, cols = pts[inlier], cols[inlier]
print(f"outliers removed {(~inlier).sum():,} -> {len(pts):,} points")

out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
trimesh.PointCloud(pts.astype(np.float32),
                   colors=(cols * 255).clip(0, 255).astype(np.uint8)).export(out / "cloud.ply")

# Frame k of the extraction sits at START + k / FPS in the source video.
fps = meta["fps"]
cams = gaussian_filter1d(c2w[:, :3, 3], args.path_smooth * fps, axis=0, mode="nearest")
# Optical axis (camera +z) in world coordinates: where the diver was filming.
forwards = gaussian_filter1d(c2w[:, :3, 2], args.heading_smooth * fps, axis=0, mode="nearest")
forwards /= np.linalg.norm(forwards, axis=1, keepdims=True)
times = meta["start"] + np.arange(len(cams)) / fps
(out / "path.json").write_text(json.dumps({
    "video": meta["video"],
    "positions": np.round(cams, 4).tolist(),
    "forwards": np.round(forwards, 4).tolist(),
    "times": np.round(times, 3).tolist(),
}))
print(f"saved {out / 'cloud.ply'} ({(out / 'cloud.ply').stat().st_size / 1e6:.1f} MB) and {out / 'path.json'}")
