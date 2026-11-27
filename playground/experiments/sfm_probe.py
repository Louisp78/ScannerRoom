"""Photogrammetry feasibility probe on a bench run (hybrid step 1).

Question: on these transect videos, how many frames can a classical
structure-from-motion (SfM) register, and do its camera poses agree with
LingBot-Map's? If SfM registers most frames in one piece, LingBot poses can
later be refined by bundle adjustment; if it fragments, only sparse points
are usable.

Reuses a finished bench run (its frames and recon.npz), so LingBot is not
re-run. Two stages, run as separate processes: PyTorch (feature matching) and
pycolmap (mapping) load clashing OpenMP runtimes in one process.

  python sfm_probe.py match <run-dir> [seconds]   # SuperPoint + LightGlue
  python sfm_probe.py map   <run-dir> [seconds]   # COLMAP incremental SfM + scores

[seconds] keeps only the start of the excerpt, to bound the run time.

Pairs follow the LingBot path: each frame is matched with its next few
neighbours, plus any later frame whose LingBot camera sits as close and looks
the same way (revisits, e.g. outbound and return legs).

Output: <run-dir>/sfm[-<seconds>s]/ (database, model, sfm.json).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

NEIGHBOURS = 5          # sequential pairs per frame
REVISIT_MAX_ANGLE = 30  # degrees between view directions for a revisit pair
MAX_KEYPOINTS = 2048
MAX_MAPPING_SECONDS = 3 * 3600  # a full transect (~1000 frames) needs far more than an excerpt
# COLMAP starts from the pair of frames seen from the widest angle and asks
# for 16 degrees by default, a setting for photo sets. Consecutive video
# frames are close together, so on a slow, level swim no pair qualifies and
# nothing is reconstructed; 8 degrees still gives a well-posed start.
INIT_MIN_TRI_ANGLE = 8
LIMIT = None            # first frames only, set from the optional <seconds> argument


def frame_paths(run):
    paths = sorted((run / "frames").glob("*.jpg"))
    return paths[:LIMIT] if LIMIT else paths


def lingbot_cameras(run):
    z = np.load(run / "recon.npz")
    c2w = z["extrinsic_w2c"].astype(np.float64)  # the port mislabels it: this is camera-to-world
    return c2w[:, :, 3], c2w[:, :, 2], z["intrinsic"][0].astype(np.float64), z["images"].shape[2]


def pairs_along_path(run, n):
    centres, forward, _, _ = lingbot_cameras(run)
    pairs = {(i, j) for i in range(n) for j in range(i + 1, min(n, i + 1 + NEIGHBOURS))}
    # A revisit is as close as the sequential window reaches, in the same direction.
    step = np.median(np.linalg.norm(np.diff(centres, axis=0), axis=1))
    reach = step * NEIGHBOURS
    cos_max = np.cos(np.radians(REVISIT_MAX_ANGLE))
    centres, forward = centres[:n], forward[:n]
    for i in range(n):
        d = np.linalg.norm(centres[i + NEIGHBOURS + 1:] - centres[i], axis=1)
        same_way = forward[i + NEIGHBOURS + 1:] @ forward[i] > cos_max
        # Nearest revisits only: a hovering camera would otherwise pair with
        # every frame around it and the matching cost explodes.
        near = np.nonzero((d < reach) & same_way)[0]
        for k in near[np.argsort(d[near])][:NEIGHBOURS]:
            pairs.add((i, i + NEIGHBOURS + 1 + int(k)))
    return sorted(pairs)


def stage_match(run, out):
    import cv2
    import torch
    from lightglue import LightGlue, SuperPoint

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    extractor = SuperPoint(max_num_keypoints=MAX_KEYPOINTS).eval().to(device)
    matcher = LightGlue(features="superpoint").eval().to(device)

    paths = frame_paths(run)
    feats, keypoints = [], {}
    t0 = time.time()
    with torch.inference_mode():
        for i, p in enumerate(paths):
            grey = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            img = torch.from_numpy(grey).float()[None, None].to(device) / 255.0
            f = extractor.extract(img)
            feats.append(f)
            keypoints[f"kp{i}"] = f["keypoints"][0].cpu().numpy()
        t_extract = time.time() - t0
        pairs = pairs_along_path(run, len(paths))
        matches = {}
        for i, j in pairs:
            m = matcher({"image0": feats[i], "image1": feats[j]})["matches"][0].cpu().numpy()
            matches[f"m{i}_{j}"] = m.astype(np.uint32)
    np.savez_compressed(out / "features.npz", **keypoints, **matches)
    info = {"frames": len(paths), "pairs": len(pairs),
            "revisitPairs": sum(1 for i, j in pairs if j - i > NEIGHBOURS),
            "extractSeconds": round(t_extract, 1), "matchSeconds": round(time.time() - t0 - t_extract, 1)}
    (out / "match.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info))


def align(rot_sfm_c2w, centres_sfm, rot_lb_c2w, centres_lb):
    """Similarity taking SfM's world onto LingBot's.

    Rotation from the camera orientations (chordal mean), not from the centres:
    a near-straight transect leaves the rotation about its own axis undefined.
    Scale and translation then by least squares on the centres.
    """
    u, _, vt = np.linalg.svd(np.einsum("kij,klj->il", rot_lb_c2w, rot_sfm_c2w))
    r = u @ np.diag([1, 1, np.sign(np.linalg.det(u @ vt))]) @ vt
    a = (r @ (centres_sfm - centres_sfm.mean(0)).T).T
    b = centres_lb - centres_lb.mean(0)
    s = (a * b).sum() / (a * a).sum()
    return s, r, centres_lb.mean(0) - s * r @ centres_sfm.mean(0)


def stage_map(run, out):
    import pycolmap
    from PIL import Image

    paths = frame_paths(run)
    data = np.load(out / "features.npz")
    db_path = out / "database.db"
    db_path.unlink(missing_ok=True)

    # One shared camera, focal seeded from LingBot's estimate, refined by BA.
    centres_lb, _, k_lb, width_lb = lingbot_cameras(run)
    w = Image.open(paths[0]).size[0]
    focal = k_lb[0, 0] * w / width_lb
    opts = pycolmap.ImageReaderOptions(camera_model="SIMPLE_RADIAL")
    pycolmap.Database.open(db_path).close()
    pycolmap.import_images(db_path, run / "frames", pycolmap.CameraMode.SINGLE, options=opts)

    db = pycolmap.Database.open(db_path)
    cam = next(iter(db.read_all_cameras()))
    cam.params = [focal, cam.params[1], cam.params[2], 0.0]
    cam.has_prior_focal_length = True
    db.update_camera(cam)
    ids = {img.name: img.image_id for img in db.read_all_images()}
    names = [p.name for p in paths]
    for i, name in enumerate(names):
        db.write_keypoints(ids[name], data[f"kp{i}"].astype(np.float32) + 0.5)  # COLMAP: pixel centre at 0.5
    pair_lines = []
    for key in (k for k in data.files if k.startswith("m")):
        i, j = map(int, key[1:].split("_"))
        db.write_matches(ids[names[i]], ids[names[j]], data[key])
        pair_lines.append(f"{names[i]} {names[j]}")
    db.close()
    (out / "pairs.txt").write_text("\n".join(pair_lines) + "\n")

    t0 = time.time()
    pycolmap.verify_matches(db_path, out / "pairs.txt")
    t_verify = time.time() - t0
    model_dir = out / "model"
    model_dir.mkdir(exist_ok=True)
    mopts = pycolmap.IncrementalPipelineOptions(max_runtime_seconds=MAX_MAPPING_SECONDS, random_seed=0)
    mopts.mapper.init_min_tri_angle = INIT_MIN_TRI_ANGLE
    models = pycolmap.incremental_mapping(db_path, run / "frames", model_dir, mopts)
    t_map = time.time() - t0 - t_verify

    sizes = sorted((m.num_reg_images() for m in models.values()), reverse=True)
    result = {"frames": len(paths), "models": len(models), "modelSizes": sizes,
              "registeredLargest": round(sizes[0] / len(paths), 3) if sizes else 0.0,
              "registeredAll": round(sum(sizes) / len(paths), 3),
              "verifySeconds": round(t_verify, 1), "mappingSeconds": round(t_map, 1)}
    if models:
        best = max(models.values(), key=lambda m: m.num_reg_images())
        index = {n: i for i, n in enumerate(names)}
        reg = sorted((index[img.name], img) for img in best.images.values() if img.has_pose)
        frames = np.array([i for i, _ in reg])
        centres = np.array([img.projection_center() for _, img in reg])
        rot_w2c = np.array([img.cam_from_world().rotation.matrix() for _, img in reg])
        # Agreement with LingBot: bring SfM into LingBot's frame (similarity),
        # then compare positions (relative to path length) and orientations.
        z = np.load(run / "recon.npz")
        rot_lb = z["extrinsic_w2c"][frames, :, :3].astype(np.float64)
        rot_sfm = np.transpose(rot_w2c, (0, 2, 1))
        s, r, t = align(rot_sfm, centres, rot_lb, centres_lb[frames])
        aligned = (s * (r @ centres.T)).T + t
        path_len = np.linalg.norm(np.diff(centres_lb[frames], axis=0), axis=1).sum()
        rel = np.einsum("kji,kjl->kil", r @ rot_sfm, rot_lb)
        ang = np.degrees(np.arccos(np.clip((np.trace(rel, axis1=1, axis2=2) - 1) / 2, -1, 1)))
        gaps = np.diff(frames)
        result.update({
            "points3D": best.num_points3D(),
            "meanReprojError": round(best.compute_mean_reprojection_error(), 3),
            "meanTrackLength": round(best.compute_mean_track_length(), 2),
            "focalSfm": round(float(best.cameras[next(iter(best.cameras))].params[0]), 1),
            "focalLingbot": round(float(focal), 1),
            "longestGapFrames": int(gaps.max()) - 1 if len(gaps) else 0,
            "positionErrorMedian": round(float(np.median(np.linalg.norm(aligned - centres_lb[frames], axis=1)) / path_len), 4),
            "rotationErrorMedianDeg": round(float(np.median(ang)), 2),
        })
        pts = np.array([p.xyz for p in best.points3D.values()])
        plot(out / "probe.png", run, result, centres_lb[frames], aligned,
             (s * (r @ pts.T)).T + t, rot_lb, frames, ang)
    (out / "sfm.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


def plot(path, run, result, path_lb, path_sfm, points, rot_lb, frames, ang):
    """Top and side views of both camera paths with SfM's sparse points, and
    the orientation gap per frame. Axes come from the data: along the path,
    across it, and the cameras' mean viewing direction (down onto the reef)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    down = rot_lb[:, :, 2].mean(0)
    down /= np.linalg.norm(down)
    along = path_lb[-1] - path_lb[0]
    along -= along @ down * down
    along /= np.linalg.norm(along)
    across = np.cross(down, along)
    origin = path_lb[0]
    proj = lambda x: np.stack([(x - origin) @ along, (x - origin) @ across, (x - origin) @ down], 1)
    lb, sf, pt = proj(path_lb), proj(path_sfm), proj(points)
    # Keep the reef, drop far outliers, for readable views.
    keep = np.all(np.abs(pt - np.median(pt, 0)) < 4 * np.percentile(np.abs(pt - np.median(pt, 0)), 90, axis=0), 1)
    pt = pt[keep]

    fig, ax = plt.subplots(3, 1, figsize=(11, 10), gridspec_kw={"height_ratios": [2, 1.3, 1]})
    for a, (i, j, title) in zip(ax[:2], [(0, 1, "top view"), (0, 2, "side view")]):
        a.scatter(pt[:, i], pt[:, j], s=0.3, c=pt[:, 2], cmap="viridis_r", alpha=0.5, lw=0)
        a.plot(lb[:, i], lb[:, j], "-", c="#e4572e", lw=2, label="LingBot cameras")
        a.plot(sf[:, i], sf[:, j], "--", c="#222", lw=1.5, label="SfM cameras (aligned)")
        a.set_title(title); a.set_aspect("equal"); a.legend(loc="upper right", fontsize=8)
    ax[1].invert_yaxis()
    ax[2].plot(frames, ang, c="#3a7ca5")
    ax[2].set_xlabel("frame"); ax[2].set_ylabel("orientation gap (deg)")
    ax[2].set_ylim(bottom=0)
    fig.suptitle(f"{run.parent.name}: {result['registeredLargest']:.0%} registered in one model, "
                 f"{result['models']} model(s), {result['points3D']} points, reproj {result['meanReprojError']} px\n"
                 f"position gap {result['positionErrorMedian']:.1%} of path, orientation gap median "
                 f"{result['rotationErrorMedianDeg']} deg", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    global LIMIT
    stage, run = sys.argv[1], Path(sys.argv[2]).resolve()
    if json.loads((run / "frames.json").read_text()).get("portrait"):
        # LingBot reconstructs portrait frames turned on their side and SfM
        # would see them upright: the comparison needs that rotation first.
        sys.exit("Portrait videos are not supported by the SfM probe yet")
    seconds = float(sys.argv[3]) if len(sys.argv) > 3 else None
    suffix = ""
    if seconds:
        LIMIT = round(seconds * json.loads((run / "frames.json").read_text())["fps"])
        suffix = f"-{seconds:g}s"
    out = run / f"sfm{suffix}"
    out.mkdir(exist_ok=True)
    {"match": stage_match, "map": stage_map}[stage](run, out)


if __name__ == "__main__":
    main()
