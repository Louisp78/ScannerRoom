"""Export a LingBot-Map .npz as web assets for the Vue viewer.

Usage: export-web.py <reconstruction.npz> <frames-meta.json> <out-dir> [--frames <dir>] [--conf 1.05]

Writes into <out-dir>:
- cloud.ply: coloured point cloud, cleaned and downsampled to at most
  --max-points: the overview the viewer loads first. Points are sorted by tile.
- tiles/<i>.bin: the same cloud at full detail (see "detail tiles" below), cut
  into spatial tiles the viewer streams in near the camera. Only written when
  the full detail does not fit the overview budget.
- path.json: per frame, the smoothed camera position, the smoothed viewing
  direction and the timestamp in the video. Smoothing is done here, in seconds
  of video, so the viewer only interpolates and works for any frame rate.
  Also the tile index and the reconstruction parameters.

Before cleaning, each frame's depth is rescaled to agree with its neighbouring
frames (see "depth scale correction" below). With --frames (the source frames
the reconstruction was run on), each depth map is then refined at twice the
model's resolution and coloured from the source frames (see "fine depth").

Cleaning steps, in order:
1. Keep pixels above the depth-confidence threshold (1.0 means "no idea"),
   plus low-confidence but textured pixels that neighbouring frames agree
   with (far reef, not fog).
2. Drop open-water pixels: blue-dominant and textureless. The mask is widened a
   few pixels because depth at the reef/water silhouette is unreliable and
   produces "flying" points.
3. Voxel downsample: one averaged point per voxel. The scale is arbitrary and
   varies between reconstructions, so the voxel edge is the footprint of one
   depth pixel (the model's, or the fine depth's with --frames) at the median
   depth of the kept pixels: as fine as the depth maps go, the same relative
   detail everywhere. If that exceeds the
   --max-detail-points storage budget, the voxel grows until it fits.
4. Statistical outlier removal on the downsampled cloud.
5. Overview: the detail cloud regrouped into coarser voxels until it fits the
   --max-points budget, what a browser loads comfortably in one go.

Frames are processed one at a time and merged into the voxel grid as they go,
so memory stays bounded on full-length transects (~1000 frames).

Coordinates are in the first camera's frame (OpenCV convention: x right,
y down, z forward, scale arbitrary); the viewer converts them. For portrait
videos that frame is first turned back upright (see "portrait frames" below).
"""
import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter1d
from scipy.sparse import coo_matrix, identity
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

parser = argparse.ArgumentParser()
parser.add_argument("npz")
parser.add_argument("meta")
parser.add_argument("out_dir")
# Source frames of the reconstruction (02-extract-frames.sh output). Without
# them, the cloud stays at the model's 518 px resolution.
parser.add_argument("--frames")
parser.add_argument("--conf", type=float, default=1.05)
# Per-frame poses jitter (hand-held camera, 2 fps). Gaussian sigmas in seconds.
parser.add_argument("--path-smooth", type=float, default=1.0)
parser.add_argument("--heading-smooth", type=float, default=1.5)
# Web budget of the overview: ~16 bytes per point in cloud.ply, so 2 M points is ~32 MB.
parser.add_argument("--max-points", type=int, default=2_000_000)
# Storage budget of the detail tiles: 9 bytes per point, so 12 M points is
# ~108 MB on disk. Browsers only download the tiles near the camera.
parser.add_argument("--max-detail-points", type=int, default=12_000_000)
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


def log_depth_ratio(pts: np.ndarray, k: int) -> float | None:
    """Median log of frame k's predicted depth over the depth of pts seen from
    frame k; None when they overlap too little to tell."""
    inside, x, y, z = project(pts, k)
    ok = inside & confident[k, y, x]
    return float(np.median(np.log(depth[k, y[ok], x[ok]] / z[ok]))) if ok.sum() >= 500 else None


# The model was never trained underwater: when the diver rises or sinks, a
# frame's depth scale can disagree with its neighbours' (up to +-25 % between
# frames 2 apart on tab-south), so every frame lays the seabed at a different
# height and the cloud shows stacked layers. Keep the poses and rescale each
# frame's depth: every pair of frames up to SCALE_PAIRS apart measures how much
# their predicted depths disagree (median log ratio of one frame's depth over
# the other's reprojected into it), and a least-squares solve finds the
# per-frame log scales c that best explain these differences (c_k - c_j), with
# a weak pull towards the model's own scale (SCALE_PRIOR * c_k^2).
# The pull matters: an earlier version rescaled each frame against the already
# rescaled previous ones, and on long transects that chain ran away (depth x500
# on some frames after 1000 frames: inflating depth against unscaled camera
# moves makes frames agree trivially). Measured on tab-south / site3 (60 s) /
# site3 transect 3 (1000 frames), median depth error between frames 2 and 8
# apart: none 7.8/9.8, 2.2/5.4, 7.4/19.0 %; this 3.3/7.1, 1.8/3.5, 6.1/13.5 %,
# scales p10-p90 within 0.70-1.49 and the median depth kept (x1.00-1.02).
SCALE_PAIRS, SCALE_PRIOR = 8, 0.3
pairs = []
window = {}  # confident world points of the last SCALE_PAIRS frames, subsampled
for k in range(len(depth)):
    for j, pts in window.items():
        m = log_depth_ratio(pts, k)
        if m is not None:
            pairs.append((k, j, m))
    window[k] = back_project(k)[confident[k]][::4]
    window.pop(k - SCALE_PAIRS, None)
S = len(depth)
if pairs:
    pk, pj, pm = (np.array(c) for c in zip(*pairs))
    n = len(pm)
    A = coo_matrix((np.r_[np.ones(n), -np.ones(n)], (np.r_[np.arange(n), np.arange(n)], np.r_[pk, pj])),
                   shape=(n, S)).tocsr()
    scales = np.exp(spsolve((A.T @ A + SCALE_PRIOR * identity(S)).tocsc(), A.T @ pm))
else:
    scales = np.ones(S)
depth /= scales[:, None, None].astype(np.float32)
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
# One model pixel at the median depth: finer voxels would only split points
# the depth maps cannot tell apart (~0.3 % of the depth at 518 px wide).
median_depth = float(np.median(depth[confident & ~water]))
voxel = median_depth / float(np.median(K[:, 0, 0]))

# Voxel grid, filled frame by frame: one packed int64 key per voxel, with the
# sums of the positions and colours that fell in it and their count.
KEY_BITS = 21
KEY_HALF = 1 << (KEY_BITS - 1)


def voxel_keys(p: np.ndarray, edge: float) -> np.ndarray:
    q = np.floor(p / edge).astype(np.int64) + KEY_HALF
    # A frame can keep no pixel at all (diver filming open water).
    assert not q.size or q.min() >= 0 and q.max() < 1 << KEY_BITS, "cloud too large for the voxel key"
    return (q[:, 0] << 2 * KEY_BITS) | (q[:, 1] << KEY_BITS) | q[:, 2]


def merge(keys: np.ndarray, sums: np.ndarray, counts: np.ndarray):
    """Collapse rows sharing a key."""
    uniq, inv = np.unique(keys, return_inverse=True)
    return (uniq, np.stack([np.bincount(inv, sums[:, j], len(uniq)) for j in range(6)], 1),
            np.bincount(inv, counts, len(uniq)))


# Fine depth. LingBot-Map sees frames at 518 px wide, whatever the video's
# resolution (1440 px for NOAA, 3840 px for a phone). A monocular depth model
# run on the source frames at FINE x that resolution adds the relief the
# model's patches cannot see (coral branches, rock rims), and the colours come
# from the source frames instead of the model's downscaled input:
# - Depth Anything V2 Small (Apache-2.0) predicts relative inverse depth; it is
#   fitted per frame to LingBot's (affine in inverse depth, confident pixels,
#   the worst-fitting 20 % dropped and refitted);
# - LingBot keeps the shape: the remaining log ratio between both is smoothed
#   over one model patch (14 px, the model's own unit of detail) and applied,
#   so only relief finer than a patch comes from the monocular model;
# - the result stays within AGREE_TOL of LingBot's depth, the disagreement
#   the multi-view check already tolerates between frames. Unclamped, the
#   monocular model rebuilds low-confidence areas its own way (a cliff at the
#   reef / water edge on tab-south).
# Cross-frame depth error (frame k against k+2, median) is unchanged: site3
# 2.22 -> 2.19 %, tab-south 8.93 -> 8.88 %. Masks (confidence, agreement,
# water) stay at the model's resolution and are upsampled.
FINE, PATCH = 2, 14
MONO_MODEL, MONO_REVISION = "depth-anything/Depth-Anything-V2-Small-hf", "5426e4f0f36572d16453bbda7a8389317b1bef99"
fine = None
if args.frames:
    import torch
    from PIL import Image, ImageOps
    from transformers import AutoModelForDepthEstimation

    frame_paths = sorted(Path(args.frames).glob("*.jpg"))
    assert len(frame_paths) == len(depth), f"{len(frame_paths)} frames in {args.frames}, {len(depth)} reconstructed"
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    mono_model = AutoModelForDepthEstimation.from_pretrained(MONO_MODEL, revision=MONO_REVISION).to(device).eval()
    Hf, Wf = H * FINE, W * FINE
    # Same pixel grid as the model's, FINE times denser: (u + 0.5) * FINE - 0.5.
    Kf = K.copy()
    Kf[:, :2, :2] *= FINE
    Kf[:, :2, 2] = (K[:, :2, 2] + 0.5) * FINE - 0.5
    uf, vf = np.meshgrid(np.arange(Wf), np.arange(Hf))

    def fine_image(k: int) -> np.ndarray:
        """Source frame k as float32 RGB 0-1, oriented and stretched like the
        model's input (reconstruct.py), at FINE x its size."""
        img = ImageOps.exif_transpose(Image.open(frame_paths[k])).convert("RGB")
        if img.height > img.width:
            img = img.transpose(Image.ROTATE_270)
        return np.asarray(img.resize((Wf, Hf), Image.LANCZOS)).astype(np.float32) / 255

    @torch.no_grad()
    def mono_disparity(img: np.ndarray) -> np.ndarray:
        """Relative inverse depth of img, same size."""
        x = cv2.resize(img, (Wf // PATCH * PATCH, Hf // PATCH * PATCH), interpolation=cv2.INTER_AREA)
        x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]  # ImageNet normalisation
        x = torch.from_numpy(x.transpose(2, 0, 1)[None].astype(np.float32)).to(device)
        out = mono_model(pixel_values=x).predicted_depth[0].float().cpu().numpy()
        return cv2.resize(out, (Wf, Hf), interpolation=cv2.INTER_LINEAR)

    def fine_depth(k: int, img: np.ndarray) -> np.ndarray:
        up = cv2.resize(depth[k], (Wf, Hf), interpolation=cv2.INTER_LINEAR)
        ok = confident[k] & ~water[k]
        if ok.sum() < 500:  # nothing to fit on (open water)
            return up
        disp = mono_disparity(img)
        disp_m = cv2.resize(disp, (W, H), interpolation=cv2.INTER_AREA)
        A, y = np.stack([disp_m[ok], np.ones(ok.sum())], 1), 1 / depth[k][ok]
        fit = np.linalg.lstsq(A, y, rcond=None)[0]
        residual = np.abs(A @ fit - y)
        best = residual <= np.percentile(residual, 80)
        fit = np.linalg.lstsq(A[best], y[best], rcond=None)[0]
        inv_m = fit[0] * disp_m + fit[1]
        valid = (ok & (inv_m > 0)).astype(np.float32)
        log_ratio = np.where(valid > 0, np.log(depth[k] * np.maximum(inv_m, 1e-12)), 0).astype(np.float32)
        # Normalised convolution: smooth over valid pixels only.
        correction = (cv2.GaussianBlur(log_ratio * valid, (0, 0), PATCH)
                      / np.maximum(cv2.GaussianBlur(valid, (0, 0), PATCH), 1e-6))
        inv = fit[0] * disp + fit[1]
        z = np.exp(cv2.resize(correction, (Wf, Hf), interpolation=cv2.INTER_LINEAR)) / np.maximum(inv, 1e-12)
        z = np.where(inv > 0, z, up)
        return np.clip(z, up * np.exp(-AGREE_TOL), up * np.exp(AGREE_TOL)).astype(np.float32)

    def fine_points(k: int, keep: np.ndarray):
        """World points and colours of the kept pixels of frame k, at FINE x resolution."""
        img = fine_image(k)
        z = fine_depth(k, img).astype(np.float64)
        keep = cv2.resize(keep.astype(np.uint8), (Wf, Hf), interpolation=cv2.INTER_NEAREST).astype(bool)
        cam = np.stack([(uf - Kf[k, 0, 2]) / Kf[k, 0, 0] * z, (vf - Kf[k, 1, 2]) / Kf[k, 1, 1] * z, z], -1)[keep]
        return cam @ c2w[k, :, :3].T + c2w[k, :, 3], img[keep]

    fine = fine_points
    # Voxel down to one fine pixel at the median depth.
    voxel /= FINE

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
    pts, rgb = fine(k, keep) if fine else (world_k[keep], image(k)[keep])
    pending.append((voxel_keys(pts, voxel), np.hstack([pts, rgb]), np.ones(len(pts))))
    if len(pending) == 32 or k == len(depth) - 1:
        grid = merge(*(np.concatenate([g, *(p[i] for p in pending)]) for i, g in enumerate(grid)))
        pending = []

n_pixels = depth.size
print(f"confident pixels {n_confident / n_pixels * 100:.1f}%, + agreeing views {n_agreeing / n_pixels * 100:.1f}%, "
      f"after water removal {n_kept / n_pixels * 100:.1f}% -> {n_kept:,} points")
print(f"voxel {voxel:.5f} ({voxel / median_depth:.4f} x median depth): {len(grid[0]):,} points")


def fit_budget(grid, voxel: float, budget: int, name: str):
    """Regroup the voxels into coarser ones, weighted by their counts, until
    the cloud holds at most `budget` points. The cloud is a surface, so the
    point count goes with 1 / edge^2."""
    while len(grid[0]) > budget:
        voxel *= np.sqrt(len(grid[0]) / budget) * 1.02
        _, sums, counts = grid
        grid = merge(voxel_keys(sums[:, :3] / counts[:, None], voxel), sums, counts)
        print(f"over the {budget:,} point {name} budget: voxel {voxel:.5f} -> {len(grid[0]):,} points")
    return grid, voxel


grid, detail_voxel = fit_budget(grid, voxel, args.max_detail_points, "detail")
_, sums, counts = grid
pts, cols = sums[:, :3] / counts[:, None], sums[:, 3:] / counts[:, None]
del grid, sums

dist, _ = cKDTree(pts).query(pts, k=9, workers=-1)
mean_d = dist[:, 1:].mean(1)
inlier = mean_d < mean_d.mean() + 2 * mean_d.std()
pts, cols, counts = pts[inlier], cols[inlier], counts[inlier]
del dist, mean_d
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

# Overview: the detail cloud regrouped until it fits the web budget. Each
# detail point weighs as many pixels as it averaged.
base_grid, voxel = fit_budget(
    (voxel_keys(pts, detail_voxel), np.hstack([pts, cols]) * counts[:, None], counts),
    detail_voxel, args.max_points, "overview")
_, sums, base_counts = base_grid
base_pts, base_cols = sums[:, :3] / base_counts[:, None], sums[:, 3:] / base_counts[:, None]
del base_grid, sums, base_counts

out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)
shutil.rmtree(out / "tiles", ignore_errors=True)

# Detail tiles. A browser cannot hold a full-detail transect (tens of millions
# of points), so the detail cloud is cut into tiles of at most TILE_POINTS by
# recursive median splits along the longest side (a k-d tree: tiles follow the
# transect's shape, whatever its length). The overview points are split by the
# same planes, so the viewer can swap a tile's overview points for its detail.
# A tile is stored as uint16 positions within its bounding box (precision
# 1/65535 of the box, far below the voxel) then uint8 sRGB colours: 9 bytes.
TILE_POINTS = 250_000
tiles, base_order = [], []
if len(pts) > len(base_pts):
    (out / "tiles").mkdir()

    def split(idx: np.ndarray, base_idx: np.ndarray) -> None:
        p = pts[idx]
        if len(idx) <= TILE_POINTS:
            lo, hi = p.min(0), p.max(0)
            q = np.round((p - lo) / np.maximum(hi - lo, 1e-12) * 65535).astype("<u2")
            c = (cols[idx] * 255).round().clip(0, 255).astype(np.uint8)
            name = f"tiles/{len(tiles)}.bin"
            (out / name).write_bytes(q.tobytes() + c.tobytes())
            tiles.append({"file": name, "min": np.round(lo, 5).tolist(), "max": np.round(hi, 5).tolist(),
                          "points": len(idx), "base": [sum(len(b) for b in base_order), len(base_idx)]})
            base_order.append(base_idx)
            return
        axis = int(np.argmax(np.ptp(p, 0)))
        order = np.argsort(p[:, axis], kind="stable")
        cut = p[order[len(order) // 2], axis]
        left = base_pts[base_idx, axis] < cut
        split(idx[order[:len(order) // 2]], base_idx[left])
        split(idx[order[len(order) // 2:]], base_idx[~left])

    split(np.arange(len(pts)), np.arange(len(base_pts)))
    base_order = np.concatenate(base_order)
    base_pts, base_cols = base_pts[base_order], base_cols[base_order]
    print(f"detail: {len(tiles)} tiles, {len(pts):,} points, voxel {detail_voxel:.5f}, "
          f"{sum((out / t['file']).stat().st_size for t in tiles) / 1e6:.0f} MB")

trimesh.PointCloud(base_pts.astype(np.float32),
                   colors=(base_cols * 255).clip(0, 255).astype(np.uint8)).export(out / "cloud.ply")

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
        "model": "LingBot-Map (MLX, FP16)" + (" + Depth Anything V2 Small" if fine else ""),
        "frames": len(cams),
        "fps": fps,
        # Length of the source video; older sidecars predate it.
        "videoLength": round(meta["length"], 1) if "length" in meta else None,
        "points": len(base_pts),
        # Overview voxel; the detail tiles below have their own.
        "voxel": round(voxel, 6),
        "voxelOfMedianDepth": round(voxel / median_depth, 4),
        "confidence": args.conf,
        "keptPixels": round(n_kept / n_pixels, 3),
        "recoveredPixels": round(n_agreeing / n_pixels, 3),
        "depthScale": [round(float(np.percentile(scales, q)), 3) for q in (10, 90)],
        "pathLength": round(float(np.linalg.norm(np.diff(cams, axis=0), axis=1).sum()), 3),
        "medianDepth": round(median_depth, 4),
        "detailPoints": len(pts) if tiles else len(base_pts),
        "detailVoxel": round(detail_voxel if tiles else voxel, 6),
    },
    # Detail tiles: bounding box (same frame as cloud.ply), point count and
    # range of the overview points (start, count) they replace in cloud.ply.
    "tiles": tiles,
}))
print(f"saved {out / 'cloud.ply'} ({(out / 'cloud.ply').stat().st_size / 1e6:.1f} MB) and {out / 'path.json'}")
