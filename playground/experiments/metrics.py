"""Score one experiment run and render its cloud, so variants can be compared.

Usage: metrics.py <run-dir>
Reads <run-dir>/recon.npz (reconstruct.py), <run-dir>/web/{cloud.ply,path.json}
(export-web.py) and <run-dir>/frames/; writes <run-dir>/metrics.json,
<run-dir>/render.png (cloud from above and from the side) and
<run-dir>/sample.jpg (the middle input frame, as LingBot-Map saw it).

Metrics, all scale-free (the reconstruction's scale is arbitrary):
- confident: share of pixels above the export's confidence threshold (1.05).
  Caveat: the model can be "confident" and wrong; read it with the others.
- depthError2 / depthError8: raw model consistency, before export-web's scale
  correction. Frame k's confident pixels reprojected into frame k+2 (k+8):
  median |log| of predicted depth over reprojected depth, median over k. Lower
  = the model agrees with itself across views.
- jitter: median |second difference| / median |first difference| of the
  camera centres. Lower = smoother, more plausible trajectory.
- thickness: median spread of the cloud across its local surface (smallest
  PCA axis of each point's 16 neighbours), in voxels. Lower = crisper
  surfaces, fewer doubled layers.
- kept / recovered / points / depthScale: copied from path.json.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import trimesh
from scipy.spatial import cKDTree

CONF = 1.05
run = Path(sys.argv[1])
d = np.load(run / "recon.npz", allow_pickle=False)
c2w = d["extrinsic_w2c"].astype(np.float64)  # true camera-to-world, see export-web.py
K = d["intrinsic"].astype(np.float64)
depth = d["depth"][..., 0].astype(np.float64)
conf = d["depth_conf"]
S, H, W = depth.shape
u, v = np.meshgrid(np.arange(W), np.arange(H))


def depth_error(gap: int) -> float:
    errs = []
    for k in range(S - gap):
        j = k + gap
        m = conf[k] > CONF
        z = depth[k][m]
        cam = np.stack([(u[m] - K[k, 0, 2]) / K[k, 0, 0] * z, (v[m] - K[k, 1, 2]) / K[k, 1, 1] * z, z], -1)
        q = (cam @ c2w[k, :, :3].T + c2w[k, :, 3] - c2w[j, :, 3]) @ c2w[j, :, :3]
        x = np.round(K[j, 0, 0] * q[:, 0] / q[:, 2] + K[j, 0, 2])
        y = np.round(K[j, 1, 1] * q[:, 1] / q[:, 2] + K[j, 1, 2])
        ok = (q[:, 2] > 0) & (x >= 0) & (x < W) & (y >= 0) & (y < H)
        if ok.sum() < 500:
            continue
        xi, yi = x[ok].astype(int), y[ok].astype(int)
        errs.append(np.median(np.abs(np.log(depth[j, yi, xi] / q[ok, 2]))))
    return float(np.median(errs)) if errs else float("nan")


centres = c2w[:, :3, 3]
step = np.linalg.norm(np.diff(centres, axis=0), axis=1)
accel = np.linalg.norm(np.diff(centres, 2, axis=0), axis=1)

path = json.loads((run / "web/path.json").read_text())["reconstruction"]
cloud = trimesh.load(run / "web/cloud.ply")
pts = np.asarray(cloud.vertices, np.float64)
cols = np.asarray(cloud.colors)[:, :3]
_, idx = cKDTree(pts).query(pts, k=16)
nb = pts[idx] - pts[idx].mean(1, keepdims=True)
smallest = np.linalg.eigvalsh(np.einsum("nki,nkj->nij", nb, nb) / 16)[:, 0]
thickness = float(np.median(np.sqrt(np.maximum(smallest, 0))) / path["voxel"])

metrics = {
    "confident": round(float((conf > CONF).mean()), 3),
    "depthError2": round(depth_error(2), 4),
    "depthError8": round(depth_error(8), 4),
    "jitter": round(float(np.median(accel) / np.median(step)), 3),
    "thickness": round(thickness, 3),
    "kept": path["keptPixels"],
    "recovered": path["recoveredPixels"],
    "points": path["points"],
    "depthScale": path["depthScale"],
}
(run / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
print(json.dumps(metrics))


def splat(p: np.ndarray, c: np.ndarray, axes: tuple[int, int], toward: int, size: int = 900) -> np.ndarray:
    """Orthographic render: project on two axes, nearest point along `toward` wins."""
    a, b = p[:, axes[0]], p[:, axes[1]]
    lo_a, hi_a = np.percentile(a, [0.5, 99.5])
    lo_b, hi_b = np.percentile(b, [0.5, 99.5])
    s = (size - 1) / max(hi_a - lo_a, hi_b - lo_b)
    x = ((a - lo_a) * s).astype(int)
    y = ((b - lo_b) * s).astype(int)
    ok = (x >= 0) & (x < size) & (y >= 0) & (y < size)
    order = np.argsort(-p[ok, toward])  # far first, near overwrite
    img = np.full((size, size, 3), 255, np.uint8)
    img[y[ok][order], x[ok][order]] = c[ok][order]
    # Close single-pixel gaps between points.
    return cv2.morphologyEx(img, cv2.MORPH_ERODE, np.ones((2, 2), np.uint8))


# Upright camera frame (export-web.py): x right, y down, z forward.
# Above: x across, z along the swim, looking down (smaller y = higher = nearer).
top = splat(pts, cols, (0, 2), toward=1)[::-1]
side = splat(pts, cols, (2, 1), toward=0)
render = np.hstack([top, np.full((top.shape[0], 8, 3), 255, np.uint8), side])
cv2.imwrite(str(run / "render.png"), cv2.cvtColor(render, cv2.COLOR_RGB2BGR))
frames = sorted((run / "frames").glob("*.jpg"))
mid = cv2.imread(str(frames[len(frames) // 2]))
cv2.imwrite(str(run / "sample.jpg"), cv2.resize(mid, (mid.shape[1] // 2, mid.shape[0] // 2)))
